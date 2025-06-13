"""High-level OAuth service for managing OAuth flows and token lifecycle."""

import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_

from lib.oauth_client import OAuthClient, OAuthProvider, OAuthToken, OAuthError
from lib.logger import logger
from lib.exceptions import AIRException
from models.orm.integration import Integration, OAuthState
from models.orm.user import User
from .token_refresh import TokenRefreshService, RefreshResult


class OAuthFlowError(AIRException):
    """OAuth flow specific error."""
    pass


class OAuthService:
    """High-level service for managing OAuth flows and integration lifecycle."""
    
    def __init__(self, db: Session, oauth_client: Optional[OAuthClient] = None):
        self.db = db
        self.oauth_client = oauth_client or OAuthClient()
        self.token_refresh_service = TokenRefreshService(db, oauth_client)
    
    async def initiate_oauth_flow(
        self,
        user_id: UUID,
        provider: OAuthProvider,
        redirect_uri: str,
        scopes: Optional[List[str]] = None
    ) -> Tuple[str, str]:
        """
        Initiate OAuth flow for a user.
        
        Args:
            user_id: User ID initiating the flow
            provider: OAuth provider
            redirect_uri: Redirect URI for OAuth callback
            scopes: Optional list of scopes to request
            
        Returns:
            Tuple of (authorization_url, state)
        """
        try:
            # Generate secure state parameter
            state = secrets.token_urlsafe(32)
            
            # Generate authorization URL
            auth_url, _ = self.oauth_client.get_auth_url(
                provider=provider,
                redirect_uri=redirect_uri,
                scopes=scopes,
                state=state
            )
            
            # Store OAuth state in database
            oauth_state = OAuthState(
                state=state,
                user_id=user_id,
                platform=provider.value,
                redirect_uri=redirect_uri,
                scopes=scopes or [],
                expires_at=datetime.utcnow() + timedelta(minutes=10)
            )
            
            self.db.add(oauth_state)
            self.db.commit()
            
            logger.info(f"Initiated OAuth flow for user {user_id} with provider {provider}")
            return auth_url, state
            
        except Exception as e:
            logger.error(f"Failed to initiate OAuth flow: {str(e)}")
            raise OAuthFlowError(f"Failed to initiate OAuth flow: {str(e)}")
    
    async def complete_oauth_flow(
        self,
        code: str,
        state: str,
        redirect_uri: str
    ) -> Integration:
        """
        Complete OAuth flow by exchanging code for tokens.
        
        Args:
            code: Authorization code from provider
            state: State parameter to validate
            redirect_uri: Redirect URI used in the flow
            
        Returns:
            Created or updated Integration instance
        """
        try:
            # Validate and retrieve OAuth state
            oauth_state = self.db.query(OAuthState).filter(
                and_(
                    OAuthState.state == state,
                    OAuthState.used == False,
                    OAuthState.expires_at > datetime.utcnow()
                )
            ).first()
            
            if not oauth_state:
                raise OAuthFlowError("Invalid or expired OAuth state")
            
            if oauth_state.redirect_uri != redirect_uri:
                raise OAuthFlowError("Redirect URI mismatch")
            
            # Mark state as used
            oauth_state.mark_used()
            
            # Get provider enum
            try:
                provider = OAuthProvider(oauth_state.platform)
            except ValueError:
                raise OAuthFlowError(f"Unsupported provider: {oauth_state.platform}")
            
            # Exchange code for tokens
            logger.info(f"Exchanging OAuth code for user {oauth_state.user_id} with provider {provider}")
            
            oauth_token = await self.oauth_client.exchange_code(
                provider=provider,
                code=code,
                state=state,
                redirect_uri=redirect_uri
            )
            
            # Get or create integration
            integration = self.db.query(Integration).filter(
                and_(
                    Integration.user_id == oauth_state.user_id,
                    Integration.platform == provider.value
                )
            ).first()
            
            if integration:
                logger.info(f"Updating existing integration {integration.id}")
            else:
                logger.info(f"Creating new integration for user {oauth_state.user_id} with provider {provider}")
                integration = Integration(
                    user_id=oauth_state.user_id,
                    platform=provider.value,
                    provider_name=provider.value.title()
                )
                self.db.add(integration)
            
            # Store OAuth token
            integration.store_oauth_token(oauth_token)
            integration.redirect_uri = redirect_uri
            
            # Get and store user info
            try:
                user_info = await self.oauth_client.get_user_info(provider, oauth_token)
                integration.platform_metadata = {
                    **integration.platform_metadata,
                    "user_info": user_info,
                    "connected_at": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.warning(f"Failed to get user info for integration {integration.id}: {str(e)}")
            
            self.db.commit()
            
            logger.info(f"Successfully completed OAuth flow for integration {integration.id}")
            return integration
            
        except OAuthError as e:
            logger.error(f"OAuth error completing flow: {str(e)}")
            raise OAuthFlowError(f"OAuth error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error completing OAuth flow: {str(e)}")
            raise OAuthFlowError(f"Failed to complete OAuth flow: {str(e)}")
    
    async def refresh_integration_token(
        self,
        integration_id: UUID,
        force: bool = False
    ) -> Tuple[RefreshResult, Optional[str]]:
        """
        Refresh token for a specific integration.
        
        Args:
            integration_id: Integration ID to refresh
            force: Force refresh even if token is not expiring
            
        Returns:
            Tuple of (result, error_message)
        """
        integration = self.db.query(Integration).filter(
            Integration.id == integration_id
        ).first()
        
        if not integration:
            return RefreshResult.FAILED, "Integration not found"
        
        return await self.token_refresh_service.refresh_token_for_integration(
            integration, force=force
        )
    
    async def ensure_valid_token(self, integration: Integration) -> Optional[OAuthToken]:
        """
        Ensure integration has a valid token, refreshing if necessary.
        
        Args:
            integration: Integration to check
            
        Returns:
            Valid OAuthToken or None if unable to get valid token
        """
        try:
            # Check if token is expiring soon
            if integration.is_token_expiring_soon():
                logger.info(f"Token expiring soon for integration {integration.id}, attempting refresh")
                
                result, error = await self.token_refresh_service.refresh_token_for_integration(
                    integration, force=False
                )
                
                if result != RefreshResult.SUCCESS:
                    logger.error(f"Failed to refresh token for integration {integration.id}: {error}")
                    return None
            
            # Return the current token
            return integration.get_oauth_token()
            
        except Exception as e:
            logger.error(f"Error ensuring valid token for integration {integration.id}: {str(e)}")
            return None
    
    async def disconnect_integration(self, integration_id: UUID) -> bool:
        """
        Disconnect an integration by revoking tokens and updating status.
        
        Args:
            integration_id: Integration ID to disconnect
            
        Returns:
            True if disconnection was successful
        """
        try:
            integration = self.db.query(Integration).filter(
                Integration.id == integration_id
            ).first()
            
            if not integration:
                logger.warning(f"Integration {integration_id} not found for disconnection")
                return False
            
            # Attempt to revoke tokens
            revoke_success = await self.token_refresh_service.revoke_integration_tokens(integration)
            
            # Update integration status
            integration.status = "disconnected"
            integration.error_message = None
            integration.error_count = 0
            integration.retry_after = None
            
            self.db.commit()
            
            logger.info(f"Successfully disconnected integration {integration_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting integration {integration_id}: {str(e)}")
            return False
    
    async def reconnect_integration(
        self,
        integration_id: UUID,
        redirect_uri: str,
        scopes: Optional[List[str]] = None
    ) -> Tuple[str, str]:
        """
        Initiate reconnection flow for an existing integration.
        
        Args:
            integration_id: Integration ID to reconnect
            redirect_uri: Redirect URI for OAuth callback
            scopes: Optional list of scopes to request
            
        Returns:
            Tuple of (authorization_url, state)
        """
        integration = self.db.query(Integration).filter(
            Integration.id == integration_id
        ).first()
        
        if not integration:
            raise OAuthFlowError("Integration not found")
        
        try:
            provider = OAuthProvider(integration.platform)
        except ValueError:
            raise OAuthFlowError(f"Unsupported provider: {integration.platform}")
        
        return await self.initiate_oauth_flow(
            user_id=integration.user_id,
            provider=provider,
            redirect_uri=redirect_uri,
            scopes=scopes
        )
    
    def get_user_integrations(
        self,
        user_id: UUID,
        status_filter: Optional[List[str]] = None
    ) -> List[Integration]:
        """
        Get all integrations for a user.
        
        Args:
            user_id: User ID to get integrations for
            status_filter: Optional list of statuses to filter by
            
        Returns:
            List of Integration instances
        """
        query = self.db.query(Integration).filter(Integration.user_id == user_id)
        
        if status_filter:
            query = query.filter(Integration.status.in_(status_filter))
        
        return query.all()
    
    def get_integration_by_platform(
        self,
        user_id: UUID,
        platform: str
    ) -> Optional[Integration]:
        """
        Get integration for a specific user and platform.
        
        Args:
            user_id: User ID
            platform: Platform name
            
        Returns:
            Integration instance or None
        """
        return self.db.query(Integration).filter(
            and_(
                Integration.user_id == user_id,
                Integration.platform == platform
            )
        ).first()
    
    async def validate_integration_token(self, integration_id: UUID) -> bool:
        """
        Validate that an integration's token is still valid.
        
        Args:
            integration_id: Integration ID to validate
            
        Returns:
            True if token is valid
        """
        integration = self.db.query(Integration).filter(
            Integration.id == integration_id
        ).first()
        
        if not integration:
            return False
        
        return await self.token_refresh_service.validate_token(integration)
    
    def get_oauth_statistics(self) -> Dict[str, any]:
        """Get OAuth and integration statistics."""
        stats = self.token_refresh_service.get_refresh_statistics()
        
        # Add OAuth-specific statistics
        now = datetime.utcnow()
        
        # Count OAuth states
        active_states = self.db.query(OAuthState).filter(
            and_(
                OAuthState.used == False,
                OAuthState.expires_at > now
            )
        ).count()
        
        expired_states = self.db.query(OAuthState).filter(
            OAuthState.expires_at <= now
        ).count()
        
        # Count integrations by provider
        provider_counts = {}
        for provider in OAuthProvider:
            count = self.db.query(Integration).filter(
                Integration.platform == provider.value
            ).count()
            provider_counts[provider.value] = count
        
        stats.update({
            "oauth_states": {
                "active": active_states,
                "expired": expired_states
            },
            "provider_counts": provider_counts
        })
        
        return stats
    
    async def cleanup_expired_oauth_states(self) -> int:
        """
        Clean up expired OAuth states.
        
        Returns:
            Number of states cleaned up
        """
        expired_states = self.db.query(OAuthState).filter(
            OAuthState.expires_at <= datetime.utcnow()
        ).all()
        
        count = len(expired_states)
        
        for state in expired_states:
            self.db.delete(state)
        
        self.db.commit()
        
        if count > 0:
            logger.info(f"Cleaned up {count} expired OAuth states")
        
        return count
    
    def get_available_providers(self) -> List[str]:
        """Get list of available OAuth providers."""
        return [provider.value for provider in self.oauth_client.get_available_providers()] 