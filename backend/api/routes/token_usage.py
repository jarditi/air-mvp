"""
Token Usage API Routes

This module provides REST API endpoints for LLM token usage tracking,
cost monitoring, budget management, and usage analytics.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from lib.database import get_db
from services.token_usage_service import TokenUsageService, TokenUsageError, BudgetExceededError
from services.auth import get_current_user
from models.orm.user import User

router = APIRouter()


# Request/Response Models

class UsageStatsResponse(BaseModel):
    """Response model for usage statistics."""
    period_days: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_cost: float
    total_tokens: int
    avg_cost_per_request: float
    avg_tokens_per_request: float
    avg_response_time: float
    success_rate: float
    cache_hit_rate: float
    by_model: Dict[str, Dict[str, Any]]
    by_usage_type: Dict[str, Dict[str, Any]]


class BudgetCreateRequest(BaseModel):
    """Request model for creating a budget."""
    budget_type: str = Field(..., description="Type of budget: 'user', 'global', 'usage_type'")
    budget_period: str = Field(..., description="Period: 'daily', 'weekly', 'monthly'")
    budget_amount_usd: float = Field(..., gt=0, description="Budget amount in USD")
    scope: Optional[str] = Field(None, description="Scope for usage_type budgets")
    warning_threshold: float = Field(0.8, ge=0, le=1, description="Warning threshold (0.0-1.0)")
    hard_limit: bool = Field(False, description="Whether to enforce hard limit")


class BudgetResponse(BaseModel):
    """Response model for budget information."""
    id: str
    user_id: Optional[str]
    budget_type: str
    scope: Optional[str]
    budget_period: str
    budget_amount_usd: float
    warning_threshold: float
    hard_limit: bool
    current_period_start: str
    current_period_end: str
    current_period_spent: float
    current_period_requests: int
    usage_percentage: float
    remaining_budget: float
    is_warning_threshold_exceeded: bool
    budget_exceeded: bool
    is_active: bool


class BudgetStatusResponse(BaseModel):
    """Response model for budget status."""
    user_id: str
    budgets: List[BudgetResponse]
    any_exceeded: bool
    any_warning: bool


class UsageLogResponse(BaseModel):
    """Response model for usage log entries."""
    id: str
    created_at: str
    user_id: Optional[str]
    request_id: Optional[str]
    model: str
    usage_type: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    response_time_ms: int
    success: bool
    cached_response: bool


class OptimizationRecommendationsResponse(BaseModel):
    """Response model for optimization recommendations."""
    period_days: int
    total_recommendations: int
    recommendations: List[Dict[str, Any]]
    current_stats: Dict[str, Any]


# API Endpoints

@router.get("/usage/statistics", response_model=UsageStatsResponse)
async def get_usage_statistics(
    period_days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive usage statistics for the current user.
    
    Args:
        period_days: Number of days to analyze (1-365)
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Usage statistics including costs, tokens, performance metrics
    """
    try:
        service = TokenUsageService(db)
        stats = service.get_usage_statistics(
            user_id=current_user.id,
            period_days=period_days
        )
        return UsageStatsResponse(**stats)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get usage statistics: {e}")


@router.get("/usage/logs")
async def get_usage_logs(
    model: Optional[str] = Query(None, description="Filter by model name"),
    usage_type: Optional[str] = Query(None, description="Filter by usage type"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    success_only: Optional[bool] = Query(None, description="Filter by success status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get usage logs with filtering and pagination.
    
    Args:
        model: Filter by model name
        usage_type: Filter by usage type
        start_date: Filter by start date
        end_date: Filter by end date
        success_only: Filter by success status
        limit: Maximum number of results (1-1000)
        offset: Offset for pagination
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List of usage log entries
    """
    try:
        service = TokenUsageService(db)
        logs = service.get_usage_logs(
            user_id=current_user.id,
            model=model,
            usage_type=usage_type,
            start_date=start_date,
            end_date=end_date,
            success_only=success_only,
            limit=limit,
            offset=offset
        )
        
        return {
            "logs": [log.to_dict() for log in logs],
            "total": len(logs),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get usage logs: {e}")


@router.post("/budgets", response_model=BudgetResponse)
async def create_budget(
    budget_request: BudgetCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new cost budget for the current user.
    
    Args:
        budget_request: Budget configuration
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Created budget information
    """
    try:
        service = TokenUsageService(db)
        budget = service.create_budget(
            user_id=current_user.id,
            budget_type=budget_request.budget_type,
            budget_period=budget_request.budget_period,
            budget_amount_usd=budget_request.budget_amount_usd,
            scope=budget_request.scope,
            warning_threshold=budget_request.warning_threshold,
            hard_limit=budget_request.hard_limit
        )
        
        return BudgetResponse(**budget.to_dict())
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TokenUsageError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budgets")
async def get_budgets(
    active_only: bool = Query(True, description="Only return active budgets"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get budgets for the current user.
    
    Args:
        active_only: Only return active budgets
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List of user budgets
    """
    try:
        service = TokenUsageService(db)
        budgets = service.get_budgets(
            user_id=current_user.id,
            active_only=active_only
        )
        
        return {
            "budgets": [budget.to_dict() for budget in budgets],
            "total": len(budgets)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get budgets: {e}")


@router.get("/budgets/status", response_model=BudgetStatusResponse)
async def get_budget_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get budget status for the current user.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Budget status including warnings and exceeded budgets
    """
    try:
        service = TokenUsageService(db)
        status = service.check_budget_status(current_user.id)
        
        return BudgetStatusResponse(**status)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get budget status: {e}")


@router.get("/optimization/recommendations", response_model=OptimizationRecommendationsResponse)
async def get_optimization_recommendations(
    period_days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get optimization recommendations based on usage patterns.
    
    Args:
        period_days: Number of days to analyze (1-365)
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Optimization recommendations and current usage statistics
    """
    try:
        service = TokenUsageService(db)
        recommendations = service.get_optimization_recommendations(
            user_id=current_user.id,
            period_days=period_days
        )
        
        return OptimizationRecommendationsResponse(**recommendations)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {e}")


@router.get("/usage/summary/{period_type}")
async def get_usage_summary(
    period_type: str,
    period_start: datetime,
    model: Optional[str] = Query(None, description="Filter by model"),
    usage_type: Optional[str] = Query(None, description="Filter by usage type"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get or generate usage summary for a specific period.
    
    Args:
        period_type: Type of period ('hour', 'day', 'week', 'month')
        period_start: Start of the period
        model: Filter by model name
        usage_type: Filter by usage type
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Usage summary for the specified period
    """
    if period_type not in ["hour", "day", "week", "month"]:
        raise HTTPException(status_code=400, detail="Invalid period type")
    
    try:
        service = TokenUsageService(db)
        summary = await service.generate_usage_summary(
            period_type=period_type,
            period_start=period_start,
            user_id=current_user.id,
            model=model,
            usage_type=usage_type
        )
        
        return summary.to_dict()
        
    except TokenUsageError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Admin endpoints (for global statistics)

@router.get("/admin/usage/global")
async def get_global_usage_statistics(
    period_days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get global usage statistics (admin only).
    
    Args:
        period_days: Number of days to analyze
        current_user: Current authenticated user (must be admin)
        db: Database session
        
    Returns:
        Global usage statistics
    """
    # TODO: Add admin role check
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        service = TokenUsageService(db)
        stats = service.get_usage_statistics(
            user_id=None,  # Global stats
            period_days=period_days
        )
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get global statistics: {e}")


@router.post("/admin/budgets/global", response_model=BudgetResponse)
async def create_global_budget(
    budget_request: BudgetCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a global cost budget (admin only).
    
    Args:
        budget_request: Budget configuration
        current_user: Current authenticated user (must be admin)
        db: Database session
        
    Returns:
        Created global budget
    """
    # TODO: Add admin role check
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        service = TokenUsageService(db)
        budget = service.create_budget(
            user_id=None,  # Global budget
            budget_type="global",
            budget_period=budget_request.budget_period,
            budget_amount_usd=budget_request.budget_amount_usd,
            scope=budget_request.scope,
            warning_threshold=budget_request.warning_threshold,
            hard_limit=budget_request.hard_limit
        )
        
        return BudgetResponse(**budget.to_dict())
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TokenUsageError as e:
        raise HTTPException(status_code=500, detail=str(e)) 