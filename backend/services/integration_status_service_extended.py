"""Extended integration status tracking service with alert management and analytics."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from lib.logger import logger
from lib.exceptions import AIRException
from models.orm.integration import Integration
from models.orm.integration_status import (
    IntegrationStatusEvent, IntegrationHealthCheck, IntegrationAlert,
    IntegrationEventType, IntegrationSeverity
)
from .integration_service import IntegrationService, IntegrationStatus
from .integration_status_service import IntegrationStatusService, AlertType, HealthCheckType


class IntegrationStatusServiceExtended(IntegrationStatusService):
    """Extended integration status service with full alert management and analytics."""
    
    # Alert Management Methods
    
    def create_alert(
        self,
        integration_id: UUID,
        alert_type: AlertType,
        severity: IntegrationSeverity,
        title: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        notification_channels: Optional[List[str]] = None
    ) -> IntegrationAlert:
        """
        Create an integration alert.
        
        Args:
            integration_id: Integration ID
            alert_type: Type of alert
            severity: Alert severity
            title: Alert title
            message: Alert message
            details: Additional alert details
            notification_channels: Channels to send notifications
            
        Returns:
            Created IntegrationAlert
        """
        # Check if similar alert already exists and is active
        existing_alert = self.db.query(IntegrationAlert).filter(
            and_(
                IntegrationAlert.integration_id == integration_id,
                IntegrationAlert.alert_type == alert_type.value,
                IntegrationAlert.status.in_(["active", "acknowledged"])
            )
        ).first()
        
        if existing_alert:
            logger.info(f"Similar alert already exists for integration {integration_id}, alert type {alert_type.value}")
            return existing_alert
        
        alert = IntegrationAlert(
            integration_id=integration_id,
            alert_type=alert_type.value,
            severity=severity.value,
            title=title,
            message=message,
            details=details or {},
            notification_channels=notification_channels or []
        )
        
        self.db.add(alert)
        self.db.commit()
        
        logger.warning(f"Created alert {alert_type.value} for integration {integration_id}: {title}")
        
        # Log the alert creation as an event
        self.log_event(
            integration_id=integration_id,
            event_type=IntegrationEventType.ERROR_OCCURRED,
            severity=severity,
            message=f"Alert created: {title}",
            details={"alert_type": alert_type.value, "alert_id": str(alert.id)}
        )
        
        return alert
    
    def get_active_alerts(
        self,
        user_id: Optional[UUID] = None,
        integration_id: Optional[UUID] = None,
        severity_filter: Optional[List[IntegrationSeverity]] = None,
        alert_types: Optional[List[AlertType]] = None
    ) -> List[IntegrationAlert]:
        """Get active alerts with optional filters."""
        query = self.db.query(IntegrationAlert).filter(
            IntegrationAlert.status.in_(["active", "acknowledged"])
        )
        
        if user_id:
            query = query.join(Integration).filter(Integration.user_id == user_id)
        
        if integration_id:
            query = query.filter(IntegrationAlert.integration_id == integration_id)
        
        if severity_filter:
            query = query.filter(IntegrationAlert.severity.in_([s.value for s in severity_filter]))
        
        if alert_types:
            query = query.filter(IntegrationAlert.alert_type.in_([a.value for a in alert_types]))
        
        return query.order_by(desc(IntegrationAlert.created_at)).all()
    
    def acknowledge_alert(self, alert_id: UUID, acknowledged_by: str) -> IntegrationAlert:
        """Acknowledge an alert."""
        alert = self.db.query(IntegrationAlert).filter(IntegrationAlert.id == alert_id).first()
        if not alert:
            raise AIRException(f"Alert {alert_id} not found")
        
        alert.acknowledge(acknowledged_by)
        self.db.commit()
        
        logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
        return alert
    
    def resolve_alert(
        self,
        alert_id: UUID,
        resolution_message: str,
        auto_resolved: bool = False
    ) -> IntegrationAlert:
        """Resolve an alert."""
        alert = self.db.query(IntegrationAlert).filter(IntegrationAlert.id == alert_id).first()
        if not alert:
            raise AIRException(f"Alert {alert_id} not found")
        
        alert.resolve(resolution_message, auto_resolved)
        self.db.commit()
        
        # Log the resolution as an event
        self.log_event(
            integration_id=alert.integration_id,
            event_type=IntegrationEventType.ERROR_RESOLVED,
            severity=IntegrationSeverity.INFO,
            message=f"Alert resolved: {resolution_message}",
            details={"alert_id": str(alert_id), "auto_resolved": auto_resolved}
        )
        
        logger.info(f"Alert {alert_id} resolved: {resolution_message}")
        return alert
    
    # Bulk Operations
    
    async def bulk_health_check(
        self,
        user_id: Optional[UUID] = None,
        check_types: Optional[List[HealthCheckType]] = None,
        max_concurrent: int = 10
    ) -> Dict[str, Any]:
        """
        Perform bulk health checks on integrations.
        
        Args:
            user_id: Optional user ID to filter integrations
            check_types: Types of checks to perform
            max_concurrent: Maximum concurrent checks
            
        Returns:
            Bulk health check results
        """
        # Get integrations to check
        if user_id:
            integrations = self.integration_service.get_user_integrations(
                user_id, 
                status_filter=[IntegrationStatus.CONNECTED]
            )
        else:
            integrations = self.db.query(Integration).filter(
                Integration.status == IntegrationStatus.CONNECTED
            ).all()
        
        if not integrations:
            return {"total": 0, "success": 0, "failed": 0, "checks_performed": 0}
        
        check_types = check_types or [HealthCheckType.TOKEN_VALIDITY, HealthCheckType.API_CONNECTIVITY]
        
        logger.info(f"Starting bulk health check for {len(integrations)} integrations")
        
        results = {
            "total": len(integrations),
            "success": 0,
            "failed": 0,
            "checks_performed": 0,
            "by_check_type": {}
        }
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def check_with_semaphore(integration, check_type):
            async with semaphore:
                try:
                    health_check = await self.perform_health_check(integration.id, check_type)
                    results["checks_performed"] += 1
                    
                    if health_check.success:
                        results["success"] += 1
                    else:
                        results["failed"] += 1
                    
                    # Track by check type
                    if check_type.value not in results["by_check_type"]:
                        results["by_check_type"][check_type.value] = {"success": 0, "failed": 0}
                    
                    if health_check.success:
                        results["by_check_type"][check_type.value]["success"] += 1
                    else:
                        results["by_check_type"][check_type.value]["failed"] += 1
                    
                    return health_check
                except Exception as e:
                    logger.error(f"Health check failed for integration {integration.id}: {e}")
                    results["failed"] += 1
                    return None
        
        # Create tasks for all integration/check_type combinations
        tasks = []
        for integration in integrations:
            for check_type in check_types:
                tasks.append(check_with_semaphore(integration, check_type))
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info(f"Bulk health check completed: {results}")
        return results
    
    # Analytics and Reporting Methods
    
    def get_integration_status_dashboard(self, user_id: UUID) -> Dict[str, Any]:
        """
        Get comprehensive status dashboard for user's integrations.
        
        Args:
            user_id: User ID
            
        Returns:
            Dashboard data dictionary
        """
        # Get user integrations
        integrations = self.integration_service.get_user_integrations(user_id)
        
        # Get active alerts
        active_alerts = self.get_active_alerts(user_id=user_id)
        
        # Get recent events (last 24 hours)
        recent_events = self.get_user_events(
            user_id=user_id,
            limit=50
        )
        
        # Calculate health distribution
        health_distribution = {"healthy": 0, "warning": 0, "critical": 0, "unknown": 0}
        for integration in integrations:
            health = self.integration_service.get_integration_health(integration.id)
            health_distribution[health.value] += 1
        
        # Calculate alert distribution
        alert_distribution = {"critical": 0, "error": 0, "warning": 0, "info": 0}
        for alert in active_alerts:
            alert_distribution[alert.severity] += 1
        
        # Get sync performance metrics
        sync_metrics = self._calculate_sync_metrics(integrations)
        
        # Get uptime metrics
        uptime_metrics = self._calculate_uptime_metrics(integrations)
        
        return {
            "summary": {
                "total_integrations": len(integrations),
                "active_integrations": len([i for i in integrations if i.status == "connected"]),
                "total_alerts": len(active_alerts),
                "critical_alerts": alert_distribution["critical"],
                "health_score": self._calculate_health_score(health_distribution)
            },
            "health_distribution": health_distribution,
            "alert_distribution": alert_distribution,
            "sync_metrics": sync_metrics,
            "uptime_metrics": uptime_metrics,
            "recent_events": [event.to_dict() for event in recent_events[:10]],
            "active_alerts": [alert.to_dict() for alert in active_alerts[:10]],
            "integrations": [
                {
                    "id": str(integration.id),
                    "platform": integration.platform,
                    "status": integration.status,
                    "health": self.integration_service.get_integration_health(integration.id).value,
                    "last_sync": integration.last_successful_sync_at.isoformat() if integration.last_successful_sync_at else None,
                    "error_count": integration.error_count or 0
                }
                for integration in integrations
            ]
        }
    
    def get_integration_analytics(
        self,
        integration_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get detailed analytics for an integration."""
        integration = self.integration_service.get_integration(integration_id)
        if not integration:
            raise AIRException(f"Integration {integration_id} not found")
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get events in time period
        events = self.db.query(IntegrationStatusEvent).filter(
            and_(
                IntegrationStatusEvent.integration_id == integration_id,
                IntegrationStatusEvent.created_at >= cutoff_date
            )
        ).all()
        
        # Get health checks in time period
        health_checks = self.db.query(IntegrationHealthCheck).filter(
            and_(
                IntegrationHealthCheck.integration_id == integration_id,
                IntegrationHealthCheck.created_at >= cutoff_date
            )
        ).all()
        
        # Get alerts in time period
        alerts = self.db.query(IntegrationAlert).filter(
            and_(
                IntegrationAlert.integration_id == integration_id,
                IntegrationAlert.created_at >= cutoff_date
            )
        ).all()
        
        # Calculate metrics
        event_counts = {}
        for event in events:
            event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1
        
        health_check_success_rate = 0
        if health_checks:
            successful_checks = len([hc for hc in health_checks if hc.success])
            health_check_success_rate = (successful_checks / len(health_checks)) * 100
        
        avg_response_time = 0
        if health_checks:
            response_times = [hc.response_time_ms for hc in health_checks if hc.response_time_ms]
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
        
        return {
            "integration_id": str(integration_id),
            "period_days": days,
            "metrics": {
                "total_events": len(events),
                "total_health_checks": len(health_checks),
                "total_alerts": len(alerts),
                "health_check_success_rate": round(health_check_success_rate, 2),
                "average_response_time_ms": round(avg_response_time, 2),
                "sync_count": integration.total_syncs or 0,
                "items_synced": integration.total_items_synced or 0,
                "error_count": integration.error_count or 0
            },
            "event_distribution": event_counts,
            "recent_events": [event.to_dict() for event in events[-10:]],
            "recent_health_checks": [hc.to_dict() for hc in health_checks[-10:]],
            "recent_alerts": [alert.to_dict() for alert in alerts[-5:]]
        }
    
    # Private Helper Methods
    
    def _calculate_sync_metrics(self, integrations: List[Integration]) -> Dict[str, Any]:
        """Calculate sync performance metrics."""
        total_syncs = sum(i.total_syncs or 0 for i in integrations)
        total_items = sum(i.total_items_synced or 0 for i in integrations)
        
        # Calculate average sync duration
        durations = [i.last_sync_duration_seconds for i in integrations if i.last_sync_duration_seconds]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            "total_syncs": total_syncs,
            "total_items_synced": total_items,
            "average_sync_duration_seconds": round(avg_duration, 2),
            "integrations_with_recent_sync": len([
                i for i in integrations 
                if i.last_successful_sync_at and 
                (datetime.utcnow() - i.last_successful_sync_at).total_seconds() < 86400  # 24 hours
            ])
        }
    
    def _calculate_uptime_metrics(self, integrations: List[Integration]) -> Dict[str, Any]:
        """Calculate uptime metrics."""
        connected_count = len([i for i in integrations if i.status == "connected"])
        total_count = len(integrations)
        
        uptime_percentage = (connected_count / total_count * 100) if total_count > 0 else 0
        
        return {
            "uptime_percentage": round(uptime_percentage, 2),
            "connected_integrations": connected_count,
            "total_integrations": total_count,
            "disconnected_integrations": total_count - connected_count
        }
    
    def _calculate_health_score(self, health_distribution: Dict[str, int]) -> float:
        """Calculate overall health score (0-100)."""
        total = sum(health_distribution.values())
        if total == 0:
            return 100.0
        
        # Weight the health statuses
        score = (
            health_distribution["healthy"] * 100 +
            health_distribution["warning"] * 70 +
            health_distribution["critical"] * 20 +
            health_distribution["unknown"] * 50
        ) / total
        
        return round(score, 1) 