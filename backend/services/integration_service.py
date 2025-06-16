"""Integration service for managing integration lifecycle and operations."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from lib.logger import logger
from lib.exceptions import AIRException
from models.orm.integration import Integration
from models.orm.user import User
from .oauth_service import OAuthService
from .token_refresh import TokenRefreshService, RefreshResult


class IntegrationStatus(str, Enum):
    """Integration status values."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    EXPIRED = "expired"
    REVOKED = "revoked"


class SyncFrequency(str, Enum):
    """Sync frequency options."""
    REALTIME = "realtime"
    HOURLY = "hourly"
    DAILY = "daily"
    MANUAL = "manual"


class IntegrationHealth(str, Enum):
    """Integration health status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class IntegrationService:
    """Service for managing integration lifecycle and operations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.oauth_service = OAuthService(db)
        self.token_refresh_service = TokenRefreshService(db)
    
    def create_integration(
        self,
        user_id: UUID,
        platform: str,
        provider_name: str,
        sync_frequency: SyncFrequency = SyncFrequency.HOURLY,
        auto_sync_enabled: bool = True,
        sync_settings: Optional[Dict[str, Any]] = None
    ) -> Integration:
        """
        Create a new integration.
        
        Args:
            user_id: User ID
            platform: Platform identifier
            provider_name: Human-readable provider name
            sync_frequency: How often to sync
            auto_sync_enabled: Whether auto-sync is enabled
            sync_settings: Platform-specific sync settings
            
        Returns:
            Created Integration instance
        """
        # Check if integration already exists
        existing = self.db.query(Integration).filter(
            and_(
                Integration.user_id == user_id,
                Integration.platform == platform
            )
        ).first()
        
        if existing:
            raise AIRException(f"Integration already exists for user {user_id} and platform {platform}")
        
        integration = Integration(
            user_id=user_id,
            platform=platform,
            provider_name=provider_name,
            status=IntegrationStatus.DISCONNECTED,
            sync_frequency=sync_frequency.value,
            auto_sync_enabled=auto_sync_enabled,
            sync_settings=sync_settings or {}
        )
        
        self.db.add(integration)
        self.db.commit()
        
        logger.info(f"Created integration {integration.id} for user {user_id} with platform {platform}")
        return integration
    
    def update_integration_settings(
        self,
        integration_id: UUID,
        sync_frequency: Optional[SyncFrequency] = None,
        auto_sync_enabled: Optional[bool] = None,
        sync_settings: Optional[Dict[str, Any]] = None
    ) -> Integration:
        """
        Update integration settings.
        
        Args:
            integration_id: Integration ID to update
            sync_frequency: New sync frequency
            auto_sync_enabled: New auto-sync setting
            sync_settings: New sync settings
            
        Returns:
            Updated Integration instance
        """
        integration = self.db.query(Integration).filter(
            Integration.id == integration_id
        ).first()
        
        if not integration:
            raise AIRException(f"Integration {integration_id} not found")
        
        if sync_frequency is not None:
            integration.sync_frequency = sync_frequency.value
        
        if auto_sync_enabled is not None:
            integration.auto_sync_enabled = auto_sync_enabled
        
        if sync_settings is not None:
            integration.update_sync_settings(sync_settings)
        
        integration.updated_at = datetime.utcnow()
        self.db.commit()
        
        logger.info(f"Updated settings for integration {integration_id}")
        return integration
    
    def get_integration(self, integration_id: UUID) -> Optional[Integration]:
        """Get integration by ID."""
        return self.db.query(Integration).filter(
            Integration.id == integration_id
        ).first()
    
    async def update_integration_metadata(
        self,
        integration_id: UUID,
        metadata_updates: Dict[str, Any]
    ) -> Integration:
        """
        Update integration metadata.
        
        Args:
            integration_id: Integration ID to update
            metadata_updates: Dictionary of metadata updates
            
        Returns:
            Updated Integration instance
        """
        integration = self.db.query(Integration).filter(
            Integration.id == integration_id
        ).first()
        
        if not integration:
            raise AIRException(f"Integration {integration_id} not found")
        
        # Update platform_metadata
        current_metadata = integration.platform_metadata or {}
        current_metadata.update(metadata_updates)
        integration.platform_metadata = current_metadata
        integration.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        logger.info(f"Updated metadata for integration {integration_id}")
        return integration
    
    def get_user_integrations(
        self,
        user_id: UUID,
        status_filter: Optional[List[IntegrationStatus]] = None,
        platform_filter: Optional[List[str]] = None
    ) -> List[Integration]:
        """
        Get integrations for a user with optional filters.
        
        Args:
            user_id: User ID
            status_filter: Filter by status
            platform_filter: Filter by platform
            
        Returns:
            List of Integration instances
        """
        query = self.db.query(Integration).filter(Integration.user_id == user_id)
        
        if status_filter:
            query = query.filter(Integration.status.in_([s.value for s in status_filter]))
        
        if platform_filter:
            query = query.filter(Integration.platform.in_(platform_filter))
        
        return query.order_by(desc(Integration.created_at)).all()
    
    def get_integrations_for_sync(
        self,
        sync_frequency: SyncFrequency,
        limit: Optional[int] = None
    ) -> List[Integration]:
        """
        Get integrations that need syncing for a given frequency.
        
        Args:
            sync_frequency: Sync frequency to filter by
            limit: Maximum number of integrations to return
            
        Returns:
            List of Integration instances ready for sync
        """
        now = datetime.utcnow()
        
        # Calculate cutoff time based on frequency
        if sync_frequency == SyncFrequency.HOURLY:
            cutoff = now - timedelta(hours=1)
        elif sync_frequency == SyncFrequency.DAILY:
            cutoff = now - timedelta(days=1)
        else:
            cutoff = now - timedelta(minutes=5)  # Default for realtime
        
        query = self.db.query(Integration).filter(
            and_(
                Integration.status == IntegrationStatus.CONNECTED,
                Integration.auto_sync_enabled == True,
                Integration.sync_frequency == sync_frequency.value,
                or_(
                    Integration.last_sync_at.is_(None),
                    Integration.last_sync_at <= cutoff
                ),
                or_(
                    Integration.retry_after.is_(None),
                    Integration.retry_after <= now
                )
            )
        ).order_by(Integration.last_sync_at.asc().nullsfirst())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    async def sync_integration(
        self,
        integration_id: UUID,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Perform sync operation for an integration.
        
        Args:
            integration_id: Integration ID to sync
            force: Force sync even if not due
            
        Returns:
            Sync result dictionary
        """
        integration = self.get_integration(integration_id)
        if not integration:
            return {"success": False, "error": "Integration not found"}
        
        # Check if sync is needed
        if not force and not self._should_sync_now(integration):
            return {"success": True, "skipped": True, "reason": "Sync not due"}
        
        # Ensure we have a valid token
        oauth_token = await self.oauth_service.ensure_valid_token(integration)
        if not oauth_token:
            return {"success": False, "error": "Unable to get valid token"}
        
        # Mark sync as started
        sync_start = datetime.utcnow()
        integration.mark_sync_started()
        self.db.commit()
        
        try:
            # TODO: Implement actual sync logic based on platform
            # This would call platform-specific sync services
            sync_result = await self._perform_platform_sync(integration, oauth_token)
            
            # Mark sync as completed
            sync_duration = int((datetime.utcnow() - sync_start).total_seconds())
            integration.mark_sync_completed(
                items_synced=sync_result.get("items_synced", 0),
                duration_seconds=sync_duration
            )
            self.db.commit()
            
            logger.info(f"Successfully synced integration {integration_id}")
            return {
                "success": True,
                "items_synced": sync_result.get("items_synced", 0),
                "duration_seconds": sync_duration
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Sync failed for integration {integration_id}: {error_msg}")
            
            # Calculate retry delay
            retry_minutes = self._calculate_sync_retry_delay(integration)
            integration.mark_sync_failed(error_msg, retry_minutes)
            self.db.commit()
            
            return {
                "success": False,
                "error": error_msg,
                "retry_after_minutes": retry_minutes
            }
    
    async def bulk_sync_integrations(
        self,
        sync_frequency: SyncFrequency,
        max_concurrent: int = 10
    ) -> Dict[str, Any]:
        """
        Perform bulk sync for integrations with given frequency.
        
        Args:
            sync_frequency: Sync frequency to process
            max_concurrent: Maximum concurrent syncs
            
        Returns:
            Bulk sync results
        """
        integrations = self.get_integrations_for_sync(sync_frequency, limit=100)
        
        if not integrations:
            return {"total": 0, "success": 0, "failed": 0, "skipped": 0}
        
        logger.info(f"Starting bulk sync for {len(integrations)} integrations with frequency {sync_frequency}")
        
        results = {"total": len(integrations), "success": 0, "failed": 0, "skipped": 0}
        
        # Process in batches to avoid overwhelming the system
        import asyncio
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def sync_with_semaphore(integration):
            async with semaphore:
                result = await self.sync_integration(integration.id)
                if result.get("success"):
                    if result.get("skipped"):
                        results["skipped"] += 1
                    else:
                        results["success"] += 1
                else:
                    results["failed"] += 1
                return result
        
        tasks = [sync_with_semaphore(integration) for integration in integrations]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info(f"Bulk sync completed: {results}")
        return results
    
    def get_integration_health(self, integration_id: UUID) -> IntegrationHealth:
        """
        Assess the health of an integration.
        
        Args:
            integration_id: Integration ID to assess
            
        Returns:
            Health status
        """
        integration = self.get_integration(integration_id)
        if not integration:
            return IntegrationHealth.UNKNOWN
        
        now = datetime.utcnow()
        
        # Critical: Integration is disconnected, expired, or revoked
        if integration.status in [IntegrationStatus.DISCONNECTED, IntegrationStatus.EXPIRED, IntegrationStatus.REVOKED]:
            return IntegrationHealth.CRITICAL
        
        # Critical: Token is expired
        if integration.is_token_expired():
            return IntegrationHealth.CRITICAL
        
        # Critical: High error count
        if (integration.error_count or 0) >= 5:
            return IntegrationHealth.CRITICAL
        
        # Warning: Token expiring soon
        if integration.is_token_expiring_soon(buffer_minutes=60):  # 1 hour buffer
            return IntegrationHealth.WARNING
        
        # Warning: Recent errors
        if integration.error_count and integration.error_count > 0:
            return IntegrationHealth.WARNING
        
        # Warning: No recent sync for auto-sync enabled integrations
        if integration.auto_sync_enabled and integration.last_successful_sync_at:
            hours_since_sync = (now - integration.last_successful_sync_at).total_seconds() / 3600
            if hours_since_sync > 24:  # No sync in 24 hours
                return IntegrationHealth.WARNING
        
        return IntegrationHealth.HEALTHY
    
    def get_integration_metrics(self, integration_id: UUID) -> Dict[str, Any]:
        """
        Get comprehensive metrics for an integration.
        
        Args:
            integration_id: Integration ID
            
        Returns:
            Metrics dictionary
        """
        integration = self.get_integration(integration_id)
        if not integration:
            return {}
        
        now = datetime.utcnow()
        
        # Calculate uptime percentage (last 30 days)
        thirty_days_ago = now - timedelta(days=30)
        
        metrics = {
            "integration_id": str(integration_id),
            "platform": integration.platform,
            "status": integration.status,
            "health": self.get_integration_health(integration_id).value,
            "total_syncs": integration.total_syncs or 0,
            "total_items_synced": integration.total_items_synced or 0,
            "error_count": integration.error_count or 0,
            "last_sync_duration_seconds": integration.last_sync_duration_seconds,
            "sync_frequency": integration.sync_frequency,
            "auto_sync_enabled": integration.auto_sync_enabled,
            "features_enabled": integration.features_enabled or [],
            "created_at": integration.created_at.isoformat() if integration.created_at else None,
            "last_sync_at": integration.last_sync_at.isoformat() if integration.last_sync_at else None,
            "last_successful_sync_at": integration.last_successful_sync_at.isoformat() if integration.last_successful_sync_at else None,
            "last_error_at": integration.last_error_at.isoformat() if integration.last_error_at else None,
            "token_expires_at": integration.token_expires_at.isoformat() if integration.token_expires_at else None,
        }
        
        # Calculate time-based metrics
        if integration.last_successful_sync_at:
            hours_since_sync = (now - integration.last_successful_sync_at).total_seconds() / 3600
            metrics["hours_since_last_sync"] = round(hours_since_sync, 2)
        
        if integration.token_expires_at:
            hours_until_expiry = (integration.token_expires_at - now).total_seconds() / 3600
            metrics["hours_until_token_expiry"] = round(hours_until_expiry, 2)
        
        # Calculate average sync performance
        if integration.total_syncs and integration.total_syncs > 0:
            if integration.last_sync_duration_seconds:
                metrics["average_sync_duration_seconds"] = integration.last_sync_duration_seconds
            
            if integration.total_items_synced:
                metrics["average_items_per_sync"] = round(
                    integration.total_items_synced / integration.total_syncs, 2
                )
        
        return metrics
    
    def get_user_integration_summary(self, user_id: UUID) -> Dict[str, Any]:
        """
        Get summary of all integrations for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Summary dictionary
        """
        integrations = self.get_user_integrations(user_id)
        
        summary = {
            "total_integrations": len(integrations),
            "by_status": {},
            "by_platform": {},
            "by_health": {},
            "total_syncs": 0,
            "total_items_synced": 0,
            "auto_sync_enabled_count": 0,
            "features_enabled": set()
        }
        
        for integration in integrations:
            # Count by status
            status = integration.status
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
            
            # Count by platform
            platform = integration.platform
            summary["by_platform"][platform] = summary["by_platform"].get(platform, 0) + 1
            
            # Count by health
            health = self.get_integration_health(integration.id).value
            summary["by_health"][health] = summary["by_health"].get(health, 0) + 1
            
            # Aggregate metrics
            summary["total_syncs"] += integration.total_syncs or 0
            summary["total_items_synced"] += integration.total_items_synced or 0
            
            if integration.auto_sync_enabled:
                summary["auto_sync_enabled_count"] += 1
            
            # Collect all enabled features
            if integration.features_enabled:
                summary["features_enabled"].update(integration.features_enabled)
        
        summary["features_enabled"] = list(summary["features_enabled"])
        
        return summary
    
    def _should_sync_now(self, integration: Integration) -> bool:
        """Check if integration should be synced now."""
        if not integration.auto_sync_enabled:
            return False
        
        if integration.status != IntegrationStatus.CONNECTED:
            return False
        
        # Check retry delay
        if integration.retry_after and datetime.utcnow() < integration.retry_after:
            return False
        
        # Check if sync is due based on frequency
        if not integration.last_sync_at:
            return True
        
        now = datetime.utcnow()
        time_since_sync = now - integration.last_sync_at
        
        if integration.sync_frequency == SyncFrequency.REALTIME:
            return time_since_sync >= timedelta(minutes=5)
        elif integration.sync_frequency == SyncFrequency.HOURLY:
            return time_since_sync >= timedelta(hours=1)
        elif integration.sync_frequency == SyncFrequency.DAILY:
            return time_since_sync >= timedelta(days=1)
        
        return False
    
    async def _perform_platform_sync(self, integration: Integration, oauth_token) -> Dict[str, Any]:
        """
        Perform platform-specific sync operation.
        
        This is a placeholder that would be implemented with actual platform sync logic.
        """
        # TODO: Implement platform-specific sync logic
        # This would dispatch to platform-specific sync services
        
        logger.info(f"Performing sync for platform {integration.platform}")
        
        # Simulate sync operation
        import asyncio
        await asyncio.sleep(0.1)  # Simulate API call
        
        return {
            "items_synced": 10,  # Placeholder
            "success": True
        }
    
    def _calculate_sync_retry_delay(self, integration: Integration) -> int:
        """Calculate retry delay in minutes for failed sync."""
        error_count = integration.error_count or 0
        
        # Exponential backoff: 5, 10, 20, 40, 60 minutes (max)
        delay_minutes = min(5 * (2 ** error_count), 60)
        
        return delay_minutes 