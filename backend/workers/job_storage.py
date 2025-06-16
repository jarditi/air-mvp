"""
Job Result Storage Service (Task 3.1.4)

This module provides persistent storage and retrieval for Celery job results,
with support for different storage backends and result lifecycle management.
"""

import os
import sys
import json
import pickle
import gzip
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Union
from enum import Enum
from dataclasses import dataclass, asdict
import redis
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Text, Integer, Boolean, LargeBinary

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.database import Base, SessionLocal
from lib.logger import logger
from config import settings


class ResultStatus(Enum):
    """Job result status enumeration"""
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    REVOKED = "REVOKED"
    RETRY = "RETRY"


class StorageBackend(Enum):
    """Storage backend types"""
    REDIS = "redis"
    DATABASE = "database"
    HYBRID = "hybrid"  # Redis for recent, DB for historical


@dataclass
class JobResult:
    """Job result data structure"""
    task_id: str
    task_name: str
    status: ResultStatus
    result: Any = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = None
    retry_count: int = 0
    worker_name: Optional[str] = None
    args: Optional[tuple] = None
    kwargs: Optional[dict] = None
    metadata: Optional[dict] = None


class JobResultModel(Base):
    """SQLAlchemy model for job results"""
    __tablename__ = "job_results"
    
    task_id = Column(String(255), primary_key=True)
    task_name = Column(String(255), nullable=False, index=True)
    status = Column(String(50), nullable=False, index=True)
    result_data = Column(LargeBinary)  # Compressed JSON/pickle data
    error_message = Column(Text)
    traceback = Column(Text)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True), index=True)
    execution_time = Column(Integer)  # Milliseconds
    retry_count = Column(Integer, default=0)
    worker_name = Column(String(255))
    args_data = Column(LargeBinary)  # Compressed args
    kwargs_data = Column(LargeBinary)  # Compressed kwargs
    metadata_data = Column(Text)  # JSON metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class JobResultStorage:
    """Comprehensive job result storage and retrieval service"""
    
    def __init__(self, backend: StorageBackend = StorageBackend.HYBRID):
        self.backend = backend
        self.redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL) if backend in [StorageBackend.REDIS, StorageBackend.HYBRID] else None
        self.redis_ttl = 86400 * 7  # 7 days in Redis
        self.db_retention_days = 30  # 30 days in database
        
        logger.info(f"JobResultStorage initialized with backend: {backend.value}")
    
    def store_result(self, job_result: JobResult) -> bool:
        """Store job result using configured backend"""
        try:
            if self.backend == StorageBackend.REDIS:
                return self._store_in_redis(job_result)
            elif self.backend == StorageBackend.DATABASE:
                return self._store_in_database(job_result)
            elif self.backend == StorageBackend.HYBRID:
                # Store in both Redis (for fast access) and Database (for persistence)
                redis_success = self._store_in_redis(job_result)
                db_success = self._store_in_database(job_result)
                return redis_success or db_success  # Success if either succeeds
            
            return False
        except Exception as e:
            logger.error(f"Failed to store job result {job_result.task_id}: {e}")
            return False
    
    def get_result(self, task_id: str) -> Optional[JobResult]:
        """Retrieve job result by task ID"""
        try:
            if self.backend == StorageBackend.REDIS:
                return self._get_from_redis(task_id)
            elif self.backend == StorageBackend.DATABASE:
                return self._get_from_database(task_id)
            elif self.backend == StorageBackend.HYBRID:
                # Try Redis first (faster), then database
                result = self._get_from_redis(task_id)
                if result is None:
                    result = self._get_from_database(task_id)
                return result
            
            return None
        except Exception as e:
            logger.error(f"Failed to get job result {task_id}: {e}")
            return None
    
    def get_results_by_task_name(self, task_name: str, limit: int = 100, status: Optional[ResultStatus] = None) -> List[JobResult]:
        """Get job results by task name"""
        try:
            if self.backend == StorageBackend.DATABASE or self.backend == StorageBackend.HYBRID:
                return self._get_from_database_by_task_name(task_name, limit, status)
            elif self.backend == StorageBackend.REDIS:
                return self._get_from_redis_by_pattern(f"result:{task_name}:*", limit, status)
            
            return []
        except Exception as e:
            logger.error(f"Failed to get results for task {task_name}: {e}")
            return []
    
    def get_recent_results(self, hours: int = 24, limit: int = 100) -> List[JobResult]:
        """Get recent job results"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            if self.backend == StorageBackend.DATABASE or self.backend == StorageBackend.HYBRID:
                return self._get_recent_from_database(cutoff_time, limit)
            elif self.backend == StorageBackend.REDIS:
                return self._get_recent_from_redis(cutoff_time, limit)
            
            return []
        except Exception as e:
            logger.error(f"Failed to get recent results: {e}")
            return []
    
    def get_failed_results(self, hours: int = 24, limit: int = 50) -> List[JobResult]:
        """Get failed job results for analysis"""
        return self.get_results_by_status(ResultStatus.FAILURE, hours, limit)
    
    def get_results_by_status(self, status: ResultStatus, hours: int = 24, limit: int = 100) -> List[JobResult]:
        """Get job results by status"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            if self.backend == StorageBackend.DATABASE or self.backend == StorageBackend.HYBRID:
                db = SessionLocal()
                try:
                    query = db.query(JobResultModel).filter(
                        JobResultModel.status == status.value,
                        JobResultModel.completed_at >= cutoff_time
                    ).order_by(JobResultModel.completed_at.desc()).limit(limit)
                    
                    results = []
                    for row in query.all():
                        job_result = self._model_to_job_result(row)
                        if job_result:
                            results.append(job_result)
                    
                    return results
                finally:
                    db.close()
            
            return []
        except Exception as e:
            logger.error(f"Failed to get results by status {status.value}: {e}")
            return []
    
    def delete_result(self, task_id: str) -> bool:
        """Delete job result"""
        try:
            success = True
            
            if self.backend in [StorageBackend.REDIS, StorageBackend.HYBRID]:
                redis_success = self.redis_client.delete(f"result:{task_id}") > 0
                success = success and redis_success
            
            if self.backend in [StorageBackend.DATABASE, StorageBackend.HYBRID]:
                db = SessionLocal()
                try:
                    deleted = db.query(JobResultModel).filter(
                        JobResultModel.task_id == task_id
                    ).delete()
                    db.commit()
                    db_success = deleted > 0
                    success = success and db_success
                finally:
                    db.close()
            
            return success
        except Exception as e:
            logger.error(f"Failed to delete job result {task_id}: {e}")
            return False
    
    def cleanup_old_results(self) -> Dict[str, int]:
        """Clean up old job results"""
        try:
            cleanup_stats = {'redis_deleted': 0, 'db_deleted': 0}
            
            # Clean up Redis (older than redis_ttl)
            if self.backend in [StorageBackend.REDIS, StorageBackend.HYBRID]:
                cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=self.redis_ttl)
                redis_deleted = self._cleanup_redis_results(cutoff_time)
                cleanup_stats['redis_deleted'] = redis_deleted
            
            # Clean up Database (older than db_retention_days)
            if self.backend in [StorageBackend.DATABASE, StorageBackend.HYBRID]:
                cutoff_time = datetime.now(timezone.utc) - timedelta(days=self.db_retention_days)
                db_deleted = self._cleanup_database_results(cutoff_time)
                cleanup_stats['db_deleted'] = db_deleted
            
            logger.info(f"Cleanup completed: {cleanup_stats}")
            return cleanup_stats
        except Exception as e:
            logger.error(f"Failed to cleanup old results: {e}")
            return {'redis_deleted': 0, 'db_deleted': 0}
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        try:
            stats = {
                'backend': self.backend.value,
                'redis_stats': {},
                'database_stats': {}
            }
            
            # Redis stats
            if self.backend in [StorageBackend.REDIS, StorageBackend.HYBRID]:
                redis_keys = self.redis_client.keys("result:*")
                stats['redis_stats'] = {
                    'total_results': len(redis_keys)
                }
            
            # Database stats
            if self.backend in [StorageBackend.DATABASE, StorageBackend.HYBRID]:
                db = SessionLocal()
                try:
                    total_count = db.query(JobResultModel).count()
                    success_count = db.query(JobResultModel).filter(
                        JobResultModel.status == ResultStatus.SUCCESS.value
                    ).count()
                    failure_count = db.query(JobResultModel).filter(
                        JobResultModel.status == ResultStatus.FAILURE.value
                    ).count()
                    
                    stats['database_stats'] = {
                        'total_results': total_count,
                        'success_count': success_count,
                        'failure_count': failure_count,
                        'success_rate': success_count / total_count if total_count > 0 else 0
                    }
                finally:
                    db.close()
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {'backend': self.backend.value, 'error': str(e)}
    
    def _store_in_redis(self, job_result: JobResult) -> bool:
        """Store job result in Redis"""
        try:
            key = f"result:{job_result.task_id}"
            data = self._serialize_job_result(job_result)
            
            # Store with TTL
            self.redis_client.setex(key, self.redis_ttl, data)
            return True
        except Exception as e:
            logger.error(f"Failed to store in Redis: {e}")
            return False
    
    def _store_in_database(self, job_result: JobResult) -> bool:
        """Store job result in database"""
        try:
            db = SessionLocal()
            try:
                # Check if result already exists
                existing = db.query(JobResultModel).filter(
                    JobResultModel.task_id == job_result.task_id
                ).first()
                
                if existing:
                    # Update existing record
                    self._update_model_from_job_result(existing, job_result)
                else:
                    # Create new record
                    model = self._job_result_to_model(job_result)
                    db.add(model)
                
                db.commit()
                return True
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to store in database: {e}")
            return False
    
    def _get_from_redis(self, task_id: str) -> Optional[JobResult]:
        """Get job result from Redis"""
        try:
            key = f"result:{task_id}"
            data = self.redis_client.get(key)
            
            if data:
                return self._deserialize_job_result(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get from Redis: {e}")
            return None
    
    def _get_from_database(self, task_id: str) -> Optional[JobResult]:
        """Get job result from database"""
        try:
            db = SessionLocal()
            try:
                model = db.query(JobResultModel).filter(
                    JobResultModel.task_id == task_id
                ).first()
                
                if model:
                    return self._model_to_job_result(model)
                return None
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to get from database: {e}")
            return None
    
    def _get_from_database_by_task_name(self, task_name: str, limit: int, status: Optional[ResultStatus]) -> List[JobResult]:
        """Get job results from database by task name"""
        try:
            db = SessionLocal()
            try:
                query = db.query(JobResultModel).filter(
                    JobResultModel.task_name == task_name
                )
                
                if status:
                    query = query.filter(JobResultModel.status == status.value)
                
                query = query.order_by(JobResultModel.completed_at.desc()).limit(limit)
                
                results = []
                for row in query.all():
                    job_result = self._model_to_job_result(row)
                    if job_result:
                        results.append(job_result)
                
                return results
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to get from database by task name: {e}")
            return []
    
    def _get_recent_from_database(self, cutoff_time: datetime, limit: int) -> List[JobResult]:
        """Get recent job results from database"""
        try:
            db = SessionLocal()
            try:
                query = db.query(JobResultModel).filter(
                    JobResultModel.completed_at >= cutoff_time
                ).order_by(JobResultModel.completed_at.desc()).limit(limit)
                
                results = []
                for row in query.all():
                    job_result = self._model_to_job_result(row)
                    if job_result:
                        results.append(job_result)
                
                return results
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to get recent from database: {e}")
            return []
    
    def _cleanup_database_results(self, cutoff_time: datetime) -> int:
        """Clean up old database results"""
        try:
            db = SessionLocal()
            try:
                deleted = db.query(JobResultModel).filter(
                    JobResultModel.completed_at < cutoff_time
                ).delete()
                db.commit()
                return deleted
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to cleanup database results: {e}")
            return 0
    
    def _serialize_job_result(self, job_result: JobResult) -> bytes:
        """Serialize job result for storage"""
        data = asdict(job_result)
        
        # Convert datetime objects to ISO strings
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, ResultStatus):
                data[key] = value.value
        
        # Compress the data
        json_data = json.dumps(data).encode('utf-8')
        return gzip.compress(json_data)
    
    def _deserialize_job_result(self, data: bytes) -> JobResult:
        """Deserialize job result from storage"""
        # Decompress the data
        json_data = gzip.decompress(data).decode('utf-8')
        data_dict = json.loads(json_data)
        
        # Convert ISO strings back to datetime objects
        for key in ['started_at', 'completed_at']:
            if data_dict.get(key):
                data_dict[key] = datetime.fromisoformat(data_dict[key])
        
        # Convert status string back to enum
        if data_dict.get('status'):
            data_dict['status'] = ResultStatus(data_dict['status'])
        
        return JobResult(**data_dict)
    
    def _job_result_to_model(self, job_result: JobResult) -> JobResultModel:
        """Convert JobResult to SQLAlchemy model"""
        model = JobResultModel(
            task_id=job_result.task_id,
            task_name=job_result.task_name,
            status=job_result.status.value,
            error_message=job_result.error,
            traceback=job_result.traceback,
            started_at=job_result.started_at,
            completed_at=job_result.completed_at,
            execution_time=int(job_result.execution_time * 1000) if job_result.execution_time else None,
            retry_count=job_result.retry_count,
            worker_name=job_result.worker_name
        )
        
        # Compress and store complex data
        if job_result.result is not None:
            model.result_data = gzip.compress(pickle.dumps(job_result.result))
        
        if job_result.args:
            model.args_data = gzip.compress(pickle.dumps(job_result.args))
        
        if job_result.kwargs:
            model.kwargs_data = gzip.compress(pickle.dumps(job_result.kwargs))
        
        if job_result.metadata:
            model.metadata_data = json.dumps(job_result.metadata)
        
        return model
    
    def _model_to_job_result(self, model: JobResultModel) -> Optional[JobResult]:
        """Convert SQLAlchemy model to JobResult"""
        try:
            # Decompress complex data
            result = None
            if model.result_data:
                result = pickle.loads(gzip.decompress(model.result_data))
            
            args = None
            if model.args_data:
                args = pickle.loads(gzip.decompress(model.args_data))
            
            kwargs = None
            if model.kwargs_data:
                kwargs = pickle.loads(gzip.decompress(model.kwargs_data))
            
            metadata = None
            if model.metadata_data:
                metadata = json.loads(model.metadata_data)
            
            execution_time = None
            if model.execution_time:
                execution_time = model.execution_time / 1000.0  # Convert back to seconds
            
            return JobResult(
                task_id=model.task_id,
                task_name=model.task_name,
                status=ResultStatus(model.status),
                result=result,
                error=model.error_message,
                traceback=model.traceback,
                started_at=model.started_at,
                completed_at=model.completed_at,
                execution_time=execution_time,
                retry_count=model.retry_count,
                worker_name=model.worker_name,
                args=args,
                kwargs=kwargs,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Failed to convert model to job result: {e}")
            return None
    
    def _update_model_from_job_result(self, model: JobResultModel, job_result: JobResult):
        """Update existing model with job result data"""
        model.status = job_result.status.value
        model.error_message = job_result.error
        model.traceback = job_result.traceback
        model.completed_at = job_result.completed_at
        model.execution_time = int(job_result.execution_time * 1000) if job_result.execution_time else None
        model.retry_count = job_result.retry_count
        model.worker_name = job_result.worker_name
        model.updated_at = datetime.now(timezone.utc)
        
        # Update compressed data
        if job_result.result is not None:
            model.result_data = gzip.compress(pickle.dumps(job_result.result))
        
        if job_result.metadata:
            model.metadata_data = json.dumps(job_result.metadata)


# Global job result storage instance
job_storage = JobResultStorage(StorageBackend.HYBRID) 