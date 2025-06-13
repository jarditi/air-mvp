"""Celery worker for automatic token refresh operations."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any

from celery import Celery
from sqlalchemy.orm import sessionmaker

from config import settings
from lib.database import get_db_session
from lib.logger import logger
from services.token_refresh import TokenRefreshService
from services.oauth_service import OAuthService
from models.orm.integration import Integration


# Initialize Celery app
celery_app = Celery(
    'token_refresh_worker',
    broker=settings.CELERY_BROKER_URL or 'redis://localhost:6379/0',
    backend=settings.CELERY_RESULT_BACKEND or 'redis://localhost:6379/0'
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_compression='gzip',
    result_compression='gzip',
)

# Periodic task schedule
celery_app.conf.beat_schedule = {
    'refresh-expiring-tokens': {
        'task': 'workers.token_refresh_worker.refresh_expiring_tokens',
        'schedule': 300.0,  # Every 5 minutes
    },
    'cleanup-expired-oauth-states': {
        'task': 'workers.token_refresh_worker.cleanup_expired_oauth_states',
        'schedule': 3600.0,  # Every hour
    },
    'token-health-check': {
        'task': 'workers.token_refresh_worker.token_health_check',
        'schedule': 1800.0,  # Every 30 minutes
    },
}


def get_async_session():
    """Get async database session for worker tasks."""
    return get_db_session()


@celery_app.task(bind=True, max_retries=3)
def refresh_expiring_tokens(self, buffer_minutes: int = 5, max_concurrent: int = 10):
    """
    Celery task to refresh tokens that are expiring soon.
    
    Args:
        buffer_minutes: Refresh tokens expiring within this many minutes
        max_concurrent: Maximum concurrent refresh operations
    """
    try:
        logger.info(f"Starting scheduled token refresh task (buffer: {buffer_minutes} minutes)")
        
        # Run the async function in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                _refresh_expiring_tokens_async(buffer_minutes, max_concurrent)
            )
            
            logger.info(f"Token refresh task completed: {result}")
            return result
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Token refresh task failed: {str(e)}")
        
        # Retry with exponential backoff
        countdown = 60 * (2 ** self.request.retries)  # 60s, 120s, 240s
        raise self.retry(exc=e, countdown=countdown)


@celery_app.task(bind=True, max_retries=2)
def refresh_integration_token(self, integration_id: str, force: bool = False):
    """
    Celery task to refresh token for a specific integration.
    
    Args:
        integration_id: Integration ID to refresh
        force: Force refresh even if token is not expiring
    """
    try:
        logger.info(f"Starting token refresh for integration {integration_id}")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                _refresh_integration_token_async(integration_id, force)
            )
            
            logger.info(f"Integration token refresh completed: {result}")
            return result
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Integration token refresh failed: {str(e)}")
        
        countdown = 300 * (2 ** self.request.retries)  # 5min, 10min
        raise self.retry(exc=e, countdown=countdown)


@celery_app.task(bind=True, max_retries=1)
def cleanup_expired_oauth_states(self):
    """Celery task to clean up expired OAuth states."""
    try:
        logger.info("Starting OAuth state cleanup task")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_cleanup_expired_oauth_states_async())
            
            logger.info(f"OAuth state cleanup completed: cleaned up {result} states")
            return {"cleaned_up": result}
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"OAuth state cleanup failed: {str(e)}")
        raise self.retry(exc=e, countdown=300)  # Retry after 5 minutes


@celery_app.task(bind=True, max_retries=1)
def token_health_check(self):
    """Celery task to perform health checks on integrations."""
    try:
        logger.info("Starting token health check task")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_token_health_check_async())
            
            logger.info(f"Token health check completed: {result}")
            return result
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Token health check failed: {str(e)}")
        raise self.retry(exc=e, countdown=600)  # Retry after 10 minutes


@celery_app.task(bind=True, max_retries=2)
def refresh_user_tokens(self, user_id: str, force: bool = False):
    """
    Celery task to refresh all tokens for a specific user.
    
    Args:
        user_id: User ID to refresh tokens for
        force: Force refresh even if tokens are not expiring
    """
    try:
        logger.info(f"Starting token refresh for user {user_id}")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                _refresh_user_tokens_async(user_id, force)
            )
            
            logger.info(f"User token refresh completed: {result}")
            return result
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"User token refresh failed: {str(e)}")
        
        countdown = 300 * (2 ** self.request.retries)  # 5min, 10min
        raise self.retry(exc=e, countdown=countdown)


# Async helper functions

async def _refresh_expiring_tokens_async(buffer_minutes: int, max_concurrent: int) -> Dict[str, Any]:
    """Async helper for refreshing expiring tokens."""
    db = get_async_session()
    try:
        token_refresh_service = TokenRefreshService(db)
        return await token_refresh_service.refresh_expiring_tokens(
            buffer_minutes=buffer_minutes,
            max_concurrent=max_concurrent
        )
    finally:
        db.close()


async def _refresh_integration_token_async(integration_id: str, force: bool) -> Dict[str, Any]:
    """Async helper for refreshing a specific integration token."""
    db = get_async_session()
    try:
        # Get the integration
        integration = db.query(Integration).filter(
            Integration.id == integration_id
        ).first()
        
        if not integration:
            return {"success": False, "error": "Integration not found"}
        
        token_refresh_service = TokenRefreshService(db)
        result, error = await token_refresh_service.refresh_token_for_integration(
            integration, force=force
        )
        
        return {
            "success": result.value == "success",
            "result": result.value,
            "error": error,
            "integration_id": integration_id
        }
        
    finally:
        db.close()


async def _refresh_user_tokens_async(user_id: str, force: bool) -> Dict[str, Any]:
    """Async helper for refreshing all user tokens."""
    db = get_async_session()
    try:
        token_refresh_service = TokenRefreshService(db)
        results = await token_refresh_service.refresh_user_tokens(
            user_id=user_id,
            force=force
        )
        
        # Convert results to serializable format
        serializable_results = {}
        for integration_id, (result, error) in results.items():
            serializable_results[integration_id] = {
                "result": result.value,
                "error": error
            }
        
        return {
            "user_id": user_id,
            "total_integrations": len(results),
            "results": serializable_results
        }
        
    finally:
        db.close()


async def _cleanup_expired_oauth_states_async() -> int:
    """Async helper for cleaning up expired OAuth states."""
    db = get_async_session()
    try:
        oauth_service = OAuthService(db)
        return await oauth_service.cleanup_expired_oauth_states()
    finally:
        db.close()


async def _token_health_check_async() -> Dict[str, Any]:
    """Async helper for performing token health checks."""
    db = get_async_session()
    try:
        token_refresh_service = TokenRefreshService(db)
        stats = token_refresh_service.get_refresh_statistics()
        
        # Identify critical issues
        critical_issues = []
        warnings = []
        
        # Check for expired tokens
        if stats["status_counts"].get("expired", 0) > 0:
            critical_issues.append(f"{stats['status_counts']['expired']} integrations have expired tokens")
        
        # Check for high error rates
        if stats["with_errors"] > stats["total_integrations"] * 0.1:  # More than 10% with errors
            warnings.append(f"{stats['with_errors']} integrations have errors")
        
        # Check for tokens expiring soon
        if stats["expiring_within_hour"] > 0:
            warnings.append(f"{stats['expiring_within_hour']} tokens expire within an hour")
        
        # Check for rate limited integrations
        if stats["rate_limited"] > 0:
            warnings.append(f"{stats['rate_limited']} integrations are rate limited")
        
        health_status = "healthy"
        if critical_issues:
            health_status = "critical"
        elif warnings:
            health_status = "warning"
        
        return {
            "health_status": health_status,
            "critical_issues": critical_issues,
            "warnings": warnings,
            "statistics": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    finally:
        db.close()


# Utility functions for manual task scheduling

def schedule_integration_refresh(integration_id: str, force: bool = False, delay: int = 0):
    """
    Schedule a token refresh for a specific integration.
    
    Args:
        integration_id: Integration ID to refresh
        force: Force refresh even if token is not expiring
        delay: Delay in seconds before executing the task
    """
    if delay > 0:
        refresh_integration_token.apply_async(
            args=[integration_id, force],
            countdown=delay
        )
    else:
        refresh_integration_token.delay(integration_id, force)


def schedule_user_token_refresh(user_id: str, force: bool = False, delay: int = 0):
    """
    Schedule token refresh for all user integrations.
    
    Args:
        user_id: User ID to refresh tokens for
        force: Force refresh even if tokens are not expiring
        delay: Delay in seconds before executing the task
    """
    if delay > 0:
        refresh_user_tokens.apply_async(
            args=[user_id, force],
            countdown=delay
        )
    else:
        refresh_user_tokens.delay(user_id, force)


def schedule_bulk_refresh(buffer_minutes: int = 5, delay: int = 0):
    """
    Schedule bulk refresh of expiring tokens.
    
    Args:
        buffer_minutes: Refresh tokens expiring within this many minutes
        delay: Delay in seconds before executing the task
    """
    if delay > 0:
        refresh_expiring_tokens.apply_async(
            args=[buffer_minutes],
            countdown=delay
        )
    else:
        refresh_expiring_tokens.delay(buffer_minutes)


if __name__ == '__main__':
    # For running the worker directly
    celery_app.start() 