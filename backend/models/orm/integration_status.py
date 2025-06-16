"""Integration status tracking models for monitoring integration health and events."""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Integer, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from enum import Enum

from .base import BaseModel


class IntegrationEventType(str, Enum):
    """Types of integration events to track."""
    CREATED = "created"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    TOKEN_REFRESHED = "token_refreshed"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_REVOKED = "token_revoked"
    SYNC_STARTED = "sync_started"
    SYNC_COMPLETED = "sync_completed"
    SYNC_FAILED = "sync_failed"
    ERROR_OCCURRED = "error_occurred"
    ERROR_RESOLVED = "error_resolved"
    RATE_LIMITED = "rate_limited"
    SETTINGS_UPDATED = "settings_updated"
    FEATURE_ENABLED = "feature_enabled"
    FEATURE_DISABLED = "feature_disabled"
    HEALTH_CHECK_FAILED = "health_check_failed"
    HEALTH_CHECK_PASSED = "health_check_passed"


class IntegrationSeverity(str, Enum):
    """Severity levels for integration events."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class IntegrationStatusEvent(BaseModel):
    """Model for tracking integration status changes and events."""
    
    __tablename__ = "integration_status_events"
    
    # Foreign key to integration
    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Event details
    event_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    message = Column(Text, nullable=False)
    details = Column(JSONB, default=dict)  # Additional event-specific data
    
    # Status tracking
    previous_status = Column(String(20))  # Status before this event
    new_status = Column(String(20))  # Status after this event
    
    # Context information
    user_agent = Column(String(255))  # If triggered by user action
    ip_address = Column(String(45))  # If triggered by user action
    source = Column(String(50), default="system")  # 'system', 'user', 'api', 'worker'
    
    # Metrics
    duration_ms = Column(Integer)  # Duration of operation that triggered event
    items_affected = Column(Integer)  # Number of items affected (e.g., synced)
    
    # Resolution tracking
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    resolution_message = Column(Text)
    
    # Relationships
    # integration = relationship("Integration", back_populates="status_events")
    
    def __init__(self, **kwargs):
        """Initialize status event with proper defaults."""
        super().__init__(**kwargs)
    
    def mark_resolved(self, resolution_message: str) -> None:
        """Mark this event as resolved."""
        self.resolved = True
        self.resolved_at = datetime.utcnow()
        self.resolution_message = resolution_message
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "integration_id": str(self.integration_id),
            "event_type": self.event_type,
            "severity": self.severity,
            "message": self.message,
            "details": self.details,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "source": self.source,
            "duration_ms": self.duration_ms,
            "items_affected": self.items_affected,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_message": self.resolution_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self) -> str:
        return f"<IntegrationStatusEvent(id={self.id}, integration_id={self.integration_id}, event_type={self.event_type}, severity={self.severity})>"


class IntegrationHealthCheck(BaseModel):
    """Model for tracking integration health check results."""
    
    __tablename__ = "integration_health_checks"
    
    # Foreign key to integration
    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Health check details
    check_type = Column(String(50), nullable=False)  # 'token_validity', 'api_connectivity', 'sync_performance'
    status = Column(String(20), nullable=False, index=True)  # 'healthy', 'warning', 'critical', 'unknown'
    
    # Results
    response_time_ms = Column(Integer)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text)
    details = Column(JSONB, default=dict)
    
    # Metrics
    check_duration_ms = Column(Integer)
    
    # Relationships
    # integration = relationship("Integration", back_populates="health_checks")
    
    def __init__(self, **kwargs):
        """Initialize health check with proper defaults."""
        super().__init__(**kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "integration_id": str(self.integration_id),
            "check_type": self.check_type,
            "status": self.status,
            "response_time_ms": self.response_time_ms,
            "success": self.success,
            "error_message": self.error_message,
            "details": self.details,
            "check_duration_ms": self.check_duration_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self) -> str:
        return f"<IntegrationHealthCheck(id={self.id}, integration_id={self.integration_id}, check_type={self.check_type}, status={self.status})>"


class IntegrationAlert(BaseModel):
    """Model for integration alerts and notifications."""
    
    __tablename__ = "integration_alerts"
    
    # Foreign key to integration
    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Alert details
    alert_type = Column(String(50), nullable=False, index=True)  # 'token_expiring', 'sync_failing', 'rate_limited'
    severity = Column(String(20), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    details = Column(JSONB, default=dict)
    
    # Alert state
    status = Column(String(20), default="active", index=True)  # 'active', 'acknowledged', 'resolved', 'suppressed'
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime)
    acknowledged_by = Column(String(255))  # User who acknowledged
    
    # Resolution
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    resolution_message = Column(Text)
    auto_resolved = Column(Boolean, default=False)
    
    # Notification tracking
    notification_sent = Column(Boolean, default=False)
    notification_sent_at = Column(DateTime)
    notification_channels = Column(JSONB, default=list)  # ['email', 'webhook', 'slack']
    
    # Suppression
    suppressed_until = Column(DateTime)
    suppression_reason = Column(Text)
    
    # Relationships
    # integration = relationship("Integration", back_populates="alerts")
    
    def __init__(self, **kwargs):
        """Initialize alert with proper defaults."""
        super().__init__(**kwargs)
    
    def acknowledge(self, acknowledged_by: str) -> None:
        """Acknowledge this alert."""
        self.acknowledged = True
        self.acknowledged_at = datetime.utcnow()
        self.acknowledged_by = acknowledged_by
        self.status = "acknowledged"
        self.updated_at = datetime.utcnow()
    
    def resolve(self, resolution_message: str, auto_resolved: bool = False) -> None:
        """Resolve this alert."""
        self.resolved = True
        self.resolved_at = datetime.utcnow()
        self.resolution_message = resolution_message
        self.auto_resolved = auto_resolved
        self.status = "resolved"
        self.updated_at = datetime.utcnow()
    
    def suppress(self, until: datetime, reason: str) -> None:
        """Suppress this alert until a specific time."""
        self.suppressed_until = until
        self.suppression_reason = reason
        self.status = "suppressed"
        self.updated_at = datetime.utcnow()
    
    def is_active(self) -> bool:
        """Check if alert is currently active."""
        if self.resolved or self.status == "resolved":
            return False
        
        if self.suppressed_until and datetime.utcnow() < self.suppressed_until:
            return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "integration_id": str(self.integration_id),
            "alert_type": self.alert_type,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "details": self.details,
            "status": self.status,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_message": self.resolution_message,
            "auto_resolved": self.auto_resolved,
            "notification_sent": self.notification_sent,
            "notification_sent_at": self.notification_sent_at.isoformat() if self.notification_sent_at else None,
            "notification_channels": self.notification_channels,
            "suppressed_until": self.suppressed_until.isoformat() if self.suppressed_until else None,
            "suppression_reason": self.suppression_reason,
            "is_active": self.is_active(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self) -> str:
        return f"<IntegrationAlert(id={self.id}, integration_id={self.integration_id}, alert_type={self.alert_type}, severity={self.severity}, status={self.status})>" 