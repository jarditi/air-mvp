"""
Email Contact Filtering API Routes for AIR MVP

This module provides REST API endpoints for Task 2.5.4: Email-based contact filtering
with two-way validation using metadata-only analysis.

Endpoints:
- POST /email-contacts/extract - Extract and filter contacts from emails
- POST /email-contacts/validate - Validate specific contact quality
- GET /email-contacts/stats - Get filtering statistics
- GET /email-contacts/suggestions/cold - Get cold outreach suggestions
- GET /email-contacts/health - Service health check
"""

import logging
from typing import Dict, List, Optional, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from lib.database import get_db
from services.email_contact_filtering_service import EmailContactFilteringService
from services.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Email Contact Filtering"])


# Pydantic models for request/response
class EmailContactExtractionRequest(BaseModel):
    """Request model for email contact extraction"""
    integration_id: str = Field(..., description="Gmail integration ID")
    days_back: int = Field(90, description="Number of days to look back", ge=1, le=365)
    max_messages: int = Field(1000, description="Maximum messages to analyze", ge=100, le=5000)
    min_message_count: int = Field(2, description="Minimum messages per contact", ge=1, le=10)
    require_two_way: bool = Field(True, description="Require bidirectional communication")


class EmailContactValidationRequest(BaseModel):
    """Request model for contact validation"""
    integration_id: str = Field(..., description="Gmail integration ID")
    contact_email: str = Field(..., description="Email address to validate")


class EmailContactSuggestionsRequest(BaseModel):
    """Request model for contact suggestions"""
    integration_id: str = Field(..., description="Gmail integration ID")
    suggestion_type: str = Field("cold_outreach", description="Type of suggestions")
    limit: int = Field(20, description="Maximum suggestions to return", ge=1, le=100)


class EmailContactExtractionResponse(BaseModel):
    """Response model for email contact extraction"""
    contacts_analyzed: int
    contacts_extracted: int
    contacts_filtered: int
    two_way_validated: int
    professional_contacts: int
    automated_filtered: int
    spam_filtered: int
    processing_time_seconds: float
    contacts: List[Dict[str, Any]]
    statistics: Dict[str, Any]


class EmailContactValidationResponse(BaseModel):
    """Response model for contact validation"""
    email: str
    found: bool
    message_count: Optional[int] = None
    thread_count: Optional[int] = None
    has_two_way: Optional[bool] = None
    is_professional: Optional[bool] = None
    is_automated: Optional[bool] = None
    response_rate: Optional[float] = None
    relationship_strength: Optional[float] = None
    last_contact: Optional[str] = None
    quality_assessment: Optional[str] = None
    reason: Optional[str] = None


class EmailContactStatsResponse(BaseModel):
    """Response model for filtering statistics"""
    last_filtering_run: str
    total_emails_analyzed: int
    contacts_extracted: int
    contacts_filtered: int
    two_way_validated: int
    professional_contacts: int
    automated_filtered: int
    spam_filtered: int
    avg_quality_score: float
    top_domains: List[Dict[str, Any]]


class EmailContactSuggestionsResponse(BaseModel):
    """Response model for contact suggestions"""
    suggestions: List[Dict[str, Any]]
    suggestion_type: str
    total_count: int


class EmailContactHealthResponse(BaseModel):
    """Response model for service health check"""
    status: str
    service_name: str
    version: str
    features_available: List[str]
    last_check: str


@router.post("/extract", response_model=EmailContactExtractionResponse)
async def extract_email_contacts(
    request: EmailContactExtractionRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Extract and filter email contacts using metadata-only analysis
    
    This endpoint analyzes Gmail metadata to identify legitimate professional contacts
    with two-way validation, spam filtering, and relationship strength scoring.
    
    Args:
        request: Email contact extraction parameters
        background_tasks: Background task manager
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Email filtering results with validated contacts
    """
    try:
        service = EmailContactFilteringService(db)
        
        # Perform email contact extraction and filtering
        result = await service.extract_and_filter_contacts(
            integration_id=request.integration_id,
            days_back=request.days_back,
            max_messages=request.max_messages,
            min_message_count=request.min_message_count,
            require_two_way=request.require_two_way
        )
        
        return {
            "success": True,
            "data": {
                "contacts_analyzed": result.contacts_analyzed,
                "contacts_extracted": result.contacts_extracted,
                "contacts_filtered": result.contacts_filtered,
                "two_way_validated": result.two_way_validated,
                "professional_contacts": result.professional_contacts,
                "automated_filtered": result.automated_filtered,
                "spam_filtered": result.spam_filtered,
                "processing_time_seconds": result.processing_time_seconds,
                "contacts": result.contacts,
                "statistics": result.statistics
            }
        }
        
    except ValueError as e:
        logger.error(f"Email contact extraction validation error: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to extract email contacts: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract email contacts: {str(e)}"
        )


@router.post("/validate", response_model=EmailContactValidationResponse)
async def validate_contact_quality(
    request: EmailContactValidationRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Validate the quality of a specific email contact
    
    This endpoint analyzes the email history with a specific contact to determine
    relationship strength, communication patterns, and professional quality.
    
    Args:
        request: Contact validation parameters
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Contact quality validation result
    """
    try:
        service = EmailContactFilteringService(db)
        
        # Validate contact quality
        result = await service.validate_contact_quality(
            integration_id=request.integration_id,
            contact_email=request.contact_email
        )
        
        return {
            "success": True,
            "data": result
        }
        
    except ValueError as e:
        logger.error(f"Contact validation error: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to validate contact: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate contact: {str(e)}"
        )


@router.get("/stats", response_model=EmailContactStatsResponse)
async def get_filtering_statistics(
    integration_id: str = Query(..., description="Gmail integration ID"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get email contact filtering statistics
    
    This endpoint returns comprehensive statistics about email contact filtering
    operations, including counts, quality metrics, and domain analysis.
    
    Args:
        integration_id: Gmail integration ID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Email filtering statistics
    """
    try:
        service = EmailContactFilteringService(db)
        
        # Get filtering statistics
        stats = await service.get_filtering_statistics(integration_id)
        
        return {
            "success": True,
            "data": stats
        }
        
    except ValueError as e:
        logger.error(f"Statistics retrieval error: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to get filtering statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get filtering statistics: {str(e)}"
        )


@router.get("/suggestions/cold", response_model=EmailContactSuggestionsResponse)
async def get_cold_outreach_suggestions(
    integration_id: str = Query(..., description="Gmail integration ID"),
    limit: int = Query(20, description="Maximum suggestions to return", ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get cold outreach contact suggestions
    
    This endpoint returns suggestions for contacts that would be good candidates
    for cold outreach based on professional quality and low recent engagement.
    
    Args:
        integration_id: Gmail integration ID
        limit: Maximum number of suggestions to return
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Cold outreach contact suggestions
    """
    try:
        service = EmailContactFilteringService(db)
        
        # Get cold outreach suggestions
        suggestions = await service.get_contact_suggestions(
            integration_id=integration_id,
            suggestion_type='cold_outreach',
            limit=limit
        )
        
        return {
            "success": True,
            "data": {
                "suggestions": suggestions,
                "suggestion_type": "cold_outreach",
                "total_count": len(suggestions)
            }
        }
        
    except ValueError as e:
        logger.error(f"Suggestions retrieval error: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to get contact suggestions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get contact suggestions: {str(e)}"
        )


@router.get("/suggestions/reconnect")
async def get_reconnect_suggestions(
    integration_id: str = Query(..., description="Gmail integration ID"),
    limit: int = Query(20, description="Maximum suggestions to return", ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get reconnection contact suggestions
    
    This endpoint returns suggestions for contacts that would be good candidates
    for reconnection based on strong past relationships and dormant communication.
    
    Args:
        integration_id: Gmail integration ID
        limit: Maximum number of suggestions to return
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Reconnection contact suggestions
    """
    try:
        service = EmailContactFilteringService(db)
        
        # Get reconnection suggestions
        suggestions = await service.get_contact_suggestions(
            integration_id=integration_id,
            suggestion_type='reconnect',
            limit=limit
        )
        
        return {
            "success": True,
            "data": {
                "suggestions": suggestions,
                "suggestion_type": "reconnect",
                "total_count": len(suggestions)
            }
        }
        
    except ValueError as e:
        logger.error(f"Reconnect suggestions error: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to get reconnect suggestions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get reconnect suggestions: {str(e)}"
        )


@router.get("/health", response_model=EmailContactHealthResponse)
async def check_service_health(
    db: Session = Depends(get_db)
) -> EmailContactHealthResponse:
    """
    Check email contact filtering service health
    
    This endpoint provides a health check for the email contact filtering service,
    including feature availability and system status.
    
    Args:
        db: Database session
        
    Returns:
        Service health status
    """
    try:
        from datetime import datetime, timezone
        
        # Check service components
        features_available = [
            "metadata_extraction",
            "two_way_validation", 
            "spam_filtering",
            "automation_detection",
            "professional_scoring",
            "relationship_analysis",
            "contact_suggestions"
        ]
        
        return EmailContactHealthResponse(
            status="healthy",
            service_name="EmailContactFilteringService",
            version="1.0.0",
            features_available=features_available,
            last_check=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return EmailContactHealthResponse(
            status="unhealthy",
            service_name="EmailContactFilteringService",
            version="1.0.0",
            features_available=[],
            last_check=datetime.now(timezone.utc).isoformat()
        )


@router.post("/extract-background")
async def extract_email_contacts_background(
    request: EmailContactExtractionRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Extract email contacts in background for large datasets
    
    This endpoint queues email contact extraction as a background task
    for processing large volumes of email data without blocking the request.
    
    Args:
        request: Email contact extraction parameters
        background_tasks: Background task manager
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Background task status
    """
    try:
        # Add background task for email contact extraction
        background_tasks.add_task(
            _background_extract_contacts,
            db,
            request.integration_id,
            request.days_back,
            request.max_messages,
            request.min_message_count,
            request.require_two_way
        )
        
        return {
            "success": True,
            "data": {
                "message": "Email contact extraction started in background",
                "integration_id": request.integration_id,
                "estimated_completion": "5-15 minutes",
                "status": "processing"
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to start background extraction: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start background extraction: {str(e)}"
        )


async def _background_extract_contacts(
    db: Session,
    integration_id: str,
    days_back: int,
    max_messages: int,
    min_message_count: int,
    require_two_way: bool
):
    """Background task for email contact extraction"""
    try:
        service = EmailContactFilteringService(db)
        
        result = await service.extract_and_filter_contacts(
            integration_id=integration_id,
            days_back=days_back,
            max_messages=max_messages,
            min_message_count=min_message_count,
            require_two_way=require_two_way
        )
        
        logger.info(f"Background email extraction completed: {result.contacts_extracted} contacts")
        
    except Exception as e:
        logger.error(f"Background email extraction failed: {e}")
        raise 