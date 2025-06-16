"""
Job Status and Monitoring API Endpoints (Task 3.1.5)

This module provides REST API endpoints for monitoring Celery job status,
retrieving job results, and accessing job metrics and health information.
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from celery.result import AsyncResult

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from workers.job_monitor import job_monitor, JobStatus, JobMetrics
from workers.job_storage import job_storage, JobResult, ResultStatus
from workers.celery_app import celery_app
from lib.logger import logger
from services.auth import get_current_user


# Pydantic models for API responses
class JobStatusResponse(BaseModel):
    """Job status response model"""
    task_id: str
    task_name: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = None
    retry_count: int = 0
    progress: Optional[Dict[str, Any]] = None


class JobMetricsResponse(BaseModel):
    """Job metrics response model"""
    task_name: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    retry_executions: int
    avg_execution_time: float
    last_execution_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None
    failure_rate: float
    success_rate: float


class SystemHealthResponse(BaseModel):
    """System health response model"""
    status: str
    redis_healthy: bool
    workers_available: bool
    total_queued_jobs: int
    overall_failure_rate: float
    active_jobs_count: int
    circuit_breakers_open: int
    timestamp: datetime


class QueueStatsResponse(BaseModel):
    """Queue statistics response model"""
    queue_name: str
    length: int


class WorkerStatsResponse(BaseModel):
    """Worker statistics response model"""
    worker_name: str
    active_tasks: int
    stats: Dict[str, Any]


class JobHistoryResponse(BaseModel):
    """Job history response model"""
    task_id: str
    task_name: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = None
    error: Optional[str] = None


# Create router
router = APIRouter(tags=["jobs"])


@router.get("/status/{task_id}", response_model=JobStatusResponse)
async def get_job_status(
    task_id: str = Path(..., description="Task ID to check status for"),
    current_user: dict = Depends(get_current_user)
):
    """Get status of a specific job"""
    try:
        # Get result from Celery
        async_result = AsyncResult(task_id, app=celery_app)
        
        # Get additional info from job monitor
        job_info = job_monitor.active_jobs.get(task_id)
        
        # Get stored result if available
        stored_result = job_storage.get_result(task_id)
        
        # Combine information
        response_data = {
            'task_id': task_id,
            'task_name': job_info.get('task_name', 'unknown') if job_info else 'unknown',
            'status': async_result.status,
            'result': async_result.result if async_result.successful() else None,
            'error': str(async_result.result) if async_result.failed() else None,
            'retry_count': 0
        }
        
        # Add timing information if available
        if job_info:
            response_data.update({
                'started_at': job_info.get('start_time'),
                'retry_count': job_info.get('retry_count', 0)
            })
        
        if stored_result:
            response_data.update({
                'started_at': stored_result.started_at,
                'completed_at': stored_result.completed_at,
                'execution_time': stored_result.execution_time,
                'retry_count': stored_result.retry_count
            })
        
        # Add progress information if task is running
        if async_result.status == 'PROGRESS':
            response_data['progress'] = async_result.info
        
        return JobStatusResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Failed to get job status for {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")


@router.get("/metrics", response_model=Dict[str, JobMetricsResponse])
async def get_all_job_metrics(
    current_user: dict = Depends(get_current_user)
):
    """Get metrics for all job types"""
    try:
        metrics = job_monitor.get_all_metrics()
        
        response = {}
        for task_name, job_metrics in metrics.items():
            response[task_name] = JobMetricsResponse(
                task_name=job_metrics.task_name,
                total_executions=job_metrics.total_executions,
                successful_executions=job_metrics.successful_executions,
                failed_executions=job_metrics.failed_executions,
                retry_executions=job_metrics.retry_executions,
                avg_execution_time=job_metrics.avg_execution_time,
                last_execution_time=job_metrics.last_execution_time,
                last_success_time=job_metrics.last_success_time,
                last_failure_time=job_metrics.last_failure_time,
                failure_rate=job_metrics.failure_rate,
                success_rate=job_metrics.success_rate
            )
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get job metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job metrics: {str(e)}")


@router.get("/metrics/{task_name}", response_model=JobMetricsResponse)
async def get_task_metrics(
    task_name: str = Path(..., description="Task name to get metrics for"),
    current_user: dict = Depends(get_current_user)
):
    """Get metrics for a specific task type"""
    try:
        metrics = job_monitor.get_task_metrics(task_name)
        
        if not metrics:
            raise HTTPException(status_code=404, detail=f"No metrics found for task: {task_name}")
        
        return JobMetricsResponse(
            task_name=metrics.task_name,
            total_executions=metrics.total_executions,
            successful_executions=metrics.successful_executions,
            failed_executions=metrics.failed_executions,
            retry_executions=metrics.retry_executions,
            avg_execution_time=metrics.avg_execution_time,
            last_execution_time=metrics.last_execution_time,
            last_success_time=metrics.last_success_time,
            last_failure_time=metrics.last_failure_time,
            failure_rate=metrics.failure_rate,
            success_rate=metrics.success_rate
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task metrics for {task_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task metrics: {str(e)}")


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    current_user: dict = Depends(get_current_user)
):
    """Get overall system health status"""
    try:
        health_status = job_monitor.get_health_status()
        
        return SystemHealthResponse(
            status=health_status['status'],
            redis_healthy=health_status['redis_healthy'],
            workers_available=health_status['workers_available'],
            total_queued_jobs=health_status['total_queued_jobs'],
            overall_failure_rate=health_status['overall_failure_rate'],
            active_jobs_count=health_status['active_jobs_count'],
            circuit_breakers_open=health_status['circuit_breakers_open'],
            timestamp=datetime.fromisoformat(health_status['timestamp'])
        )
        
    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get system health: {str(e)}")


@router.get("/queues", response_model=List[QueueStatsResponse])
async def get_queue_stats(
    current_user: dict = Depends(get_current_user)
):
    """Get statistics for all job queues"""
    try:
        queue_stats = job_monitor.get_queue_stats()
        
        response = []
        for queue_name, stats in queue_stats.items():
            response.append(QueueStatsResponse(
                queue_name=queue_name,
                length=stats['length']
            ))
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get queue stats: {str(e)}")


@router.get("/workers", response_model=List[WorkerStatsResponse])
async def get_worker_stats(
    current_user: dict = Depends(get_current_user)
):
    """Get statistics for all active workers"""
    try:
        worker_stats = job_monitor.get_worker_stats()
        
        response = []
        for worker_name, stats in worker_stats.items():
            response.append(WorkerStatsResponse(
                worker_name=worker_name,
                active_tasks=stats['active_tasks'],
                stats=stats.get('stats', {})
            ))
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get worker stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get worker stats: {str(e)}")


@router.get("/active", response_model=List[JobStatusResponse])
async def get_active_jobs(
    current_user: dict = Depends(get_current_user)
):
    """Get all currently active jobs"""
    try:
        active_jobs = job_monitor.get_active_jobs()
        
        response = []
        for task_id, job_info in active_jobs.items():
            response.append(JobStatusResponse(
                task_id=task_id,
                task_name=job_info['task_name'],
                status=job_info['status'],
                started_at=job_info['start_time'],
                retry_count=job_info.get('retry_count', 0)
            ))
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get active jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get active jobs: {str(e)}")


@router.get("/history/{task_name}", response_model=List[JobHistoryResponse])
async def get_task_history(
    task_name: str = Path(..., description="Task name to get history for"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    current_user: dict = Depends(get_current_user)
):
    """Get execution history for a specific task type"""
    try:
        history = job_monitor.get_task_history(task_name, limit)
        
        response = []
        for job_info in history:
            response.append(JobHistoryResponse(
                task_id=job_info['task_id'],
                task_name=job_info['task_name'],
                status=job_info['status'],
                started_at=job_info.get('start_time'),
                completed_at=job_info.get('end_time'),
                execution_time=job_info.get('execution_time'),
                error=job_info.get('error')
            ))
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get task history for {task_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task history: {str(e)}")


@router.get("/failed", response_model=List[JobHistoryResponse])
async def get_failed_jobs(
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    current_user: dict = Depends(get_current_user)
):
    """Get recent failed jobs for analysis"""
    try:
        # Get failed jobs from storage
        failed_results = job_storage.get_results_by_status(ResultStatus.FAILURE, hours, limit)
        
        response = []
        for result in failed_results:
            response.append(JobHistoryResponse(
                task_id=result.task_id,
                task_name=result.task_name,
                status=result.status.value,
                started_at=result.started_at,
                completed_at=result.completed_at,
                execution_time=result.execution_time,
                error=result.error
            ))
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get failed jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get failed jobs: {str(e)}")


@router.post("/retry/{task_id}")
async def retry_failed_job(
    task_id: str = Path(..., description="Task ID to retry"),
    current_user: dict = Depends(get_current_user)
):
    """Retry a failed job"""
    try:
        # Get the original job result
        stored_result = job_storage.get_result(task_id)
        
        if not stored_result:
            raise HTTPException(status_code=404, detail=f"Job {task_id} not found")
        
        if stored_result.status != ResultStatus.FAILURE:
            raise HTTPException(status_code=400, detail=f"Job {task_id} is not in failed state")
        
        # Create new task with same parameters
        # Note: This is a simplified retry - in production you might want more sophisticated logic
        task_name = stored_result.task_name
        args = stored_result.args or ()
        kwargs = stored_result.kwargs or {}
        
        # Get the task function from Celery registry
        if task_name in celery_app.tasks:
            task_func = celery_app.tasks[task_name]
            new_result = task_func.delay(*args, **kwargs)
            
            return {
                'message': f'Job {task_id} retried successfully',
                'new_task_id': new_result.id,
                'original_task_id': task_id
            }
        else:
            raise HTTPException(status_code=400, detail=f"Task type {task_name} not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry job {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retry job: {str(e)}")


@router.delete("/cancel/{task_id}")
async def cancel_job(
    task_id: str = Path(..., description="Task ID to cancel"),
    current_user: dict = Depends(get_current_user)
):
    """Cancel a running job"""
    try:
        # Revoke the task
        celery_app.control.revoke(task_id, terminate=True)
        
        return {
            'message': f'Job {task_id} cancelled successfully',
            'task_id': task_id
        }
        
    except Exception as e:
        logger.error(f"Failed to cancel job {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")


@router.get("/storage/stats")
async def get_storage_stats(
    current_user: dict = Depends(get_current_user)
):
    """Get job result storage statistics"""
    try:
        stats = job_storage.get_storage_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get storage stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get storage stats: {str(e)}")


@router.post("/cleanup")
async def cleanup_old_data(
    current_user: dict = Depends(get_current_user)
):
    """Manually trigger cleanup of old job data"""
    try:
        # Cleanup monitoring data
        job_monitor.cleanup_old_data()
        
        # Cleanup storage data
        cleanup_stats = job_storage.cleanup_old_results()
        
        return {
            'message': 'Cleanup completed successfully',
            'cleanup_stats': cleanup_stats
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup old data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup old data: {str(e)}") 