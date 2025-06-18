"""
Token Usage Tracking Service

This service provides comprehensive tracking and management of LLM token usage,
including cost monitoring, budget management, usage analytics, and optimization insights.

Features:
- Real-time usage logging
- Cost tracking and budgets
- Usage analytics and reporting
- Performance monitoring
- Budget alerts and limits
- Usage optimization recommendations
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID
import json
import logging
from dataclasses import asdict

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.exc import IntegrityError

from lib.database import get_db
from lib.logger import logger
from lib.exceptions import AIRException
from lib.llm_client import LLMUsage, LLMUsageType, OpenAIModel
from models.orm.llm_usage import LLMUsageLog, LLMUsageSummary, LLMCostBudget
from models.orm.user import User


class TokenUsageError(AIRException):
    """Token usage tracking specific errors."""
    pass


class BudgetExceededError(TokenUsageError):
    """Raised when a budget limit is exceeded."""
    pass


class TokenUsageService:
    """
    Comprehensive token usage tracking and management service.
    
    Handles logging, analytics, budgets, and optimization for LLM usage.
    """
    
    def __init__(self, db: Session):
        """Initialize the token usage service."""
        self.db = db
    
    async def log_usage(
        self,
        usage: LLMUsage,
        endpoint: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        prompt_length: Optional[int] = None,
        completion_length: Optional[int] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        success: bool = True,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        cached_response: bool = False,
        cache_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> LLMUsageLog:
        """
        Log a single LLM usage event.
        
        Args:
            usage: LLMUsage object with token and cost information
            endpoint: API endpoint that made the request
            user_agent: User agent string
            ip_address: Client IP address
            prompt_length: Length of prompt in characters
            completion_length: Length of completion in characters
            temperature: Temperature parameter used
            max_tokens: Max tokens parameter used
            success: Whether the request was successful
            error_type: Type of error if failed
            error_message: Error message if failed
            cached_response: Whether response was cached
            cache_key: Cache key if cached
            metadata: Additional metadata
            
        Returns:
            Created LLMUsageLog instance
        """
        try:
            # Create usage log entry
            usage_log = LLMUsageLog(
                user_id=UUID(usage.user_id) if usage.user_id else None,
                request_id=usage.request_id,
                model=usage.model.value,
                usage_type=usage.usage_type.value,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                cost_usd=Decimal(str(usage.cost_usd)),
                response_time_ms=usage.response_time_ms,
                endpoint=endpoint,
                user_agent=user_agent,
                ip_address=ip_address,
                prompt_length=prompt_length,
                completion_length=completion_length,
                temperature=Decimal(str(temperature)) if temperature is not None else None,
                max_tokens=max_tokens,
                success=success,
                error_type=error_type,
                error_message=error_message,
                cached_response=cached_response,
                cache_key=cache_key,
                request_metadata=metadata or {}
            )
            
            self.db.add(usage_log)
            self.db.commit()
            
            # Update budgets if user is specified
            if usage.user_id:
                await self._update_budgets(UUID(usage.user_id), Decimal(str(usage.cost_usd)))
            
            logger.info(f"Logged LLM usage: {usage.model.value}, {usage.total_tokens} tokens, ${usage.cost_usd}")
            
            return usage_log
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to log LLM usage: {e}")
            raise TokenUsageError(f"Failed to log usage: {e}")
    
    async def _update_budgets(self, user_id: UUID, cost: Decimal) -> None:
        """Update user budgets with new usage."""
        try:
            # Get active budgets for user
            budgets = self.db.query(LLMCostBudget).filter(
                and_(
                    LLMCostBudget.user_id == user_id,
                    LLMCostBudget.is_active == True,
                    LLMCostBudget.current_period_start <= datetime.utcnow(),
                    LLMCostBudget.current_period_end >= datetime.utcnow()
                )
            ).all()
            
            for budget in budgets:
                budget.add_usage(cost)
                
                # Check for budget exceeded
                if budget.hard_limit and budget.is_budget_exceeded:
                    raise BudgetExceededError(
                        f"Budget exceeded for {budget.budget_type}: "
                        f"${budget.current_period_spent} / ${budget.budget_amount_usd}"
                    )
                
                # Log warning if threshold exceeded
                if (budget.is_warning_threshold_exceeded and 
                    budget.last_warning_sent is None):
                    budget.last_warning_sent = datetime.utcnow()
                    logger.warning(
                        f"Budget warning threshold exceeded for user {user_id}: "
                        f"{budget.usage_percentage:.1f}% of ${budget.budget_amount_usd}"
                    )
            
            self.db.commit()
            
        except BudgetExceededError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update budgets: {e}")
    
    def get_usage_logs(
        self,
        user_id: Optional[UUID] = None,
        model: Optional[str] = None,
        usage_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        success_only: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[LLMUsageLog]:
        """
        Get usage logs with filtering options.
        
        Args:
            user_id: Filter by user ID
            model: Filter by model name
            usage_type: Filter by usage type
            start_date: Filter by start date
            end_date: Filter by end date
            success_only: Filter by success status
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of LLMUsageLog instances
        """
        query = self.db.query(LLMUsageLog)
        
        # Apply filters
        if user_id:
            query = query.filter(LLMUsageLog.user_id == user_id)
        if model:
            query = query.filter(LLMUsageLog.model == model)
        if usage_type:
            query = query.filter(LLMUsageLog.usage_type == usage_type)
        if start_date:
            query = query.filter(LLMUsageLog.created_at >= start_date)
        if end_date:
            query = query.filter(LLMUsageLog.created_at <= end_date)
        if success_only is not None:
            query = query.filter(LLMUsageLog.success == success_only)
        
        # Order by most recent first
        query = query.order_by(desc(LLMUsageLog.created_at))
        
        # Apply pagination
        query = query.offset(offset).limit(limit)
        
        return query.all()
    
    def get_usage_statistics(
        self,
        user_id: Optional[UUID] = None,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive usage statistics.
        
        Args:
            user_id: Filter by user ID (None for global stats)
            period_days: Number of days to analyze
            
        Returns:
            Dictionary with usage statistics
        """
        start_date = datetime.utcnow() - timedelta(days=period_days)
        
        query = self.db.query(LLMUsageLog).filter(
            LLMUsageLog.created_at >= start_date
        )
        
        if user_id:
            query = query.filter(LLMUsageLog.user_id == user_id)
        
        logs = query.all()
        
        if not logs:
            return {
                "period_days": period_days,
                "total_requests": 0,
                "total_cost": 0.0,
                "total_tokens": 0,
                "avg_response_time": 0,
                "success_rate": 0.0,
                "cache_hit_rate": 0.0,
                "by_model": {},
                "by_usage_type": {},
                "daily_usage": []
            }
        
        # Calculate basic statistics
        total_requests = len(logs)
        successful_requests = sum(1 for log in logs if log.success)
        total_cost = sum(float(log.cost_usd) for log in logs)
        total_tokens = sum(log.total_tokens for log in logs)
        avg_response_time = sum(log.response_time_ms for log in logs) / total_requests
        success_rate = (successful_requests / total_requests) * 100
        cached_requests = sum(1 for log in logs if log.cached_response)
        cache_hit_rate = (cached_requests / total_requests) * 100
        
        # Group by model
        by_model = {}
        for log in logs:
            if log.model not in by_model:
                by_model[log.model] = {
                    "requests": 0,
                    "cost": 0.0,
                    "tokens": 0
                }
            by_model[log.model]["requests"] += 1
            by_model[log.model]["cost"] += float(log.cost_usd)
            by_model[log.model]["tokens"] += log.total_tokens
        
        # Group by usage type
        by_usage_type = {}
        for log in logs:
            if log.usage_type not in by_usage_type:
                by_usage_type[log.usage_type] = {
                    "requests": 0,
                    "cost": 0.0,
                    "tokens": 0
                }
            by_usage_type[log.usage_type]["requests"] += 1
            by_usage_type[log.usage_type]["cost"] += float(log.cost_usd)
            by_usage_type[log.usage_type]["tokens"] += log.total_tokens
        
        # Daily usage breakdown
        daily_usage = {}
        for log in logs:
            day = log.created_at.date()
            if day not in daily_usage:
                daily_usage[day] = {
                    "date": day.isoformat(),
                    "requests": 0,
                    "cost": 0.0,
                    "tokens": 0
                }
            daily_usage[day]["requests"] += 1
            daily_usage[day]["cost"] += float(log.cost_usd)
            daily_usage[day]["tokens"] += log.total_tokens
        
        return {
            "period_days": period_days,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": total_requests - successful_requests,
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "avg_cost_per_request": total_cost / total_requests,
            "avg_tokens_per_request": total_tokens / total_requests,
            "avg_response_time": avg_response_time,
            "success_rate": success_rate,
            "cache_hit_rate": cache_hit_rate,
            "by_model": by_model,
            "by_usage_type": by_usage_type,
            "daily_usage": list(daily_usage.values())
        }
    
    def create_budget(
        self,
        user_id: Optional[UUID],
        budget_type: str,
        budget_period: str,
        budget_amount_usd: float,
        scope: Optional[str] = None,
        warning_threshold: float = 0.8,
        hard_limit: bool = False
    ) -> LLMCostBudget:
        """
        Create a new cost budget.
        
        Args:
            user_id: User ID (None for global budget)
            budget_type: Type of budget ('user', 'global', 'usage_type')
            budget_period: Period ('daily', 'weekly', 'monthly')
            budget_amount_usd: Budget amount in USD
            scope: Scope for usage_type budgets
            warning_threshold: Warning threshold (0.0-1.0)
            hard_limit: Whether to enforce hard limit
            
        Returns:
            Created LLMCostBudget instance
        """
        try:
            # Calculate period dates
            now = datetime.utcnow()
            if budget_period == "daily":
                period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                period_end = period_start + timedelta(days=1)
            elif budget_period == "weekly":
                days_since_monday = now.weekday()
                period_start = (now - timedelta(days=days_since_monday)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                period_end = period_start + timedelta(weeks=1)
            elif budget_period == "monthly":
                period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if now.month == 12:
                    period_end = period_start.replace(year=now.year + 1, month=1)
                else:
                    period_end = period_start.replace(month=now.month + 1)
            else:
                raise ValueError(f"Invalid budget period: {budget_period}")
            
            budget = LLMCostBudget(
                user_id=user_id,
                budget_type=budget_type,
                scope=scope,
                budget_period=budget_period,
                budget_amount_usd=Decimal(str(budget_amount_usd)),
                warning_threshold=Decimal(str(warning_threshold)),
                hard_limit=hard_limit,
                current_period_start=period_start,
                current_period_end=period_end
            )
            
            self.db.add(budget)
            self.db.commit()
            
            logger.info(f"Created budget: {budget_type} ${budget_amount_usd} {budget_period}")
            
            return budget
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create budget: {e}")
            raise TokenUsageError(f"Failed to create budget: {e}")
    
    def get_budgets(
        self,
        user_id: Optional[UUID] = None,
        active_only: bool = True
    ) -> List[LLMCostBudget]:
        """
        Get budgets with optional filtering.
        
        Args:
            user_id: Filter by user ID
            active_only: Only return active budgets
            
        Returns:
            List of LLMCostBudget instances
        """
        query = self.db.query(LLMCostBudget)
        
        if user_id:
            query = query.filter(LLMCostBudget.user_id == user_id)
        if active_only:
            query = query.filter(LLMCostBudget.is_active == True)
        
        return query.order_by(desc(LLMCostBudget.created_at)).all()
    
    def check_budget_status(self, user_id: UUID) -> Dict[str, Any]:
        """
        Check budget status for a user.
        
        Args:
            user_id: User ID to check
            
        Returns:
            Dictionary with budget status information
        """
        budgets = self.get_budgets(user_id=user_id, active_only=True)
        
        status = {
            "user_id": str(user_id),
            "budgets": [],
            "any_exceeded": False,
            "any_warning": False,
            "total_spent_today": 0.0,
            "total_spent_this_month": 0.0
        }
        
        # Calculate daily and monthly spending
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        daily_spent = self.db.query(func.sum(LLMUsageLog.cost_usd)).filter(
            and_(
                LLMUsageLog.user_id == user_id,
                LLMUsageLog.created_at >= today,
                LLMUsageLog.success == True
            )
        ).scalar() or Decimal('0')
        
        monthly_spent = self.db.query(func.sum(LLMUsageLog.cost_usd)).filter(
            and_(
                LLMUsageLog.user_id == user_id,
                LLMUsageLog.created_at >= month_start,
                LLMUsageLog.success == True
            )
        ).scalar() or Decimal('0')
        
        status["total_spent_today"] = float(daily_spent)
        status["total_spent_this_month"] = float(monthly_spent)
        
        for budget in budgets:
            budget_info = budget.to_dict()
            budget_info["status"] = "ok"
            
            if budget.budget_exceeded:
                budget_info["status"] = "exceeded"
                status["any_exceeded"] = True
            elif budget.is_warning_threshold_exceeded:
                budget_info["status"] = "warning"
                status["any_warning"] = True
            
            status["budgets"].append(budget_info)
        
        return status
    
    async def generate_usage_summary(
        self,
        period_type: str,
        period_start: datetime,
        user_id: Optional[UUID] = None,
        model: Optional[str] = None,
        usage_type: Optional[str] = None
    ) -> LLMUsageSummary:
        """
        Generate or update a usage summary for a specific period.
        
        Args:
            period_type: Type of period ('hour', 'day', 'week', 'month')
            period_start: Start of the period
            user_id: User ID (None for global summary)
            model: Model name (None for all models)
            usage_type: Usage type (None for all types)
            
        Returns:
            LLMUsageSummary instance
        """
        try:
            # Calculate period end
            if period_type == "hour":
                period_end = period_start + timedelta(hours=1)
            elif period_type == "day":
                period_end = period_start + timedelta(days=1)
            elif period_type == "week":
                period_end = period_start + timedelta(weeks=1)
            elif period_type == "month":
                if period_start.month == 12:
                    period_end = period_start.replace(year=period_start.year + 1, month=1)
                else:
                    period_end = period_start.replace(month=period_start.month + 1)
            else:
                raise ValueError(f"Invalid period type: {period_type}")
            
            # Check if summary already exists
            existing_summary = self.db.query(LLMUsageSummary).filter(
                and_(
                    LLMUsageSummary.period_type == period_type,
                    LLMUsageSummary.period_start == period_start,
                    LLMUsageSummary.user_id == user_id,
                    LLMUsageSummary.model == model,
                    LLMUsageSummary.usage_type == usage_type
                )
            ).first()
            
            # Query usage logs for the period
            query = self.db.query(LLMUsageLog).filter(
                and_(
                    LLMUsageLog.created_at >= period_start,
                    LLMUsageLog.created_at < period_end
                )
            )
            
            if user_id:
                query = query.filter(LLMUsageLog.user_id == user_id)
            if model:
                query = query.filter(LLMUsageLog.model == model)
            if usage_type:
                query = query.filter(LLMUsageLog.usage_type == usage_type)
            
            logs = query.all()
            
            # Calculate aggregated metrics
            total_requests = len(logs)
            successful_requests = sum(1 for log in logs if log.success)
            failed_requests = total_requests - successful_requests
            total_tokens = sum(log.total_tokens for log in logs)
            total_prompt_tokens = sum(log.prompt_tokens for log in logs)
            total_completion_tokens = sum(log.completion_tokens for log in logs)
            total_cost = sum(log.cost_usd for log in logs)
            cached_requests = sum(1 for log in logs if log.cached_response)
            
            # Performance metrics
            response_times = [log.response_time_ms for log in logs if log.success]
            avg_response_time = sum(response_times) / len(response_times) if response_times else None
            min_response_time = min(response_times) if response_times else None
            max_response_time = max(response_times) if response_times else None
            
            # Calculate P95 response time
            if response_times:
                sorted_times = sorted(response_times)
                p95_index = int(len(sorted_times) * 0.95)
                p95_response_time = sorted_times[p95_index] if p95_index < len(sorted_times) else max_response_time
            else:
                p95_response_time = None
            
            # Cache hit rate
            cache_hit_rate = Decimal(cached_requests / total_requests) if total_requests > 0 else None
            
            # Unique counts
            unique_users = len(set(log.user_id for log in logs if log.user_id))
            unique_sessions = len(set(log.session_id for log in logs if log.session_id))
            
            if existing_summary:
                # Update existing summary
                summary = existing_summary
                summary.total_requests = total_requests
                summary.successful_requests = successful_requests
                summary.failed_requests = failed_requests
                summary.total_tokens = total_tokens
                summary.total_prompt_tokens = total_prompt_tokens
                summary.total_completion_tokens = total_completion_tokens
                summary.total_cost_usd = total_cost
                summary.avg_response_time_ms = avg_response_time
                summary.min_response_time_ms = min_response_time
                summary.max_response_time_ms = max_response_time
                summary.p95_response_time_ms = p95_response_time
                summary.cache_hit_rate = cache_hit_rate
                summary.cached_requests = cached_requests
                summary.unique_users = unique_users
                summary.unique_sessions = unique_sessions
                summary.updated_at = datetime.utcnow()
            else:
                # Create new summary
                summary = LLMUsageSummary(
                    period_type=period_type,
                    period_start=period_start,
                    period_end=period_end,
                    user_id=user_id,
                    model=model,
                    usage_type=usage_type,
                    total_requests=total_requests,
                    successful_requests=successful_requests,
                    failed_requests=failed_requests,
                    total_tokens=total_tokens,
                    total_prompt_tokens=total_prompt_tokens,
                    total_completion_tokens=total_completion_tokens,
                    total_cost_usd=total_cost,
                    avg_response_time_ms=avg_response_time,
                    min_response_time_ms=min_response_time,
                    max_response_time_ms=max_response_time,
                    p95_response_time_ms=p95_response_time,
                    cache_hit_rate=cache_hit_rate,
                    cached_requests=cached_requests,
                    unique_users=unique_users,
                    unique_sessions=unique_sessions
                )
                self.db.add(summary)
            
            self.db.commit()
            
            logger.info(f"Generated usage summary: {period_type} {period_start} - {total_requests} requests")
            
            return summary
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to generate usage summary: {e}")
            raise TokenUsageError(f"Failed to generate summary: {e}")
    
    def get_optimization_recommendations(
        self,
        user_id: Optional[UUID] = None,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Generate optimization recommendations based on usage patterns.
        
        Args:
            user_id: User ID (None for global recommendations)
            period_days: Number of days to analyze
            
        Returns:
            Dictionary with optimization recommendations
        """
        stats = self.get_usage_statistics(user_id=user_id, period_days=period_days)
        recommendations = []
        
        # Check cache hit rate
        if stats["cache_hit_rate"] < 20:
            recommendations.append({
                "type": "caching",
                "priority": "high",
                "title": "Low Cache Hit Rate",
                "description": f"Cache hit rate is only {stats['cache_hit_rate']:.1f}%. Consider implementing response caching.",
                "potential_savings": "20-40% cost reduction"
            })
        
        # Check model usage efficiency
        if stats["by_model"]:
            expensive_models = {
                model: data for model, data in stats["by_model"].items()
                if "gpt-4" in model.lower() and data["requests"] > stats["total_requests"] * 0.5
            }
            
            if expensive_models:
                recommendations.append({
                    "type": "model_optimization",
                    "priority": "medium",
                    "title": "High GPT-4 Usage",
                    "description": "Consider using GPT-3.5-turbo for simpler tasks to reduce costs.",
                    "potential_savings": "60-80% cost reduction for applicable tasks"
                })
        
        # Check response time patterns
        if stats["avg_response_time"] > 5000:  # 5 seconds
            recommendations.append({
                "type": "performance",
                "priority": "medium",
                "title": "Slow Response Times",
                "description": f"Average response time is {stats['avg_response_time']:.0f}ms. Consider optimizing prompts.",
                "potential_savings": "Improved user experience"
            })
        
        # Check error rate
        if stats["success_rate"] < 95:
            recommendations.append({
                "type": "reliability",
                "priority": "high",
                "title": "High Error Rate",
                "description": f"Success rate is {stats['success_rate']:.1f}%. Review error patterns and implement better retry logic.",
                "potential_savings": "Reduced wasted tokens and improved reliability"
            })
        
        # Check usage patterns
        if stats["total_requests"] > 0:
            avg_tokens = stats["avg_tokens_per_request"]
            if avg_tokens > 2000:
                recommendations.append({
                    "type": "prompt_optimization",
                    "priority": "medium",
                    "title": "High Token Usage",
                    "description": f"Average {avg_tokens:.0f} tokens per request. Consider shorter, more focused prompts.",
                    "potential_savings": "10-30% token reduction"
                })
        
        return {
            "period_days": period_days,
            "total_recommendations": len(recommendations),
            "recommendations": recommendations,
            "current_stats": stats
        } 