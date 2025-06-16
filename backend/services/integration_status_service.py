"""Integration status tracking service for comprehensive monitoring and alerting."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func, text

from lib.logger import logger
from lib.exceptions import AIRException
from models.orm.integration import Integration
from models.orm.integration_status import (
    IntegrationStatusEvent, IntegrationHealthCheck, IntegrationAlert,
    IntegrationEventType, IntegrationSeverity
)
from .integration_service import IntegrationService, IntegrationHealth, IntegrationStatus


class AlertType(str, Enum):
    """Types of alerts that can be generated."""
    TOKEN_EXPIRING = "token_expiring"
    TOKEN_EXPIRED = "token_expired"
    SYNC_FAILING = "sync_failing"
    RATE_LIMITED = "rate_limited"
    HIGH_ERROR_RATE = "high_error_rate"
    CONNECTIVITY_ISSUES = "connectivity_issues"
    PERFORMANCE_DEGRADED = "performance_degraded"
    QUOTA_EXCEEDED = "quota_exceeded"
    UNAUTHORIZED_ACCESS = "unauthorized_access"


class HealthCheckType(str, Enum):
    """Types of health checks that can be performed."""
    TOKEN_VALIDITY = "token_validity"
    API_CONNECTIVITY = "api_connectivity"
    SYNC_PERFORMANCE = "sync_performance"
    RATE_LIMIT_STATUS = "rate_limit_status"
    QUOTA_USAGE = "quota_usage"


class IntegrationStatusService:
    """Service for comprehensive integration status tracking and monitoring."""
    
    def __init__(self, db: Session):
        self.db = db
        self.integration_service = IntegrationService(db)
    
    # Event Tracking Methods
    
    def log_event(
        self,
        integration_id: UUID,
        event_type,  # Can be IntegrationEventType or str
        severity,    # Can be IntegrationSeverity or str
        message: str,
        details: Optional[Dict[str, Any]] = None,
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None,
        source: str = "system",
        duration_ms: Optional[int] = None,
        items_affected: Optional[int] = None
    ) -> IntegrationStatusEvent:
        """
        Log an integration status event.
        
        Args:
            integration_id: Integration ID
            event_type: Type of event (enum or string)
            severity: Event severity (enum or string)
            message: Human-readable message
            details: Additional event details
            previous_status: Status before event
            new_status: Status after event
            source: Event source
            duration_ms: Operation duration
            items_affected: Number of items affected
            
        Returns:
            Created IntegrationStatusEvent
        """
        # Handle both enum and string values
        event_type_value = event_type.value if hasattr(event_type, "value") else event_type if hasattr(event_type, 'value') else event_type
        severity_value = severity.value if hasattr(severity, "value") else severity if hasattr(severity, 'value') else severity
        
        event = IntegrationStatusEvent(
            integration_id=integration_id,
            event_type=event_type_value,
            severity=severity_value,
            message=message,
            details=details or {},
            previous_status=previous_status,
            new_status=new_status,
            source=source,
            duration_ms=duration_ms,
            items_affected=items_affected
        )
        
        self.db.add(event)
        self.db.commit()
        
        logger.info(f"Logged event {event_type_value} for integration {integration_id}: {message}")
        
        # Check if this event should trigger an alert
        self._check_for_alert_triggers(integration_id, event)
        
        return event
    
    def get_integration_events(
        self,
        integration_id: UUID,
        event_types: Optional[List[IntegrationEventType]] = None,
        severity_filter: Optional[List[IntegrationSeverity]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[IntegrationStatusEvent]:
        """Get events for an integration with optional filters."""
        query = self.db.query(IntegrationStatusEvent).filter(
            IntegrationStatusEvent.integration_id == integration_id
        )
        
        if event_types:
            query = query.filter(IntegrationStatusEvent.event_type.in_([e.value for e in event_types]))
        
        if severity_filter:
            query = query.filter(IntegrationStatusEvent.severity.in_([s.value for s in severity_filter]))
        
        return query.order_by(desc(IntegrationStatusEvent.created_at)).offset(offset).limit(limit).all()
    
    def get_user_events(
        self,
        user_id: UUID,
        event_types: Optional[List[IntegrationEventType]] = None,
        severity_filter: Optional[List[IntegrationSeverity]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[IntegrationStatusEvent]:
        """Get events for all user integrations."""
        query = self.db.query(IntegrationStatusEvent).join(Integration).filter(
            Integration.user_id == user_id
        )
        
        if event_types:
            query = query.filter(IntegrationStatusEvent.event_type.in_([e.value for e in event_types]))
        
        if severity_filter:
            query = query.filter(IntegrationStatusEvent.severity.in_([s.value for s in severity_filter]))
        
        return query.order_by(desc(IntegrationStatusEvent.created_at)).offset(offset).limit(limit).all()
    
    # Health Check Methods
    
    async def perform_health_check(
        self,
        integration_id: UUID,
        check_type: HealthCheckType,
        timeout_seconds: int = 30
    ) -> IntegrationHealthCheck:
        """
        Perform a health check on an integration.
        
        Args:
            integration_id: Integration ID
            check_type: Type of health check
            timeout_seconds: Timeout for the check
            
        Returns:
            IntegrationHealthCheck result
        """
        integration = self.integration_service.get_integration(integration_id)
        if not integration:
            raise AIRException(f"Integration {integration_id} not found")
        
        start_time = datetime.utcnow()
        
        try:
            # Perform the actual health check based on type
            result = await self._execute_health_check(integration, check_type, timeout_seconds)
            
            check_duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            health_check = IntegrationHealthCheck(
                integration_id=integration_id,
                check_type=check_type.value,
                status=result["status"],
                response_time_ms=result.get("response_time_ms"),
                success=result["success"],
                error_message=result.get("error_message"),
                details=result.get("details", {}),
                check_duration_ms=check_duration
            )
            
            self.db.add(health_check)
            self.db.commit()
            
            # Log the health check event
            severity = IntegrationSeverity.INFO if result["success"] else IntegrationSeverity.WARNING
            self.log_event(
                integration_id=integration_id,
                event_type=IntegrationEventType.HEALTH_CHECK_PASSED if result["success"] else IntegrationEventType.HEALTH_CHECK_FAILED,
                severity=severity,
                message=f"Health check {check_type.value} {'passed' if result['success'] else 'failed'}",
                details={"check_type": check_type.value, "duration_ms": check_duration},
                duration_ms=check_duration
            )
            
            return health_check
            
        except Exception as e:
            check_duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            error_message = str(e)
            
            health_check = IntegrationHealthCheck(
                integration_id=integration_id,
                check_type=check_type.value,
                status="critical",
                success=False,
                error_message=error_message,
                check_duration_ms=check_duration
            )
            
            self.db.add(health_check)
            self.db.commit()
            
            # Log the failed health check
            self.log_event(
                integration_id=integration_id,
                event_type=IntegrationEventType.HEALTH_CHECK_FAILED,
                severity=IntegrationSeverity.ERROR,
                message=f"Health check {check_type.value} failed: {error_message}",
                details={"check_type": check_type.value, "error": error_message},
                duration_ms=check_duration
            )
            
            return health_check
    
    def get_integration_health_history(
        self,
        integration_id: UUID,
        check_type: Optional[HealthCheckType] = None,
        hours: int = 24,
        limit: int = 100
    ) -> List[IntegrationHealthCheck]:
        """Get health check history for an integration."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = self.db.query(IntegrationHealthCheck).filter(
            and_(
                IntegrationHealthCheck.integration_id == integration_id,
                IntegrationHealthCheck.created_at >= cutoff_time
            )
        )
        
        if check_type:
            query = query.filter(IntegrationHealthCheck.check_type == check_type.value)
        
        return query.order_by(desc(IntegrationHealthCheck.created_at)).limit(limit).all()
    
    # Private Helper Methods
    
    async def _execute_health_check(
        self,
        integration: Integration,
        check_type: HealthCheckType,
        timeout_seconds: int
    ) -> Dict[str, Any]:
        """Execute a specific type of health check."""
        start_time = datetime.utcnow()
        
        try:
            if check_type == HealthCheckType.TOKEN_VALIDITY:
                # Check if token is valid and not expired
                is_expired = integration.is_token_expired()
                is_expiring_soon = integration.is_token_expiring_soon(buffer_minutes=60)
                
                if is_expired:
                    return {
                        "success": False,
                        "status": "critical",
                        "error_message": "Token is expired",
                        "details": {"expired": True}
                    }
                elif is_expiring_soon:
                    return {
                        "success": True,
                        "status": "warning",
                        "details": {"expiring_soon": True}
                    }
                else:
                    return {
                        "success": True,
                        "status": "healthy",
                        "details": {"token_valid": True}
                    }
            
            elif check_type == HealthCheckType.API_CONNECTIVITY:
                # TODO: Implement actual API connectivity check
                # This would make a simple API call to verify connectivity
                await asyncio.sleep(0.1)  # Simulate API call
                response_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                
                return {
                    "success": True,
                    "status": "healthy",
                    "response_time_ms": response_time,
                    "details": {"connectivity": "ok"}
                }
            
            elif check_type == HealthCheckType.SYNC_PERFORMANCE:
                # Check sync performance metrics
                if integration.last_sync_duration_seconds:
                    if integration.last_sync_duration_seconds > 300:  # 5 minutes
                        return {
                            "success": True,
                            "status": "warning",
                            "details": {"slow_sync": True, "duration": integration.last_sync_duration_seconds}
                        }
                
                return {
                    "success": True,
                    "status": "healthy",
                    "details": {"performance": "good"}
                }
            
            else:
                return {
                    "success": False,
                    "status": "unknown",
                    "error_message": f"Unknown check type: {check_type.value}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "status": "critical",
                "error_message": str(e),
                "details": {"exception": str(e)}
            }
    
    def _check_for_alert_triggers(self, integration_id: UUID, event: IntegrationStatusEvent) -> None:
        """Check if an event should trigger an alert."""
        try:
            # Token expiring alert
            if event.event_type == IntegrationEventType.TOKEN_EXPIRED.value:
                self.create_alert(
                    integration_id=integration_id,
                    alert_type=AlertType.TOKEN_EXPIRED,
                    severity=IntegrationSeverity.CRITICAL,
                    title="Token Expired",
                    message="OAuth token has expired and needs to be refreshed",
                    details={"event_id": str(event.id)}
                )
            
            # Sync failing alert
            elif event.event_type == IntegrationEventType.SYNC_FAILED.value:
                # Check if multiple sync failures in short period
                recent_failures = self.db.query(IntegrationStatusEvent).filter(
                    and_(
                        IntegrationStatusEvent.integration_id == integration_id,
                        IntegrationStatusEvent.event_type == IntegrationEventType.SYNC_FAILED.value,
                        IntegrationStatusEvent.created_at >= datetime.utcnow() - timedelta(hours=1)
                    )
                ).count()
                
                if recent_failures >= 3:
                    self.create_alert(
                        integration_id=integration_id,
                        alert_type=AlertType.SYNC_FAILING,
                        severity=IntegrationSeverity.ERROR,
                        title="Repeated Sync Failures",
                        message=f"Integration has failed to sync {recent_failures} times in the last hour",
                        details={"failure_count": recent_failures, "event_id": str(event.id)}
                    )
            
            # Rate limiting alert
            elif event.event_type == IntegrationEventType.RATE_LIMITED.value:
                self.create_alert(
                    integration_id=integration_id,
                    alert_type=AlertType.RATE_LIMITED,
                    severity=IntegrationSeverity.WARNING,
                    title="Rate Limited",
                    message="Integration is being rate limited by the provider",
                    details={"event_id": str(event.id)}
                )
            
        except Exception as e:
            logger.error(f"Error checking alert triggers for integration {integration_id}: {e}")
    
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
            severity=severity.value if hasattr(severity, "value") else severity,
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