"""
Conversation Threading API Routes

This module provides API endpoints for Task 3.6.1: Cross-Platform Conversation Threading.
Handles unified conversation assembly, thread merging, and context linking across platforms.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from lib.database import get_db
from services.auth import get_current_user
from models.orm.user import User
from services.conversation_threading_service import (
    ConversationThreadingService,
    ConversationThread,
    ThreadMergeCandidate,
    ConversationContext
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversation-threads", tags=["conversation-threads"])


# Request Models

class BuildThreadsRequest(BaseModel):
    """Request model for building conversation threads"""
    contact_id: Optional[str] = Field(None, description="Optional contact ID to filter threads")
    days_back: int = Field(90, ge=1, le=365, description="Number of days back to analyze")
    include_platforms: Optional[List[str]] = Field(None, description="Optional list of platforms to include")
    force_rebuild: bool = Field(False, description="Force rebuild of all threads")


class ThreadSummaryRequest(BaseModel):
    """Request model for generating thread summary"""
    thread_id: str = Field(..., description="Thread ID to summarize")


class ContextRequest(BaseModel):
    """Request model for getting conversation context"""
    interaction_id: str = Field(..., description="Interaction ID to get context for")


# Response Models

class InteractionSummary(BaseModel):
    """Interaction summary for thread response"""
    id: str
    interaction_type: str
    direction: str
    subject: Optional[str]
    interaction_date: str
    source_platform: str
    duration_minutes: Optional[int]
    sentiment_score: Optional[float]
    meeting_attendees: List[str]
    platform_metadata: Dict[str, Any]


class ConversationThreadResponse(BaseModel):
    """Response model for conversation thread"""
    thread_id: str
    contact_id: str
    user_id: str
    platforms: List[str]
    interactions: List[InteractionSummary]
    start_date: str
    end_date: str
    total_interactions: int
    thread_depth: int
    subject_themes: List[str]
    dominant_platform: str
    participant_count: int
    thread_type: str
    context_score: float
    thread_summary: Optional[str] = None


class ThreadMergeCandidateResponse(BaseModel):
    """Response model for thread merge candidate"""
    thread_a_id: str
    thread_b_id: str
    merge_confidence: float
    merge_strategy: str
    evidence: Dict[str, Any]
    recommended_action: str


class ConversationContextResponse(BaseModel):
    """Response model for conversation context"""
    interaction_id: str
    related_interactions: List[str]
    context_type: str
    confidence_score: float
    evidence: Dict[str, Any]


class BuildThreadsResponse(BaseModel):
    """Response model for build threads operation"""
    success: bool
    user_id: str
    threads: List[ConversationThreadResponse]
    total_threads: int
    merge_candidates: List[ThreadMergeCandidateResponse]
    processing_time_seconds: float
    statistics: Dict[str, Any]
    timestamp: str


class ThreadSummaryResponse(BaseModel):
    """Response model for thread summary"""
    thread_id: str
    summary: str
    generated_at: str


class ContextAnalysisResponse(BaseModel):
    """Response model for context analysis"""
    interaction_id: str
    contexts: List[ConversationContextResponse]
    total_contexts: int
    analysis_timestamp: str


# Utility Functions

def _convert_thread_to_response(thread: ConversationThread) -> ConversationThreadResponse:
    """Convert ConversationThread to response model"""
    return ConversationThreadResponse(
        thread_id=thread.thread_id,
        contact_id=thread.contact_id,
        user_id=thread.user_id,
        platforms=list(thread.platforms),
        interactions=[
            InteractionSummary(**interaction) for interaction in thread.interactions
        ],
        start_date=thread.start_date.isoformat(),
        end_date=thread.end_date.isoformat(),
        total_interactions=thread.total_interactions,
        thread_depth=thread.thread_depth,
        subject_themes=thread.subject_themes,
        dominant_platform=thread.dominant_platform,
        participant_count=thread.participant_count,
        thread_type=thread.thread_type,
        context_score=thread.context_score,
        thread_summary=thread.thread_summary
    )


def _convert_merge_candidate_to_response(candidate: ThreadMergeCandidate) -> ThreadMergeCandidateResponse:
    """Convert ThreadMergeCandidate to response model"""
    return ThreadMergeCandidateResponse(
        thread_a_id=candidate.thread_a.thread_id,
        thread_b_id=candidate.thread_b.thread_id,
        merge_confidence=candidate.merge_confidence,
        merge_strategy=candidate.merge_strategy,
        evidence=candidate.evidence,
        recommended_action=candidate.recommended_action
    )


def _convert_context_to_response(context: ConversationContext) -> ConversationContextResponse:
    """Convert ConversationContext to response model"""
    return ConversationContextResponse(
        interaction_id=context.interaction_id,
        related_interactions=context.related_interactions,
        context_type=context.context_type,
        confidence_score=context.confidence_score,
        evidence=context.evidence
    )


# API Endpoints

@router.post("/build", response_model=BuildThreadsResponse)
async def build_conversation_threads(
    request: BuildThreadsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Build unified conversation threads across platforms
    
    This endpoint assembles conversations from email, calendar, LinkedIn and other
    platforms into unified threads with intelligent merging and context linking.
    
    Args:
        request: Build threads request parameters
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Conversation threads with merge candidates and statistics
    """
    try:
        start_time = datetime.now()
        
        service = ConversationThreadingService(db)
        
        # Build conversation threads
        threads = await service.build_conversation_threads(
            user_id=str(current_user.id),
            contact_id=request.contact_id,
            days_back=request.days_back,
            include_platforms=request.include_platforms,
            force_rebuild=request.force_rebuild
        )
        
        # Find merge candidates for manual review
        merge_candidates = await service._find_thread_merge_candidates(threads)
        manual_review_candidates = [
            candidate for candidate in merge_candidates
            if candidate.recommended_action == 'manual_review'
        ]
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Generate statistics
        platform_stats = {}
        thread_type_stats = {}
        total_interactions = 0
        
        for thread in threads:
            total_interactions += thread.total_interactions
            
            # Platform statistics
            for platform in thread.platforms:
                platform_stats[platform] = platform_stats.get(platform, 0) + 1
            
            # Thread type statistics
            thread_type_stats[thread.thread_type] = thread_type_stats.get(thread.thread_type, 0) + 1
        
        statistics = {
            'total_threads': len(threads),
            'total_interactions': total_interactions,
            'avg_interactions_per_thread': total_interactions / len(threads) if threads else 0,
            'platform_distribution': platform_stats,
            'thread_type_distribution': thread_type_stats,
            'merge_candidates_found': len(merge_candidates),
            'manual_review_candidates': len(manual_review_candidates),
            'auto_merged_threads': len([c for c in merge_candidates if c.recommended_action == 'auto_merge']),
            'processing_time_seconds': processing_time
        }
        
        # Convert to response models
        thread_responses = [_convert_thread_to_response(thread) for thread in threads]
        candidate_responses = [_convert_merge_candidate_to_response(candidate) for candidate in manual_review_candidates]
        
        return BuildThreadsResponse(
            success=True,
            user_id=str(current_user.id),
            threads=thread_responses,
            total_threads=len(threads),
            merge_candidates=candidate_responses,
            processing_time_seconds=processing_time,
            statistics=statistics,
            timestamp=datetime.now().isoformat()
        )
        
    except ValueError as e:
        logger.error(f"Thread building validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Thread building failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Thread building failed: {str(e)}"
        )


@router.post("/build-background")
async def build_conversation_threads_background(
    request: BuildThreadsRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Build conversation threads in the background
    
    This endpoint queues thread building as a background task,
    useful for large datasets that might take time to process.
    
    Args:
        request: Build threads request parameters
        background_tasks: FastAPI background tasks
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Task queued confirmation
    """
    try:
        # Add background task
        background_tasks.add_task(
            _background_thread_building,
            user_id=str(current_user.id),
            contact_id=request.contact_id,
            days_back=request.days_back,
            include_platforms=request.include_platforms,
            force_rebuild=request.force_rebuild
        )
        
        return {
            "success": True,
            "message": "Conversation thread building queued as background task",
            "user_id": str(current_user.id),
            "estimated_completion": "2-5 minutes for typical interaction volume"
        }
        
    except Exception as e:
        logger.error(f"Failed to queue thread building: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue thread building task: {str(e)}"
        )


@router.get("/contact/{contact_id}", response_model=List[ConversationThreadResponse])
async def get_contact_threads(
    contact_id: str,
    days_back: int = 90,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get conversation threads for a specific contact
    
    Args:
        contact_id: Contact identifier
        days_back: Days back to analyze
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List of conversation threads for the contact
    """
    try:
        service = ConversationThreadingService(db)
        
        threads = await service.build_conversation_threads(
            user_id=str(current_user.id),
            contact_id=contact_id,
            days_back=days_back
        )
        
        return [_convert_thread_to_response(thread) for thread in threads]
        
    except Exception as e:
        logger.error(f"Failed to get contact threads: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get contact threads: {str(e)}"
        )


@router.post("/summary", response_model=ThreadSummaryResponse)
async def generate_thread_summary(
    request: ThreadSummaryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate AI-powered summary for a conversation thread
    
    Args:
        request: Thread summary request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Generated thread summary
    """
    try:
        service = ConversationThreadingService(db)
        
        # First, get the thread (simplified - in real implementation, we'd store threads)
        threads = await service.build_conversation_threads(
            user_id=str(current_user.id),
            days_back=90
        )
        
        # Find the requested thread
        target_thread = None
        for thread in threads:
            if thread.thread_id == request.thread_id:
                target_thread = thread
                break
        
        if not target_thread:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Thread {request.thread_id} not found"
            )
        
        # Generate summary
        summary = await service.generate_thread_summary(target_thread)
        
        return ThreadSummaryResponse(
            thread_id=request.thread_id,
            summary=summary,
            generated_at=datetime.now().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate thread summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate thread summary: {str(e)}"
        )


@router.post("/context", response_model=ContextAnalysisResponse)
async def analyze_conversation_context(
    request: ContextRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze conversation context for a specific interaction
    
    Args:
        request: Context analysis request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Conversation context analysis
    """
    try:
        service = ConversationThreadingService(db)
        
        # Get conversation context
        contexts = await service.get_conversation_context(request.interaction_id)
        
        context_responses = [_convert_context_to_response(context) for context in contexts]
        
        return ContextAnalysisResponse(
            interaction_id=request.interaction_id,
            contexts=context_responses,
            total_contexts=len(contexts),
            analysis_timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to analyze conversation context: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze conversation context: {str(e)}"
        )


@router.get("/statistics")
async def get_threading_statistics(
    days_back: int = 90,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get conversation threading statistics for the user
    
    Args:
        days_back: Days back to analyze
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Threading statistics and insights
    """
    try:
        service = ConversationThreadingService(db)
        
        # Build threads to get statistics
        threads = await service.build_conversation_threads(
            user_id=str(current_user.id),
            days_back=days_back
        )
        
        # Calculate comprehensive statistics
        total_threads = len(threads)
        total_interactions = sum(thread.total_interactions for thread in threads)
        
        platform_stats = {}
        thread_type_stats = {}
        context_score_buckets = {'high': 0, 'medium': 0, 'low': 0}
        thread_depth_stats = []
        
        for thread in threads:
            # Platform distribution
            for platform in thread.platforms:
                platform_stats[platform] = platform_stats.get(platform, 0) + 1
            
            # Thread type distribution
            thread_type_stats[thread.thread_type] = thread_type_stats.get(thread.thread_type, 0) + 1
            
            # Context score buckets
            if thread.context_score >= 0.7:
                context_score_buckets['high'] += 1
            elif thread.context_score >= 0.4:
                context_score_buckets['medium'] += 1
            else:
                context_score_buckets['low'] += 1
            
            # Thread depth statistics
            thread_depth_stats.append(thread.thread_depth)
        
        # Calculate averages
        avg_interactions_per_thread = total_interactions / total_threads if total_threads > 0 else 0
        avg_context_score = sum(thread.context_score for thread in threads) / total_threads if total_threads > 0 else 0
        avg_thread_depth = sum(thread_depth_stats) / len(thread_depth_stats) if thread_depth_stats else 0
        
        # Cross-platform thread analysis
        cross_platform_threads = [thread for thread in threads if len(thread.platforms) > 1]
        cross_platform_percentage = (len(cross_platform_threads) / total_threads * 100) if total_threads > 0 else 0
        
        return {
            "success": True,
            "user_id": str(current_user.id),
            "analysis_period_days": days_back,
            "overview": {
                "total_threads": total_threads,
                "total_interactions": total_interactions,
                "avg_interactions_per_thread": round(avg_interactions_per_thread, 2),
                "avg_context_score": round(avg_context_score, 3),
                "avg_thread_depth": round(avg_thread_depth, 1)
            },
            "platform_distribution": platform_stats,
            "thread_type_distribution": thread_type_stats,
            "context_quality": context_score_buckets,
            "cross_platform_analysis": {
                "cross_platform_threads": len(cross_platform_threads),
                "cross_platform_percentage": round(cross_platform_percentage, 1),
                "most_common_combinations": self._get_platform_combinations(cross_platform_threads)
            },
            "insights": {
                "most_active_platform": max(platform_stats, key=platform_stats.get) if platform_stats else None,
                "dominant_thread_type": max(thread_type_stats, key=thread_type_stats.get) if thread_type_stats else None,
                "conversation_quality": "high" if avg_context_score >= 0.7 else "medium" if avg_context_score >= 0.4 else "low"
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get threading statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get threading statistics: {str(e)}"
        )


# Background task functions

async def _background_thread_building(
    user_id: str,
    contact_id: Optional[str] = None,
    days_back: int = 90,
    include_platforms: Optional[List[str]] = None,
    force_rebuild: bool = False
):
    """
    Background task for conversation thread building
    
    Args:
        user_id: User ID
        contact_id: Optional contact ID
        days_back: Days back to analyze
        include_platforms: Optional platform filter
        force_rebuild: Force rebuild flag
    """
    try:
        from lib.database import get_db
        
        # Get a new database session for the background task
        db = next(get_db())
        
        service = ConversationThreadingService(db)
        
        threads = await service.build_conversation_threads(
            user_id=user_id,
            contact_id=contact_id,
            days_back=days_back,
            include_platforms=include_platforms,
            force_rebuild=force_rebuild
        )
        
        logger.info(f"Background thread building completed for user {user_id}: "
                   f"{len(threads)} threads built")
        
        db.close()
        
    except Exception as e:
        logger.error(f"Background thread building task failed for user {user_id}: {e}")
        if 'db' in locals():
            db.close()


def _get_platform_combinations(cross_platform_threads: List[ConversationThread]) -> Dict[str, int]:
    """Get most common platform combinations"""
    combinations = {}
    
    for thread in cross_platform_threads:
        platform_combo = " + ".join(sorted(thread.platforms))
        combinations[platform_combo] = combinations.get(platform_combo, 0) + 1
    
    # Return top 5 combinations
    sorted_combinations = sorted(combinations.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_combinations[:5]) 