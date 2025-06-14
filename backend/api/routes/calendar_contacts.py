"""
Calendar Contact Extraction API Routes

This module provides REST API endpoints for calendar-based contact extraction,
implementing Task 2.5.2: Calendar-based contact extraction (Priority 1).
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import logging

from lib.database import get_db
from services.calendar_contact_extraction import CalendarContactExtractionService
from services.auth import get_current_user
from models.orm.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calendar-contacts", tags=["calendar-contacts"])


# Request/Response Models

class CalendarContactExtractionRequest(BaseModel):
    """Request model for calendar contact extraction"""
    days_back: Optional[int] = Field(None, description="Days back to sync (defaults to config)", ge=1, le=365)
    days_forward: Optional[int] = Field(None, description="Days forward to sync (defaults to config)", ge=1, le=365)
    calendar_ids: Optional[List[str]] = Field(None, description="Specific calendar IDs to sync")
    force_refresh: bool = Field(False, description="Force refresh of existing contacts")


class CalendarContactExtractionResponse(BaseModel):
    """Response model for calendar contact extraction"""
    success: bool
    user_id: str
    sync_result: Dict[str, Any]
    extraction_result: Dict[str, Any]
    timestamp: str


class CalendarContactStatsResponse(BaseModel):
    """Response model for calendar contact statistics"""
    total_contacts: int
    by_strength_tier: Dict[str, int]
    by_interaction_frequency: Dict[str, int]
    recent_interactions: int
    avg_relationship_strength: float
    last_updated: str


class ContactSuggestionResponse(BaseModel):
    """Response model for contact reconnection suggestions"""
    contact_id: str
    name: str
    email: str
    relationship_strength: float
    days_since_contact: Optional[int]
    last_interaction: Optional[str]
    interaction_frequency: Optional[str]
    reason: str


# API Endpoints

@router.post("/extract", response_model=CalendarContactExtractionResponse)
async def extract_contacts_from_calendar(
    request: CalendarContactExtractionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Extract contacts from user's calendar events
    
    This endpoint implements the core functionality of Task 2.5.2:
    - Fetches calendar events from Google Calendar
    - Extracts attendee information as potential contacts
    - Applies intelligent scoring and deduplication
    - Creates or updates contacts in the database
    
    Args:
        request: Calendar extraction request parameters
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Extraction results with detailed statistics
    """
    try:
        service = CalendarContactExtractionService(db)
        
        result = await service.extract_contacts_from_calendar(
            user_id=str(current_user.id),
            days_back=request.days_back,
            days_forward=request.days_forward,
            calendar_ids=request.calendar_ids,
            force_refresh=request.force_refresh
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Calendar contact extraction failed")
            )
        
        return CalendarContactExtractionResponse(**result)
        
    except ValueError as e:
        logger.error(f"Calendar contact extraction validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Calendar contact extraction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Calendar contact extraction failed: {str(e)}"
        )


@router.post("/extract-background")
async def extract_contacts_background(
    request: CalendarContactExtractionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Extract contacts from calendar in the background
    
    This endpoint queues the contact extraction as a background task,
    useful for large calendar datasets that might take time to process.
    
    Args:
        request: Calendar extraction request parameters
        background_tasks: FastAPI background tasks
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Task queued confirmation
    """
    try:
        # Add background task
        background_tasks.add_task(
            _background_calendar_extraction,
            user_id=str(current_user.id),
            days_back=request.days_back,
            days_forward=request.days_forward,
            calendar_ids=request.calendar_ids,
            force_refresh=request.force_refresh
        )
        
        return {
            "success": True,
            "message": "Calendar contact extraction queued as background task",
            "user_id": str(current_user.id),
            "estimated_completion": "5-10 minutes for typical calendar size"
        }
        
    except Exception as e:
        logger.error(f"Failed to queue calendar contact extraction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue extraction task: {str(e)}"
        )


@router.get("/stats", response_model=CalendarContactStatsResponse)
async def get_calendar_contact_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get statistics about calendar-based contacts
    
    Returns comprehensive statistics about contacts extracted from calendar,
    including relationship strength distribution and interaction patterns.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Calendar contact statistics
    """
    try:
        service = CalendarContactExtractionService(db)
        
        stats = await service.get_calendar_contact_stats(str(current_user.id))
        
        return CalendarContactStatsResponse(**stats)
        
    except Exception as e:
        logger.error(f"Failed to get calendar contact stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get calendar contact statistics: {str(e)}"
        )


@router.get("/suggestions/reconnect", response_model=List[ContactSuggestionResponse])
async def get_reconnection_suggestions(
    limit: int = Query(10, description="Maximum number of suggestions", ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get suggestions for contacts to reconnect with
    
    Analyzes calendar-based contacts to identify strong relationships
    that have gone quiet and might benefit from reconnection.
    
    Args:
        limit: Maximum number of suggestions to return
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List of contact reconnection suggestions
    """
    try:
        service = CalendarContactExtractionService(db)
        
        suggestions = await service.suggest_calendar_contacts_to_reconnect(
            user_id=str(current_user.id),
            limit=limit
        )
        
        return [ContactSuggestionResponse(**suggestion) for suggestion in suggestions]
        
    except Exception as e:
        logger.error(f"Failed to get reconnection suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get reconnection suggestions: {str(e)}"
        )


@router.get("/health")
async def calendar_contacts_health():
    """
    Health check for calendar contact extraction service
    
    Returns:
        Service health status
    """
    return {
        "status": "healthy",
        "service": "calendar-contact-extraction",
        "features": [
            "calendar_event_fetching",
            "contact_extraction",
            "relationship_scoring",
            "contact_deduplication",
            "reconnection_suggestions"
        ],
        "timestamp": "2024-01-01T00:00:00Z"
    }


# Background task function

async def _background_calendar_extraction(
    user_id: str,
    days_back: Optional[int] = None,
    days_forward: Optional[int] = None,
    calendar_ids: Optional[List[str]] = None,
    force_refresh: bool = False
):
    """
    Background task for calendar contact extraction
    
    Args:
        user_id: User ID
        days_back: Days back to sync
        days_forward: Days forward to sync
        calendar_ids: Specific calendar IDs
        force_refresh: Force refresh flag
    """
    try:
        from lib.database import get_db
        
        # Get a new database session for the background task
        db = next(get_db())
        
        service = CalendarContactExtractionService(db)
        
        result = await service.extract_contacts_from_calendar(
            user_id=user_id,
            days_back=days_back,
            days_forward=days_forward,
            calendar_ids=calendar_ids,
            force_refresh=force_refresh
        )
        
        if result["success"]:
            logger.info(f"Background calendar extraction completed for user {user_id}: "
                       f"{result['extraction_result']['contacts_created']} created, "
                       f"{result['extraction_result']['contacts_updated']} updated")
        else:
            logger.error(f"Background calendar extraction failed for user {user_id}: "
                        f"{result.get('error', 'Unknown error')}")
        
        db.close()
        
    except Exception as e:
        logger.error(f"Background calendar extraction task failed for user {user_id}: {e}")
        if 'db' in locals():
            db.close() 