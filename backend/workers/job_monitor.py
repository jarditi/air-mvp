"""
Job Monitoring and Retry Logic Service (Task 3.1.3)

This module provides comprehensive monitoring, retry logic, and health tracking
for Celery background jobs in the AIR MVP system.
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import redis
from celery import current_app
from celery.result import AsyncResult
from celery.events.state import State

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.logger import logger
from config import settings


class JobStatus(Enum):
    """Job execution status enumeration"""
    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"
    REVOKED = "REVOKED"
    TIMEOUT = "TIMEOUT"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"


class RetryStrategy(Enum):
    """Retry strategy types"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    FIBONACCI = "fibonacci"
    CIRCUIT_BREAKER = "circuit_breaker"


@dataclass
class JobMetrics:
    """Job execution metrics"""
    task_name: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    retry_executions: int = 0
    avg_execution_time: float = 0.0
    last_execution_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None
    failure_rate: float = 0.0
    success_rate: float = 0.0
    
    def update_success(self, execution_time: float):
        """Update metrics for successful execution"""
        self.total_executions += 1
        self.successful_executions += 1
        self.last_execution_time = datetime.now(timezone.utc)
        self.last_success_time = self.last_execution_time
        
        # Update average execution time
        if self.avg_execution_time == 0:
            self.avg_execution_time = execution_time
        else:
            self.avg_execution_time = (self.avg_execution_time + execution_time) / 2
        
        self._calculate_rates()
    
    def update_failure(self):
        """Update metrics for failed execution"""
        self.total_executions += 1
        self.failed_executions += 1
        self.last_execution_time = datetime.now(timezone.utc)
        self.last_failure_time = self.last_execution_time
        self._calculate_rates()
    
    def update_retry(self):
        """Update metrics for retry execution"""
        self.retry_executions += 1
        self.last_execution_time = datetime.now(timezone.utc)
    
    def _calculate_rates(self):
        """Calculate success and failure rates"""
        if self.total_executions > 0:
            self.success_rate = self.successful_executions / self.total_executions
            self.failure_rate = self.failed_executions / self.total_executions


@dataclass
class CircuitBreakerState:
    """Circuit breaker state for task monitoring"""
    task_name: str
    failure_threshold: int = 5
    recovery_timeout: int = 300  # 5 minutes
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    state: str = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def should_allow_execution(self) -> bool:
        """Check if task execution should be allowed"""
        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            if self.last_failure_time and \
               (datetime.now(timezone.utc) - self.last_failure_time).seconds > self.recovery_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        elif self.state == "HALF_OPEN":
            return True
        return False
    
    def record_success(self):
        """Record successful execution"""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def record_failure(self):
        """Record failed execution"""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"


class JobMonitor:
    """Comprehensive job monitoring and retry management service"""
    
    def __init__(self):
        self.redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        self.metrics: Dict[str, JobMetrics] = {}
        self.circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self.job_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.active_jobs: Dict[str, Dict] = {}
        
        # Monitoring configuration
        self.monitoring_enabled = True
        self.metrics_retention_days = 7
        self.history_max_entries = 1000
        
        logger.info("JobMonitor initialized")
    
    def start_job_monitoring(self, task_id: str, task_name: str, args: tuple, kwargs: dict):
        """Start monitoring a job execution"""
        if not self.monitoring_enabled:
            return
        
        job_info = {
            'task_id': task_id,
            'task_name': task_name,
            'args': args,
            'kwargs': kwargs,
            'start_time': datetime.now(timezone.utc),
            'status': JobStatus.STARTED.value,
            'retry_count': 0
        }
        
        self.active_jobs[task_id] = job_info
        
        # Initialize metrics if not exists
        if task_name not in self.metrics:
            self.metrics[task_name] = JobMetrics(task_name=task_name)
        
        # Initialize circuit breaker if not exists
        if task_name not in self.circuit_breakers:
            self.circuit_breakers[task_name] = CircuitBreakerState(task_name=task_name)
        
        # Store in Redis for persistence
        self._store_job_info(task_id, job_info)
        
        logger.info(f"Started monitoring job {task_id} ({task_name})")
    
    def complete_job_monitoring(self, task_id: str, status: JobStatus, result: Any = None, error: str = None):
        """Complete job monitoring with final status"""
        if not self.monitoring_enabled or task_id not in self.active_jobs:
            return
        
        job_info = self.active_jobs[task_id]
        task_name = job_info['task_name']
        
        # Calculate execution time
        start_time = job_info['start_time']
        end_time = datetime.now(timezone.utc)
        execution_time = (end_time - start_time).total_seconds()
        
        # Update job info
        job_info.update({
            'end_time': end_time,
            'execution_time': execution_time,
            'status': status.value,
            'result': result,
            'error': error
        })
        
        # Update metrics
        if status == JobStatus.SUCCESS:
            self.metrics[task_name].update_success(execution_time)
            self.circuit_breakers[task_name].record_success()
        elif status in [JobStatus.FAILURE, JobStatus.TIMEOUT]:
            self.metrics[task_name].update_failure()
            self.circuit_breakers[task_name].record_failure()
        elif status == JobStatus.RETRY:
            self.metrics[task_name].update_retry()
        
        # Add to history
        self.job_history[task_name].append(job_info.copy())
        
        # Store final state in Redis
        self._store_job_info(task_id, job_info)
        
        # Remove from active jobs
        del self.active_jobs[task_id]
        
        logger.info(f"Completed monitoring job {task_id} ({task_name}): {status.value}")
    
    def should_allow_execution(self, task_name: str) -> Tuple[bool, str]:
        """Check if task execution should be allowed based on circuit breaker"""
        if task_name not in self.circuit_breakers:
            return True, "No circuit breaker configured"
        
        circuit_breaker = self.circuit_breakers[task_name]
        allowed = circuit_breaker.should_allow_execution()
        
        if not allowed:
            reason = f"Circuit breaker OPEN for {task_name} (failures: {circuit_breaker.failure_count})"
            return False, reason
        
        return True, "Execution allowed"
    
    def calculate_retry_delay(self, task_name: str, retry_count: int, strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF) -> int:
        """Calculate retry delay based on strategy"""
        base_delay = 60  # 1 minute base delay
        
        if strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            return min(base_delay * (2 ** retry_count), 3600)  # Max 1 hour
        elif strategy == RetryStrategy.LINEAR_BACKOFF:
            return min(base_delay * (retry_count + 1), 1800)  # Max 30 minutes
        elif strategy == RetryStrategy.FIXED_DELAY:
            return base_delay
        elif strategy == RetryStrategy.FIBONACCI:
            fib_sequence = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
            fib_index = min(retry_count, len(fib_sequence) - 1)
            return base_delay * fib_sequence[fib_index]
        else:
            return base_delay
    
    def get_task_metrics(self, task_name: str) -> Optional[JobMetrics]:
        """Get metrics for a specific task"""
        return self.metrics.get(task_name)
    
    def get_all_metrics(self) -> Dict[str, JobMetrics]:
        """Get metrics for all tasks"""
        return self.metrics.copy()
    
    def get_task_history(self, task_name: str, limit: int = 50) -> List[Dict]:
        """Get execution history for a task"""
        history = list(self.job_history.get(task_name, []))
        return history[-limit:] if limit else history
    
    def get_active_jobs(self) -> Dict[str, Dict]:
        """Get currently active jobs"""
        return self.active_jobs.copy()
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics from Redis"""
        try:
            queues = ['high_priority', 'default', 'ai_tasks', 'data_pipeline', 'low_priority']
            stats = {}
            
            for queue in queues:
                queue_length = self.redis_client.llen(queue)
                stats[queue] = {
                    'length': queue_length,
                    'name': queue
                }
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {}
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker statistics"""
        try:
            # Get active workers from Celery
            inspect = current_app.control.inspect()
            active_workers = inspect.active()
            stats = inspect.stats()
            
            worker_info = {}
            if active_workers:
                for worker_name, tasks in active_workers.items():
                    worker_stats = stats.get(worker_name, {}) if stats else {}
                    worker_info[worker_name] = {
                        'active_tasks': len(tasks),
                        'tasks': tasks,
                        'stats': worker_stats
                    }
            
            return worker_info
        except Exception as e:
            logger.error(f"Failed to get worker stats: {e}")
            return {}
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status"""
        try:
            # Check Redis connection
            redis_healthy = self.redis_client.ping()
            
            # Check worker availability
            worker_stats = self.get_worker_stats()
            workers_available = len(worker_stats) > 0
            
            # Check queue lengths
            queue_stats = self.get_queue_stats()
            total_queued = sum(q['length'] for q in queue_stats.values())
            
            # Calculate overall failure rate
            total_failures = sum(m.failed_executions for m in self.metrics.values())
            total_executions = sum(m.total_executions for m in self.metrics.values())
            overall_failure_rate = total_failures / total_executions if total_executions > 0 else 0
            
            # Determine health status
            health_status = "healthy"
            if not redis_healthy or not workers_available:
                health_status = "critical"
            elif overall_failure_rate > 0.1 or total_queued > 1000:
                health_status = "warning"
            
            return {
                'status': health_status,
                'redis_healthy': redis_healthy,
                'workers_available': workers_available,
                'total_queued_jobs': total_queued,
                'overall_failure_rate': overall_failure_rate,
                'active_jobs_count': len(self.active_jobs),
                'circuit_breakers_open': sum(1 for cb in self.circuit_breakers.values() if cb.state == "OPEN"),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get health status: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def cleanup_old_data(self):
        """Clean up old monitoring data"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.metrics_retention_days)
            
            # Clean up job history
            for task_name, history in self.job_history.items():
                # Remove old entries
                while history and history[0]['start_time'] < cutoff_date:
                    history.popleft()
            
            logger.info("Cleaned up old monitoring data")
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
    
    def _store_job_info(self, task_id: str, job_info: Dict):
        """Store job information in Redis"""
        try:
            # Convert datetime objects to ISO strings for JSON serialization
            serializable_info = {}
            for key, value in job_info.items():
                if isinstance(value, datetime):
                    serializable_info[key] = value.isoformat()
                else:
                    serializable_info[key] = value
            
            # Store with expiration (7 days)
            self.redis_client.setex(
                f"job:{task_id}",
                timedelta(days=7),
                json.dumps(serializable_info)
            )
        except Exception as e:
            logger.error(f"Failed to store job info for {task_id}: {e}")
    
    def get_job_info(self, task_id: str) -> Optional[Dict]:
        """Retrieve job information from Redis"""
        try:
            data = self.redis_client.get(f"job:{task_id}")
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get job info for {task_id}: {e}")
            return None


# Global job monitor instance
job_monitor = JobMonitor()


def monitor_task_execution(task_name: str):
    """Decorator to monitor task execution"""
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            task_id = self.request.id
            
            # Check circuit breaker
            allowed, reason = job_monitor.should_allow_execution(task_name)
            if not allowed:
                logger.warning(f"Task {task_name} blocked by circuit breaker: {reason}")
                raise Exception(f"Circuit breaker open: {reason}")
            
            # Start monitoring
            job_monitor.start_job_monitoring(task_id, task_name, args, kwargs)
            
            try:
                # Execute task
                result = func(self, *args, **kwargs)
                
                # Complete monitoring with success
                job_monitor.complete_job_monitoring(task_id, JobStatus.SUCCESS, result)
                return result
                
            except Exception as e:
                # Determine if this is a retry or final failure
                retry_count = getattr(self.request, 'retries', 0)
                max_retries = getattr(self, 'max_retries', 3)
                
                if retry_count < max_retries:
                    # This is a retry
                    job_monitor.complete_job_monitoring(task_id, JobStatus.RETRY, error=str(e))
                    
                    # Calculate retry delay
                    retry_delay = job_monitor.calculate_retry_delay(task_name, retry_count)
                    
                    # Retry with calculated delay
                    raise self.retry(exc=e, countdown=retry_delay)
                else:
                    # Final failure
                    job_monitor.complete_job_monitoring(task_id, JobStatus.FAILURE, error=str(e))
                    raise
        
        return wrapper
    return decorator 