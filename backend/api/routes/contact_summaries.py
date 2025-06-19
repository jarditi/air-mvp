"""
Contact Summaries API Routes

This module provides REST API endpoints for AI-powered contact summarization,
enabling users to generate comprehensive summaries, pre-meeting briefings,
and relationship insights.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from lib.database import get_db
from services.auth import get_current_user
from services.contact_summarization import ContactSummarizationService, ContactSummarizationError, SummaryType
from models.orm.user import User

router = APIRouter()


# Request/Response Models

class SummaryGenerateRequest(BaseModel):
    """Request model for generating contact summaries."""
    summary_type: str = Field(SummaryType.COMPREHENSIVE, description="Type of summary to generate")
    meeting_context: Optional[str] = Field(None, description="Context for pre-meeting summaries")
    force_refresh: bool = Field(False, description="Skip cache and generate fresh summary")


class PreMeetingSummaryRequest(BaseModel):
    """Request model for pre-meeting summary generation."""
    meeting_context: str = Field(..., description="Context about the upcoming meeting")
    meeting_date: Optional[datetime] = Field(None, description="Date/time of the meeting")


class BatchSummaryRequest(BaseModel):
    """Request model for batch summary generation."""
    contact_ids: List[UUID] = Field(..., description="List of contact IDs to summarize")
    summary_type: str = Field(SummaryType.BRIEF, description="Type of summary to generate")
    max_contacts: int = Field(50, ge=1, le=100, description="Maximum number of contacts to process")


class ContactSummaryResponse(BaseModel):
    """Response model for contact summaries."""
    contact_id: str
    contact_name: str
    contact_email: str
    summary_type: str
    summary: str
    talking_points: List[str]
    relationship_insights: dict
    last_interaction: Optional[str]
    interaction_count: int
    relationship_strength: float
    generated_at: str
    expires_at: str
    cached: bool
    model_used: str
    token_usage: Optional[dict]


class PreMeetingSummaryResponse(ContactSummaryResponse):
    """Response model for pre-meeting summaries."""
    meeting_context: str
    meeting_date: Optional[str]


class BatchSummaryResponse(BaseModel):
    """Response model for batch summary generation."""
    total_requested: int
    total_generated: int
    summaries: List[ContactSummaryResponse]


# API Endpoints

@router.post("/contacts/{contact_id}/summary", response_model=ContactSummaryResponse)
async def generate_contact_summary(
    contact_id: UUID,
    request: SummaryGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate an AI-powered summary for a specific contact.
    
    Args:
        contact_id: ID of the contact to summarize
        request: Summary generation parameters
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Generated contact summary with metadata
    """
    try:
        service = ContactSummarizationService(db)
        
        summary = await service.generate_contact_summary(
            contact_id=contact_id,
            user_id=current_user.id,
            summary_type=request.summary_type,
            meeting_context=request.meeting_context,
            force_refresh=request.force_refresh
        )
        
        return ContactSummaryResponse(**summary)
        
    except ContactSummarizationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {e}")


@router.get("/contacts/{contact_id}/summary", response_model=ContactSummaryResponse)
async def get_contact_summary(
    contact_id: UUID,
    summary_type: str = Query(SummaryType.COMPREHENSIVE, description="Type of summary to retrieve"),
    max_age_hours: Optional[int] = Query(None, description="Maximum age of cached summary in hours"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get cached contact summary or generate a new one if not available.
    
    Args:
        contact_id: ID of the contact
        summary_type: Type of summary to retrieve
        max_age_hours: Maximum age of cached summary
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Contact summary (cached or newly generated)
    """
    try:
        service = ContactSummarizationService(db)
        
        # Try to get cached summary first
        cached_summary = await service.get_cached_summary(
            contact_id=contact_id,
            user_id=current_user.id,
            summary_type=summary_type,
            max_age_hours=max_age_hours
        )
        
        if cached_summary:
            return ContactSummaryResponse(**cached_summary)
        
        # Generate new summary if no cache hit
        summary = await service.generate_contact_summary(
            contact_id=contact_id,
            user_id=current_user.id,
            summary_type=summary_type
        )
        
        return ContactSummaryResponse(**summary)
        
    except ContactSummarizationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get summary: {e}")


@router.get("/contacts/{contact_id}/summary/brief", response_model=ContactSummaryResponse)
async def get_brief_contact_summary(
    contact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a brief contact summary - optimized for quick overview.
    
    Args:
        contact_id: ID of the contact
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Brief contact summary
    """
    try:
        service = ContactSummarizationService(db)
        
        summary = await service.generate_contact_summary(
            contact_id=contact_id,
            user_id=current_user.id,
            summary_type=SummaryType.BRIEF
        )
        
        return ContactSummaryResponse(**summary)
        
    except ContactSummarizationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get brief summary: {e}")


@router.post("/contacts/{contact_id}/summary/meeting", response_model=PreMeetingSummaryResponse)
async def generate_pre_meeting_summary(
    contact_id: UUID,
    request: PreMeetingSummaryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate a specialized summary for upcoming meetings.
    
    Args:
        contact_id: ID of the contact
        request: Pre-meeting summary parameters
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Pre-meeting summary with talking points and preparation notes
    """
    try:
        service = ContactSummarizationService(db)
        
        summary = await service.generate_pre_meeting_summary(
            contact_id=contact_id,
            user_id=current_user.id,
            meeting_context=request.meeting_context,
            meeting_date=request.meeting_date
        )
        
        return PreMeetingSummaryResponse(**summary)
        
    except ContactSummarizationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate pre-meeting summary: {e}")


@router.post("/contacts/summaries/batch", response_model=BatchSummaryResponse)
async def generate_batch_summaries(
    request: BatchSummaryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate summaries for multiple contacts efficiently.
    
    Args:
        request: Batch summary generation parameters
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Batch summary results
    """
    try:
        service = ContactSummarizationService(db)
        
        summaries = await service.generate_batch_summaries(
            contact_ids=request.contact_ids,
            user_id=current_user.id,
            summary_type=request.summary_type,
            max_contacts=request.max_contacts
        )
        
        return BatchSummaryResponse(
            total_requested=len(request.contact_ids),
            total_generated=len(summaries),
            summaries=[ContactSummaryResponse(**summary) for summary in summaries]
        )
        
    except ContactSummarizationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate batch summaries: {e}")


@router.get("/contacts/{contact_id}/summary/relationship-status", response_model=ContactSummaryResponse)
async def get_relationship_status_summary(
    contact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get relationship status assessment for a contact.
    
    Args:
        contact_id: ID of the contact
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Relationship status summary with health assessment
    """
    try:
        service = ContactSummarizationService(db)
        
        summary = await service.generate_contact_summary(
            contact_id=contact_id,
            user_id=current_user.id,
            summary_type=SummaryType.RELATIONSHIP_STATUS
        )
        
        return ContactSummaryResponse(**summary)
        
    except ContactSummarizationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get relationship status: {e}")


@router.get("/contacts/{contact_id}/summary/updates", response_model=ContactSummaryResponse)
async def get_contact_updates_summary(
    contact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recent updates and changes for a contact.
    
    Args:
        contact_id: ID of the contact
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Updates summary with recent changes and action items
    """
    try:
        service = ContactSummarizationService(db)
        
        summary = await service.generate_contact_summary(
            contact_id=contact_id,
            user_id=current_user.id,
            summary_type=SummaryType.UPDATES
        )
        
        return ContactSummaryResponse(**summary)
        
    except ContactSummarizationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get updates summary: {e}")


@router.delete("/contacts/{contact_id}/summary/cache")
async def invalidate_contact_summary_cache(
    contact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Invalidate cached summaries for a contact to force refresh.
    
    Args:
        contact_id: ID of the contact
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Success confirmation
    """
    try:
        service = ContactSummarizationService(db)
        
        success = await service.update_summary_on_interaction(
            contact_id=contact_id,
            user_id=current_user.id,
            interaction_data={"type": "manual_cache_invalidation"}
        )
        
        if success:
            return {"message": "Summary cache invalidated successfully", "contact_id": str(contact_id)}
        else:
            raise HTTPException(status_code=500, detail="Failed to invalidate cache")
        
    except ContactSummarizationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to invalidate cache: {e}")


@router.get("/summary-types")
async def get_available_summary_types():
    """
    Get list of available summary types and their descriptions.
    
    Returns:
        Available summary types with descriptions
    """
    return {
        "summary_types": [
            {
                "type": SummaryType.COMPREHENSIVE,
                "name": "Comprehensive",
                "description": "Full relationship history, interests, and communication patterns",
                "cache_duration_hours": 24
            },
            {
                "type": SummaryType.BRIEF,
                "name": "Brief",
                "description": "Quick overview with key facts and recent activity",
                "cache_duration_hours": 12
            },
            {
                "type": SummaryType.PRE_MEETING,
                "name": "Pre-Meeting",
                "description": "Tailored for upcoming meetings with talking points",
                "cache_duration_hours": 1
            },
            {
                "type": SummaryType.RELATIONSHIP_STATUS,
                "name": "Relationship Status",
                "description": "Current relationship health and recommendations",
                "cache_duration_hours": 168
            },
            {
                "type": SummaryType.UPDATES,
                "name": "Updates",
                "description": "Recent changes and new developments",
                "cache_duration_hours": 6
            }
        ]
    } 