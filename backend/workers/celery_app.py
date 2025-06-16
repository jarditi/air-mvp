"""
Centralized Celery Application Configuration (Task 3.1.1)

This module provides the main Celery application instance with comprehensive
configuration for background job processing, task routing, and monitoring.
"""

import os
import sys
from celery import Celery
from kombu import Queue, Exchange
from datetime import timedelta

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

# Create Celery application instance
celery_app = Celery('air_mvp')

# Celery Configuration
celery_app.conf.update(
    # Broker and Backend
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,
    
    # Serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Timezone and UTC
    timezone='UTC',
    enable_utc=True,
    
    # Task Execution
    task_track_started=True,
    task_time_limit=1800,  # 30 minutes max
    task_soft_time_limit=1500,  # 25 minutes soft limit
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Worker Configuration
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    
    # Compression
    task_compression='gzip',
    result_compression='gzip',
    
    # Result Backend Settings
    result_expires=3600,  # 1 hour
    result_persistent=True,
    
    # Task Routes and Queues
    task_routes={
        # High Priority Tasks
        'workers.tasks.token_refresh_task': {'queue': 'high_priority'},
        'workers.tasks.critical_alert_task': {'queue': 'high_priority'},
        'workers.tasks.user_notification_task': {'queue': 'high_priority'},
        
        # Default Priority Tasks
        'workers.tasks.contact_processing_task': {'queue': 'default'},
        'workers.tasks.interaction_analysis_task': {'queue': 'default'},
        'workers.tasks.relationship_scoring_task': {'queue': 'default'},
        'workers.tasks.email_sync_task': {'queue': 'default'},
        'workers.tasks.calendar_sync_task': {'queue': 'default'},
        
        # AI Processing Tasks
        'workers.tasks.ai_analysis_task': {'queue': 'ai_tasks'},
        'workers.tasks.interest_extraction_task': {'queue': 'ai_tasks'},
        'workers.tasks.briefing_generation_task': {'queue': 'ai_tasks'},
        'workers.tasks.message_generation_task': {'queue': 'ai_tasks'},
        
        # Data Pipeline Tasks
        'workers.tasks.data_export_task': {'queue': 'data_pipeline'},
        'workers.tasks.bulk_operation_task': {'queue': 'data_pipeline'},
        'workers.tasks.deduplication_task': {'queue': 'data_pipeline'},
        'workers.tasks.data_cleanup_task': {'queue': 'data_pipeline'},
        
        # Low Priority Tasks
        'workers.tasks.analytics_task': {'queue': 'low_priority'},
        'workers.tasks.backup_task': {'queue': 'low_priority'},
        'workers.tasks.maintenance_task': {'queue': 'low_priority'},
    },
    
    # Queue Configuration
    task_default_queue='default',
    task_default_exchange='air_mvp',
    task_default_exchange_type='direct',
    task_default_routing_key='default',
    
    # Define Queues with Different Priorities
    task_queues=(
        Queue('high_priority', 
              Exchange('air_mvp', type='direct'), 
              routing_key='high_priority',
              queue_arguments={'x-max-priority': 10}),
        Queue('default', 
              Exchange('air_mvp', type='direct'), 
              routing_key='default',
              queue_arguments={'x-max-priority': 5}),
        Queue('ai_tasks', 
              Exchange('air_mvp', type='direct'), 
              routing_key='ai_tasks',
              queue_arguments={'x-max-priority': 7}),
        Queue('data_pipeline', 
              Exchange('air_mvp', type='direct'), 
              routing_key='data_pipeline',
              queue_arguments={'x-max-priority': 3}),
        Queue('low_priority', 
              Exchange('air_mvp', type='direct'), 
              routing_key='low_priority',
              queue_arguments={'x-max-priority': 1}),
    ),
    
    # Monitoring and Logging
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Error Handling
    task_annotations={
        '*': {
            'rate_limit': '100/m',  # Default rate limit
            'time_limit': 1800,     # 30 minutes
            'soft_time_limit': 1500, # 25 minutes
        },
        'workers.tasks.ai_analysis_task': {
            'rate_limit': '10/m',   # AI tasks are more resource intensive
            'time_limit': 3600,     # 1 hour for AI tasks
            'soft_time_limit': 3300, # 55 minutes
        },
        'workers.tasks.bulk_operation_task': {
            'rate_limit': '5/m',    # Bulk operations are heavy
            'time_limit': 7200,     # 2 hours for bulk operations
            'soft_time_limit': 6900, # 1h 55m
        },
    },
)

# Periodic Task Schedule (Celery Beat)
celery_app.conf.beat_schedule = {
    # Token Management (every 5 minutes)
    'refresh-expiring-tokens': {
        'task': 'workers.tasks.token_refresh_task',
        'schedule': timedelta(minutes=5),
        'options': {'queue': 'high_priority'}
    },
    
    # OAuth Cleanup (every hour)
    'cleanup-expired-oauth-states': {
        'task': 'workers.tasks.oauth_cleanup_task',
        'schedule': timedelta(hours=1),
        'options': {'queue': 'default'}
    },
    
    # Health Checks (every 30 minutes)
    'integration-health-check': {
        'task': 'workers.tasks.integration_health_check_task',
        'schedule': timedelta(minutes=30),
        'options': {'queue': 'default'}
    },
    
    # Relationship Scoring (every 6 hours)
    'update-relationship-scores': {
        'task': 'workers.tasks.relationship_scoring_task',
        'schedule': timedelta(hours=6),
        'options': {'queue': 'default'}
    },
    
    # Data Cleanup (daily at 2 AM)
    'daily-data-cleanup': {
        'task': 'workers.tasks.data_cleanup_task',
        'schedule': timedelta(hours=24),
        'options': {'queue': 'low_priority'}
    },
    
    # Analytics Processing (daily at 3 AM)
    'daily-analytics-processing': {
        'task': 'workers.tasks.analytics_task',
        'schedule': timedelta(hours=24),
        'options': {'queue': 'low_priority'}
    },
    
    # Contact Deduplication (weekly)
    'weekly-deduplication-scan': {
        'task': 'workers.tasks.deduplication_task',
        'schedule': timedelta(days=7),
        'options': {'queue': 'data_pipeline'}
    },
}

# Task Discovery - Auto-discover tasks from workers.tasks module
celery_app.autodiscover_tasks(['workers'])

# Celery Signals for Monitoring
@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery functionality"""
    print(f'Request: {self.request!r}')
    return {'status': 'success', 'worker_id': self.request.id}

# Task Result Storage Configuration
celery_app.conf.result_backend_transport_options = {
    'master_name': 'mymaster',
    'visibility_timeout': 3600,
    'retry_policy': {
        'timeout': 5.0
    }
}

# Error Handling Configuration
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.task_acks_late = True

# Security Configuration
if hasattr(settings, 'CELERY_SECURITY_KEY'):
    celery_app.conf.security_key = settings.CELERY_SECURITY_KEY
    celery_app.conf.security_certificate = settings.CELERY_SECURITY_CERTIFICATE
    celery_app.conf.security_cert_store = settings.CELERY_SECURITY_CERT_STORE

# Development vs Production Configuration
if os.getenv('ENVIRONMENT') == 'development':
    # Development settings
    celery_app.conf.task_always_eager = False  # Set to True for synchronous testing
    celery_app.conf.task_eager_propagates = True
    celery_app.conf.worker_log_level = 'DEBUG'
else:
    # Production settings
    celery_app.conf.worker_log_level = 'INFO'
    celery_app.conf.worker_hijack_root_logger = False

# Export the app instance
__all__ = ['celery_app'] 