"""Token refresh service for managing OAuth token lifecycle."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from lib.oauth_client import OAuthClient, OAuthProvider, OAuthToken, OAuthError
from lib.logger import logger
from lib.exceptions import AIRException
from models.orm.integration import Integration
from models.orm.user import User


class RefreshResult(str, Enum):
    """Token refresh operation results."""
    SUCCESS = "success"
    FAILED = "failed"
    NO_REFRESH_TOKEN = "no_refresh_token"
    PROVIDER_ERROR = "provider_error"
    RATE_LIMITED = "rate_limited"
    REVOKED = "revoked"


class TokenRefreshError(AIRException):
    """Token refresh specific error."""
    
    def __init__(self, message: str, result: RefreshResult, retry_after: Optional[int] = None):
        super().__init__(message)
        self.result = result
        self.retry_after = retry_after


class TokenRefreshService:
    """Service for managing OAuth token refresh operations."""
    
    def __init__(self, db: Session, oauth_client: Optional[OAuthClient] = None):
        self.db = db
        self.oauth_client = oauth_client or OAuthClient()
        
        # Rate limiting configuration (per provider)
        self.rate_limits = {
            OAuthProvider.GOOGLE: {"requests_per_hour": 100, "burst": 10},
            OAuthProvider.LINKEDIN: {"requests_per_hour": 50, "burst": 5},
            OAuthProvider.MICROSOFT: {"requests_per_hour": 100, "burst": 10},
            OAuthProvider.GITHUB: {"requests_per_hour": 100, "burst": 10},
        }
        
        # Retry configuration
        self.max_retries = 3
        self.base_retry_delay = 60  # seconds
        self.max_retry_delay = 3600  # 1 hour
    
    async def refresh_token_for_integration(
        self, 
        integration: Integration,
        force: bool = False
    ) -> Tuple[RefreshResult, Optional[str]]:
        """
        Refresh token for a specific integration.
        
        Args:
            integration: Integration to refresh token for
            force: Force refresh even if token is not expiring
            
        Returns:
            Tuple of (result, error_message)
        """
        try:
            # Check if refresh is needed
            if not force and not integration.is_token_expiring_soon():
                logger.debug(f"Token for integration {integration.id} not expiring soon, skipping refresh")
                return RefreshResult.SUCCESS, None
            
            # Check if we have a refresh token
            if not integration.refresh_token:
                logger.warning(f"No refresh token available for integration {integration.id}")
                integration.status = "expired"
                integration.error_message = "No refresh token available for automatic refresh"
                self.db.commit()
                return RefreshResult.NO_REFRESH_TOKEN, "No refresh token available"
            
            # Check rate limiting
            if not self._can_refresh_now(integration):
                retry_after = self._get_retry_delay(integration)
                logger.info(f"Rate limited for integration {integration.id}, retry after {retry_after} seconds")
                return RefreshResult.RATE_LIMITED, f"Rate limited, retry after {retry_after} seconds"
            
            # Get provider enum
            provider = integration.get_provider_enum()
            if not provider:
                error_msg = f"Unknown provider: {integration.platform}"
                logger.error(error_msg)
                return RefreshResult.PROVIDER_ERROR, error_msg
            
            # Attempt token refresh
            logger.info(f"Refreshing token for integration {integration.id} (provider: {provider})")
            
            try:
                new_token = await self.oauth_client.refresh_token(provider, integration.refresh_token)
                
                # Store the new token
                integration.store_oauth_token(new_token)
                integration.status = "connected"
                integration.error_message = None
                integration.error_count = 0
                integration.retry_after = None
                
                self.db.commit()
                
                logger.info(f"Successfully refreshed token for integration {integration.id}")
                return RefreshResult.SUCCESS, None
                
            except OAuthError as e:
                error_msg = str(e)
                logger.error(f"OAuth error refreshing token for integration {integration.id}: {error_msg}")
                
                # Handle specific OAuth errors
                if "invalid_grant" in error_msg.lower() or "refresh_token" in error_msg.lower():
                    # Refresh token is invalid/expired
                    integration.status = "revoked"
                    integration.error_message = "Refresh token expired or revoked"
                    integration.refresh_token = None
                    self.db.commit()
                    return RefreshResult.REVOKED, "Refresh token expired or revoked"
                
                elif "rate_limit" in error_msg.lower() or "quota" in error_msg.lower():
                    # Rate limited by provider
                    retry_after = self._calculate_retry_delay(integration)
                    integration.retry_after = datetime.utcnow() + timedelta(seconds=retry_after)
                    integration.mark_sync_failed(error_msg, retry_after // 60)
                    self.db.commit()
                    return RefreshResult.RATE_LIMITED, error_msg
                
                else:
                    # Other OAuth error
                    integration.mark_sync_failed(error_msg)
                    self.db.commit()
                    return RefreshResult.PROVIDER_ERROR, error_msg
            
        except Exception as e:
            error_msg = f"Unexpected error refreshing token: {str(e)}"
            logger.error(f"Error refreshing token for integration {integration.id}: {error_msg}")
            integration.mark_sync_failed(error_msg)
            self.db.commit()
            return RefreshResult.FAILED, error_msg
    
    async def refresh_expiring_tokens(
        self, 
        buffer_minutes: int = 5,
        max_concurrent: int = 10
    ) -> Dict[str, int]:
        """
        Refresh all tokens that are expiring soon.
        
        Args:
            buffer_minutes: Refresh tokens expiring within this many minutes
            max_concurrent: Maximum concurrent refresh operations
            
        Returns:
            Dictionary with counts of each result type
        """
        logger.info(f"Starting bulk token refresh for tokens expiring within {buffer_minutes} minutes")
        
        # Find integrations with expiring tokens
        cutoff_time = datetime.utcnow() + timedelta(minutes=buffer_minutes)
        
        expiring_integrations = self.db.query(Integration).filter(
            and_(
                Integration.status.in_(["connected", "error"]),
                Integration.token_expires_at <= cutoff_time,
                Integration.refresh_token_encrypted.isnot(None),
                or_(
                    Integration.retry_after.is_(None),
                    Integration.retry_after <= datetime.utcnow()
                )
            )
        ).all()
        
        if not expiring_integrations:
            logger.info("No tokens found that need refreshing")
            return {"total": 0}
        
        logger.info(f"Found {len(expiring_integrations)} integrations with expiring tokens")
        
        # Process in batches to avoid overwhelming providers
        results = {
            "total": len(expiring_integrations),
            "success": 0,
            "failed": 0,
            "no_refresh_token": 0,
            "provider_error": 0,
            "rate_limited": 0,
            "revoked": 0
        }
        
        # Create semaphore to limit concurrent operations
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def refresh_with_semaphore(integration):
            async with semaphore:
                result, error = await self.refresh_token_for_integration(integration)
                results[result.value] += 1
                return result, error
        
        # Execute refreshes concurrently
        tasks = [refresh_with_semaphore(integration) for integration in expiring_integrations]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info(f"Bulk token refresh completed: {results}")
        return results
    
    async def refresh_user_tokens(
        self, 
        user_id: str,
        force: bool = False
    ) -> Dict[str, Tuple[RefreshResult, Optional[str]]]:
        """
        Refresh all tokens for a specific user.
        
        Args:
            user_id: User ID to refresh tokens for
            force: Force refresh even if tokens are not expiring
            
        Returns:
            Dictionary mapping integration IDs to (result, error_message)
        """
        logger.info(f"Refreshing tokens for user {user_id}")
        
        integrations = self.db.query(Integration).filter(
            and_(
                Integration.user_id == user_id,
                Integration.status.in_(["connected", "error", "expired"]),
                Integration.refresh_token_encrypted.isnot(None)
            )
        ).all()
        
        if not integrations:
            logger.info(f"No integrations found for user {user_id}")
            return {}
        
        results = {}
        for integration in integrations:
            result, error = await self.refresh_token_for_integration(integration, force=force)
            results[str(integration.id)] = (result, error)
        
        logger.info(f"Refreshed {len(integrations)} integrations for user {user_id}")
        return results
    
    def _can_refresh_now(self, integration: Integration) -> bool:
        """Check if we can refresh the token now (rate limiting)."""
        if not integration.retry_after:
            return True
        return datetime.utcnow() >= integration.retry_after
    
    def _get_retry_delay(self, integration: Integration) -> int:
        """Get the number of seconds until we can retry."""
        if not integration.retry_after:
            return 0
        delta = integration.retry_after - datetime.utcnow()
        return max(0, int(delta.total_seconds()))
    
    def _calculate_retry_delay(self, integration: Integration) -> int:
        """Calculate exponential backoff retry delay."""
        error_count = integration.error_count or 0
        delay = min(
            self.base_retry_delay * (2 ** error_count),
            self.max_retry_delay
        )
        return delay
    
    async def validate_token(self, integration: Integration) -> bool:
        """
        Validate that a token is still valid by making a test API call.
        
        Args:
            integration: Integration to validate
            
        Returns:
            True if token is valid, False otherwise
        """
        try:
            provider = integration.get_provider_enum()
            if not provider:
                return False
            
            oauth_token = integration.get_oauth_token()
            if not oauth_token:
                return False
            
            # Try to get user info as a validation test
            await self.oauth_client.get_user_info(provider, oauth_token)
            return True
            
        except Exception as e:
            logger.warning(f"Token validation failed for integration {integration.id}: {str(e)}")
            return False
    
    async def revoke_integration_tokens(self, integration: Integration) -> bool:
        """
        Revoke tokens for an integration.
        
        Args:
            integration: Integration to revoke tokens for
            
        Returns:
            True if revocation was successful
        """
        try:
            provider = integration.get_provider_enum()
            if not provider:
                logger.error(f"Unknown provider for integration {integration.id}")
                return False
            
            access_token = integration.access_token
            if not access_token:
                logger.warning(f"No access token to revoke for integration {integration.id}")
                return True  # Nothing to revoke
            
            # Attempt to revoke the token
            success = await self.oauth_client.revoke_token(provider, access_token)
            
            if success:
                logger.info(f"Successfully revoked token for integration {integration.id}")
            else:
                logger.warning(f"Token revocation may have failed for integration {integration.id}")
            
            # Clear tokens from database regardless of revocation result
            integration.revoke_tokens()
            self.db.commit()
            
            return success
            
        except Exception as e:
            logger.error(f"Error revoking tokens for integration {integration.id}: {str(e)}")
            return False
    
    def get_refresh_statistics(self) -> Dict[str, any]:
        """Get statistics about token refresh operations."""
        now = datetime.utcnow()
        
        # Count integrations by status
        status_counts = {}
        for status in ["connected", "expired", "error", "revoked", "disconnected"]:
            count = self.db.query(Integration).filter(Integration.status == status).count()
            status_counts[status] = count
        
        # Count tokens expiring soon
        expiring_soon = self.db.query(Integration).filter(
            and_(
                Integration.status == "connected",
                Integration.token_expires_at <= now + timedelta(hours=1)
            )
        ).count()
        
        # Count tokens with errors
        error_count = self.db.query(Integration).filter(
            Integration.error_count > 0
        ).count()
        
        # Count rate limited integrations
        rate_limited = self.db.query(Integration).filter(
            Integration.retry_after > now
        ).count()
        
        return {
            "status_counts": status_counts,
            "expiring_within_hour": expiring_soon,
            "with_errors": error_count,
            "rate_limited": rate_limited,
            "total_integrations": sum(status_counts.values())
        } 