"""
API routes for interaction timeline - Simplified

This module provides REST endpoints for Task 3.2.3: Build interaction timeline assembly
with source prioritization. Refactored to focus on actionable relationship management
through days since last interaction tracking.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from lib.database import get_db
from services.auth import get_current_user
from models.orm.user import User
from services.interaction_timeline_service import InteractionTimelineService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["interaction-timeline"])


# Response Models
class ContactLastInteractionResponse(BaseModel):
    """Response model for contact with last interaction details"""
    contact_id: str
    contact_name: str
    contact_email: str
    company: Optional[str]
    days_since_last_interaction: int
    last_interaction_date: datetime
    last_interaction_type: str
    last_interaction_subject: Optional[str]
    relationship_strength: float
    total_interactions: int
    needs_attention: bool


class AttentionDashboardResponse(BaseModel):
    """Response model for attention dashboard"""
    user_id: str
    total_contacts: int
    active_contacts: int
    dormant_contacts: int
    needs_immediate_attention: List[Dict[str, Any]]
    needs_attention_soon: List[Dict[str, Any]]
    going_cold: List[Dict[str, Any]]
    summary: Dict[str, Any]
    generated_at: str


@router.get(
    "/contacts",
    response_model=List[ContactLastInteractionResponse],
    summary="Get contacts by last interaction",
    description="Get all contacts sorted by days since last interaction - the core relationship management view"
)
async def get_contacts_by_last_interaction(
    limit: Optional[int] = Query(None, description="Maximum number of contacts to return"),
    needs_attention_only: bool = Query(False, description="Only return contacts that need attention"),
    min_relationship_strength: float = Query(0.0, description="Minimum relationship strength filter", ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get contacts sorted by days since last interaction
    
    This is the core endpoint for relationship management - it shows you exactly
    who you haven't talked to in a while and need to reach out to.
    
    **Key Features:**
    - Sorted by days since last interaction (oldest first)
    - Shows relationship strength to prioritize outreach
    - Indicates which contacts need attention
    - Simple, actionable data format
    
    **Perfect for:**
    - Daily relationship review
    - Identifying who to reach out to
    - Preventing relationships from going cold
    """
    try:
        timeline_service = InteractionTimelineService(db)
        
        contacts = await timeline_service.get_contacts_by_last_interaction(
            user_id=str(current_user.id),
            limit=limit,
            needs_attention_only=needs_attention_only,
            min_relationship_strength=min_relationship_strength
        )
        
        return [ContactLastInteractionResponse(**contact.__dict__) for contact in contacts]
        
    except Exception as e:
        logger.error(f"Failed to get contacts by last interaction for {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get contacts")


@router.get(
    "/dashboard",
    response_model=AttentionDashboardResponse,
    summary="Get attention dashboard",
    description="Get dashboard showing contacts that need immediate attention, going cold, etc."
)
async def get_attention_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get attention dashboard for relationship management
    
    This endpoint provides a high-level view of your relationship health:
    - Contacts needing immediate attention (strong relationships going quiet)
    - Contacts needing attention soon (approaching thresholds)
    - Contacts going cold (90+ days since contact)
    
    **Perfect for:**
    - Daily relationship health check
    - Weekly relationship planning
    - Identifying relationship risks
    """
    try:
        timeline_service = InteractionTimelineService(db)
        
        dashboard = await timeline_service.get_attention_dashboard(
            user_id=str(current_user.id)
        )
        
        return AttentionDashboardResponse(**dashboard)
        
    except Exception as e:
        logger.error(f"Failed to get attention dashboard for {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get attention dashboard")


@router.get(
    "/needs-attention",
    response_model=List[ContactLastInteractionResponse],
    summary="Get contacts that need attention",
    description="Get only contacts that need attention based on relationship strength and days since last contact"
)
async def get_contacts_needing_attention(
    limit: Optional[int] = Query(10, description="Maximum number of contacts to return"),
    min_relationship_strength: float = Query(0.3, description="Minimum relationship strength", ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get contacts that need attention
    
    This is a filtered view showing only contacts that have gone too long
    without interaction based on their relationship strength:
    - Strong relationships (0.7+): 14+ days
    - Medium relationships (0.4-0.7): 30+ days  
    - Weak relationships (0.0-0.4): 90+ days
    
    **Perfect for:**
    - Action-oriented relationship management
    - Daily "who to contact" list
    - Preventing important relationships from going cold
    """
    try:
        timeline_service = InteractionTimelineService(db)
        
        contacts = await timeline_service.get_contacts_by_last_interaction(
            user_id=str(current_user.id),
            limit=limit,
            needs_attention_only=True,
            min_relationship_strength=min_relationship_strength
        )
        
        return [ContactLastInteractionResponse(**contact.__dict__) for contact in contacts]
        
    except Exception as e:
        logger.error(f"Failed to get contacts needing attention for {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get contacts needing attention")


@router.get(
    "/stats",
    summary="Get interaction statistics",
    description="Get basic interaction statistics for the user"
)
async def get_interaction_statistics(
    days_back: int = Query(30, description="Number of days to analyze", ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get interaction statistics
    
    Simple statistics about your interaction patterns:
    - Total interactions in period
    - Daily average
    - Breakdown by type and source
    - Number of active contacts
    """
    try:
        # Simple statistics calculation
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        
        from models.orm.interaction import Interaction
        interactions = db.query(Interaction).filter(
            Interaction.user_id == current_user.id,
            Interaction.interaction_date >= cutoff_date
        ).all()
        
        if not interactions:
            return {
                "period_days": days_back,
                "total_interactions": 0,
                "daily_average": 0.0,
                "by_type": {},
                "by_source": {},
                "active_contacts": 0,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
        
        # Calculate statistics
        total_interactions = len(interactions)
        daily_average = total_interactions / days_back
        
        by_type = {}
        by_source = {}
        contact_ids = set()
        
        for interaction in interactions:
            # By type
            interaction_type = interaction.interaction_type
            by_type[interaction_type] = by_type.get(interaction_type, 0) + 1
            
            # By source
            source = interaction.source_platform or 'unknown'
            by_source[source] = by_source.get(source, 0) + 1
            
            # Track unique contacts
            contact_ids.add(str(interaction.contact_id))
        
        return {
            "period_days": days_back,
            "total_interactions": total_interactions,
            "daily_average": round(daily_average, 2),
            "by_type": by_type,
            "by_source": by_source,
            "active_contacts": len(contact_ids),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get interaction statistics for {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get interaction statistics")


@router.get(
    "/health",
    summary="Timeline service health check",
    description="Check the health of the simplified timeline service"
)
async def timeline_health_check(
    db: Session = Depends(get_db)
):
    """
    Health check for the timeline service
    
    Verifies that the simplified timeline service is operational.
    """
    try:
        # Test database connectivity
        from models.orm.interaction import Interaction
        interaction_count = db.query(Interaction).count()
        
        return {
            "status": "healthy",
            "service": "interaction_timeline_simplified",
            "database_accessible": True,
            "total_interactions": interaction_count,
            "features": [
                "days_since_last_interaction",
                "attention_dashboard", 
                "contact_prioritization",
                "relationship_health_tracking"
            ],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Timeline service health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "interaction_timeline_simplified",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        } 