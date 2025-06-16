"""
Integration Status API Routes

This module provides REST API endpoints for checking and managing
integration statuses across different services (Gmail, Calendar, etc.)
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import logging

from lib.database import get_db
from services.integration_status_service import IntegrationStatusService, AlertType, HealthCheckType
from models.orm.user import User
from services.auth import get_current_user
from models.orm.integration_status import IntegrationEventType, IntegrationSeverity

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Integration Status"])


# Request/Response Models

class EventLogRequest(BaseModel):
    """Request model for logging integration events."""
    integration_id: UUID
    event_type: IntegrationEventType
    severity: IntegrationSeverity
    message: str
    details: Optional[Dict[str, Any]] = None
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    source: str = "api"
    duration_ms: Optional[int] = None
    items_affected: Optional[int] = None


class HealthCheckRequest(BaseModel):
    """Request model for performing health checks."""
    integration_id: UUID
    check_type: HealthCheckType
    timeout_seconds: int = Field(default=30, ge=5, le=300)


class BulkHealthCheckRequest(BaseModel):
    """Request model for bulk health checks."""
    user_id: Optional[UUID] = None
    check_types: Optional[List[HealthCheckType]] = None
    max_concurrent: int = Field(default=10, ge=1, le=50)


class AlertAcknowledgeRequest(BaseModel):
    """Request model for acknowledging alerts."""
    acknowledged_by: str


class AlertResolveRequest(BaseModel):
    """Request model for resolving alerts."""
    resolution_message: str
    auto_resolved: bool = False


class EventResponse(BaseModel):
    """Response model for integration events."""
    id: str
    integration_id: str
    event_type: str
    severity: str
    message: str
    details: Dict[str, Any]
    previous_status: Optional[str]
    new_status: Optional[str]
    source: str
    duration_ms: Optional[int]
    items_affected: Optional[int]
    resolved: bool
    resolved_at: Optional[str]
    resolution_message: Optional[str]
    created_at: str
    updated_at: str


class HealthCheckResponse(BaseModel):
    """Response model for health checks."""
    id: str
    integration_id: str
    check_type: str
    status: str
    response_time_ms: Optional[int]
    success: bool
    error_message: Optional[str]
    details: Dict[str, Any]
    check_duration_ms: Optional[int]
    created_at: str


class AlertResponse(BaseModel):
    """Response model for alerts."""
    id: str
    integration_id: str
    alert_type: str
    severity: str
    title: str
    message: str
    details: Dict[str, Any]
    status: str
    acknowledged: bool
    acknowledged_at: Optional[str]
    acknowledged_by: Optional[str]
    resolved: bool
    resolved_at: Optional[str]
    resolution_message: Optional[str]
    auto_resolved: bool
    notification_sent: bool
    notification_sent_at: Optional[str]
    notification_channels: List[str]
    suppressed_until: Optional[str]
    suppression_reason: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str


# Event Tracking Endpoints

@router.post("/events", response_model=EventResponse)
async def log_integration_event(
    request: EventLogRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Log an integration status event."""
    service = IntegrationStatusService(db)
    
    event = service.log_event(
        integration_id=request.integration_id,
        event_type=request.event_type,
        severity=request.severity,
        message=request.message,
        details=request.details,
        previous_status=request.previous_status,
        new_status=request.new_status,
        source=request.source,
        duration_ms=request.duration_ms,
        items_affected=request.items_affected
    )
    
    return EventResponse(**event.to_dict())


@router.get("/events/integration/{integration_id}", response_model=List[EventResponse])
async def get_integration_events(
    integration_id: UUID,
    event_types: Optional[List[IntegrationEventType]] = Query(None),
    severity_filter: Optional[List[IntegrationSeverity]] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get events for a specific integration."""
    service = IntegrationStatusService(db)
    
    events = service.get_integration_events(
        integration_id=integration_id,
        event_types=event_types,
        severity_filter=severity_filter,
        limit=limit,
        offset=offset
    )
    
    return [EventResponse(**event.to_dict()) for event in events]


@router.get("/events/user", response_model=List[EventResponse])
async def get_user_events(
    event_types: Optional[List[IntegrationEventType]] = Query(None),
    severity_filter: Optional[List[IntegrationSeverity]] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get events for all user integrations."""
    service = IntegrationStatusService(db)
    
    events = service.get_user_events(
        user_id=current_user.id,
        event_types=event_types,
        severity_filter=severity_filter,
        limit=limit,
        offset=offset
    )
    
    return [EventResponse(**event.to_dict()) for event in events]


# Health Check Endpoints

@router.post("/health-check", response_model=HealthCheckResponse)
async def perform_health_check(
    request: HealthCheckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Perform a health check on an integration."""
    service = IntegrationStatusService(db)
    
    health_check = await service.perform_health_check(
        integration_id=request.integration_id,
        check_type=request.check_type,
        timeout_seconds=request.timeout_seconds
    )
    
    return HealthCheckResponse(**health_check.to_dict())


@router.post("/health-check/bulk")
async def bulk_health_check(
    request: BulkHealthCheckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Perform bulk health checks on integrations."""
    service = IntegrationStatusService(db)
    
    # Use current user if no user_id specified
    user_id = request.user_id or current_user.id
    
    results = await service.bulk_health_check(
        user_id=user_id,
        check_types=request.check_types,
        max_concurrent=request.max_concurrent
    )
    
    return results


@router.get("/health-check/integration/{integration_id}/history", response_model=List[HealthCheckResponse])
async def get_integration_health_history(
    integration_id: UUID,
    check_type: Optional[HealthCheckType] = Query(None),
    hours: int = Query(24, ge=1, le=168),  # Max 1 week
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get health check history for an integration."""
    service = IntegrationStatusService(db)
    
    health_checks = service.get_integration_health_history(
        integration_id=integration_id,
        check_type=check_type,
        hours=hours,
        limit=limit
    )
    
    return [HealthCheckResponse(**hc.to_dict()) for hc in health_checks]


# Alert Management Endpoints

@router.get("/alerts", response_model=List[AlertResponse])
async def get_active_alerts(
    integration_id: Optional[UUID] = Query(None),
    severity_filter: Optional[List[IntegrationSeverity]] = Query(None),
    alert_types: Optional[List[AlertType]] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get active alerts for user's integrations."""
    service = IntegrationStatusService(db)
    
    alerts = service.get_active_alerts(
        user_id=current_user.id,
        integration_id=integration_id,
        severity_filter=severity_filter,
        alert_types=alert_types
    )
    
    return [AlertResponse(**alert.to_dict()) for alert in alerts]


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: UUID,
    request: AlertAcknowledgeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Acknowledge an alert."""
    service = IntegrationStatusService(db)
    
    try:
        alert = service.acknowledge_alert(alert_id, request.acknowledged_by)
        return AlertResponse(**alert.to_dict())
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/alerts/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: UUID,
    request: AlertResolveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resolve an alert."""
    service = IntegrationStatusService(db)
    
    try:
        alert = service.resolve_alert(
            alert_id=alert_id,
            resolution_message=request.resolution_message,
            auto_resolved=request.auto_resolved
        )
        return AlertResponse(**alert.to_dict())
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# Dashboard and Analytics Endpoints

@router.get("/dashboard")
async def get_integration_status_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive integration status dashboard."""
    service = IntegrationStatusService(db)
    
    dashboard = service.get_integration_status_dashboard(current_user.id)
    return dashboard


@router.get("/analytics/integration/{integration_id}")
async def get_integration_analytics(
    integration_id: UUID,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed analytics for an integration."""
    service = IntegrationStatusService(db)
    
    try:
        analytics = service.get_integration_analytics(
            integration_id=integration_id,
            days=days
        )
        return analytics
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# System Health Endpoints

@router.get("/system/health")
async def get_system_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get overall system health status."""
    service = IntegrationStatusService(db)
    
    # Get dashboard for current user
    dashboard = service.get_integration_status_dashboard(current_user.id)
    
    # Extract key health metrics
    health_summary = {
        "status": "healthy" if dashboard["summary"]["health_score"] >= 80 else 
                 "warning" if dashboard["summary"]["health_score"] >= 60 else "critical",
        "health_score": dashboard["summary"]["health_score"],
        "total_integrations": dashboard["summary"]["total_integrations"],
        "active_integrations": dashboard["summary"]["active_integrations"],
        "critical_alerts": dashboard["summary"]["critical_alerts"],
        "uptime_percentage": dashboard["uptime_metrics"]["uptime_percentage"],
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return health_summary


@router.get("/system/metrics")
async def get_system_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed system metrics."""
    service = IntegrationStatusService(db)
    
    dashboard = service.get_integration_status_dashboard(current_user.id)
    
    return {
        "health_distribution": dashboard["health_distribution"],
        "alert_distribution": dashboard["alert_distribution"],
        "sync_metrics": dashboard["sync_metrics"],
        "uptime_metrics": dashboard["uptime_metrics"],
        "timestamp": datetime.utcnow().isoformat()
    } 