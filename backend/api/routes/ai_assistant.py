"""AI assistant endpoints with caching support."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from lib.database import get_db
from services.ai_assistant import AIAssistantService, AIAssistantError
from services.auth import get_current_user
from models.orm.user import User

router = APIRouter()


# Request/Response Models

class BriefingRequest(BaseModel):
    """Request model for briefing generation."""
    contact_name: str = Field(..., description="Name of the contact")
    contact_context: str = Field(..., description="Context about the contact (company, role, etc.)")
    meeting_context: str = Field(..., description="Context about the upcoming meeting")
    force_refresh: bool = Field(False, description="Skip cache and generate fresh briefing")


class MessageRequest(BaseModel):
    """Request model for message generation."""
    message_type: str = Field(..., description="Type of message (follow_up, cold_outreach, etc.)")
    recipient_context: str = Field(..., description="Context about the recipient")
    message_context: str = Field(..., description="Context about the message purpose")
    tone: str = Field("professional", description="Desired tone (professional, friendly, formal)")
    force_refresh: bool = Field(False, description="Skip cache and generate fresh message")


class AIResponse(BaseModel):
    """Response model for AI-generated content."""
    content: str = Field(..., description="Generated content")
    model: str = Field(..., description="Model used for generation")
    cached: bool = Field(..., description="Whether response was served from cache")
    finish_reason: str = Field(..., description="Reason generation stopped")
    usage: Optional[dict] = Field(None, description="Token usage information (None for cached)")


class CacheStatsResponse(BaseModel):
    """Response model for cache statistics."""
    total_requests: int
    cache_hits: int
    cache_misses: int
    hit_rate: float
    avg_response_time_ms: float
    cost_savings_usd: float


# API Endpoints

@router.post("/briefing", response_model=AIResponse)
async def generate_briefing(
    request: BriefingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate pre-meeting briefing with intelligent caching.
    
    Args:
        request: Briefing generation request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Generated briefing with cache metadata
    """
    try:
        service = AIAssistantService(db)
        
        response = await service.generate_briefing(
            contact_name=request.contact_name,
            contact_context=request.contact_context,
            meeting_context=request.meeting_context,
            user_id=str(current_user.id),
            force_refresh=request.force_refresh
        )
        
        return AIResponse(
            content=response.content,
            model=response.model.value,
            cached=response.cached,
            finish_reason=response.finish_reason,
            usage=response.usage.to_dict() if response.usage else None
        )
        
    except AIAssistantError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate briefing: {e}")


@router.post("/message", response_model=AIResponse)
async def generate_message(
    request: MessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate AI-assisted message with intelligent caching.
    
    Args:
        request: Message generation request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Generated message with cache metadata
    """
    try:
        service = AIAssistantService(db)
        
        response = await service.generate_message(
            message_type=request.message_type,
            recipient_context=request.recipient_context,
            message_context=request.message_context,
            user_id=str(current_user.id),
            tone=request.tone,
            force_refresh=request.force_refresh
        )
        
        return AIResponse(
            content=response.content,
            model=response.model.value,
            cached=response.cached,
            finish_reason=response.finish_reason,
            usage=response.usage.to_dict() if response.usage else None
        )
        
    except AIAssistantError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate message: {e}")


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get AI assistant cache statistics.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Cache performance statistics
    """
    try:
        service = AIAssistantService(db)
        stats = service.get_cache_stats()
        return CacheStatsResponse(**stats)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {e}")


@router.delete("/cache")
async def clear_cache(
    pattern: Optional[str] = Query(None, description="Optional pattern to match keys"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Clear AI assistant cache.
    
    Args:
        pattern: Optional pattern to match keys (admin only)
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Number of keys deleted
    """
    try:
        service = AIAssistantService(db)
        
        # Regular users can only clear their own cache
        if pattern is None:
            deleted = await service.invalidate_user_cache(str(current_user.id))
            return {"message": f"Cleared {deleted} cached responses for user", "deleted": deleted}
        else:
            # TODO: Add admin role check for pattern-based clearing
            # For now, only allow user-specific clearing
            deleted = await service.invalidate_user_cache(str(current_user.id))
            return {"message": f"Cleared {deleted} cached responses for user", "deleted": deleted}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {e}")


@router.get("/health")
async def health_check(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check AI assistant service health.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Health status including cache connectivity
    """
    try:
        service = AIAssistantService(db)
        health_status = await service.health_check()
        return health_status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {e}") 