#!/usr/bin/env python3
"""
Celery Worker Management Script (Task 3.1.1)

This script provides utilities for managing Celery workers, including
starting workers with different configurations, monitoring, and health checks.
"""

import os
import sys
import signal
import subprocess
import time
import json
from typing import Dict, List, Optional
from datetime import datetime
import argparse

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workers.celery_app import celery_app
from lib.logger import logger


class WorkerManager:
    """Manages Celery workers for the AIR MVP system"""
    
    def __init__(self):
        self.workers = {}
        self.worker_configs = {
            'high_priority': {
                'queues': ['high_priority'],
                'concurrency': 2,
                'max_tasks_per_child': 100,
                'description': 'High priority tasks (tokens, alerts, notifications)'
            },
            'default': {
                'queues': ['default'],
                'concurrency': 4,
                'max_tasks_per_child': 200,
                'description': 'Default priority tasks (contacts, interactions, sync)'
            },
            'ai_tasks': {
                'queues': ['ai_tasks'],
                'concurrency': 2,
                'max_tasks_per_child': 50,
                'description': 'AI processing tasks (analysis, generation)'
            },
            'data_pipeline': {
                'queues': ['data_pipeline'],
                'concurrency': 1,
                'max_tasks_per_child': 20,
                'description': 'Data pipeline tasks (export, bulk operations)'
            },
            'low_priority': {
                'queues': ['low_priority'],
                'concurrency': 1,
                'max_tasks_per_child': 50,
                'description': 'Low priority tasks (analytics, backup, maintenance)'
            },
            'all_queues': {
                'queues': ['high_priority', 'default', 'ai_tasks', 'data_pipeline', 'low_priority'],
                'concurrency': 4,
                'max_tasks_per_child': 100,
                'description': 'All queues worker (development/testing)'
            }
        }
    
    def start_worker(self, worker_name: str, detach: bool = False) -> bool:
        """
        Start a Celery worker
        
        Args:
            worker_name: Name of the worker configuration
            detach: Whether to run in background
            
        Returns:
            bool: True if worker started successfully
        """
        if worker_name not in self.worker_configs:
            logger.error(f"Unknown worker configuration: {worker_name}")
            return False
        
        config = self.worker_configs[worker_name]
        
        # Build celery worker command
        cmd = [
            'celery',
            '-A', 'workers.celery_app',
            'worker',
            '--loglevel=info',
            f'--hostname={worker_name}@%h',
            f'--queues={",".join(config["queues"])}',
            f'--concurrency={config["concurrency"]}',
            f'--max-tasks-per-child={config["max_tasks_per_child"]}',
            '--without-gossip',
            '--without-mingle',
            '--without-heartbeat'
        ]
        
        if detach:
            cmd.append('--detach')
            cmd.extend(['--pidfile', f'/tmp/celery_{worker_name}.pid'])
            cmd.extend(['--logfile', f'/tmp/celery_{worker_name}.log'])
        
        try:
            logger.info(f"Starting worker '{worker_name}': {config['description']}")
            logger.info(f"Command: {' '.join(cmd)}")
            
            if detach:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.workers[worker_name] = process
                logger.info(f"Worker '{worker_name}' started in background (PID: {process.pid})")
            else:
                # Run in foreground
                subprocess.run(cmd, check=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start worker '{worker_name}': {e}")
            return False
        except KeyboardInterrupt:
            logger.info(f"Worker '{worker_name}' stopped by user")
            return True
    
    def stop_worker(self, worker_name: str) -> bool:
        """
        Stop a Celery worker
        
        Args:
            worker_name: Name of the worker to stop
            
        Returns:
            bool: True if worker stopped successfully
        """
        try:
            # Try to stop via pidfile first
            pidfile = f'/tmp/celery_{worker_name}.pid'
            if os.path.exists(pidfile):
                with open(pidfile, 'r') as f:
                    pid = int(f.read().strip())
                
                try:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(2)
                    os.kill(pid, signal.SIGKILL)
                    os.remove(pidfile)
                    logger.info(f"Worker '{worker_name}' stopped (PID: {pid})")
                    return True
                except ProcessLookupError:
                    logger.warning(f"Worker '{worker_name}' process not found")
                    os.remove(pidfile)
            
            # Try to stop via process object
            if worker_name in self.workers:
                process = self.workers[worker_name]
                process.terminate()
                process.wait(timeout=10)
                del self.workers[worker_name]
                logger.info(f"Worker '{worker_name}' stopped")
                return True
            
            logger.warning(f"Worker '{worker_name}' not found")
            return False
            
        except Exception as e:
            logger.error(f"Failed to stop worker '{worker_name}': {e}")
            return False
    
    def stop_all_workers(self) -> bool:
        """Stop all running workers"""
        success = True
        
        # Stop workers managed by this instance
        for worker_name in list(self.workers.keys()):
            if not self.stop_worker(worker_name):
                success = False
        
        # Stop workers via pidfiles
        for worker_name in self.worker_configs.keys():
            pidfile = f'/tmp/celery_{worker_name}.pid'
            if os.path.exists(pidfile):
                if not self.stop_worker(worker_name):
                    success = False
        
        return success
    
    def list_workers(self) -> Dict[str, Dict]:
        """List all available worker configurations"""
        return self.worker_configs
    
    def worker_status(self, worker_name: str = None) -> Dict:
        """
        Get worker status
        
        Args:
            worker_name: Specific worker name (if None, get all)
            
        Returns:
            Dict: Worker status information
        """
        try:
            # Use celery inspect to get worker status
            inspect = celery_app.control.inspect()
            
            status = {
                'active_tasks': inspect.active() or {},
                'scheduled_tasks': inspect.scheduled() or {},
                'reserved_tasks': inspect.reserved() or {},
                'stats': inspect.stats() or {},
                'registered_tasks': inspect.registered() or {},
                'timestamp': datetime.now().isoformat()
            }
            
            if worker_name:
                # Filter for specific worker
                filtered_status = {}
                for key, value in status.items():
                    if key == 'timestamp':
                        filtered_status[key] = value
                    else:
                        filtered_status[key] = {
                            k: v for k, v in value.items() 
                            if worker_name in k
                        }
                return filtered_status
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get worker status: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    def health_check(self) -> Dict:
        """Perform health check on Celery infrastructure"""
        try:
            # Check broker connection
            broker_status = celery_app.control.inspect().ping()
            
            # Check if workers are responding
            active_workers = list(broker_status.keys()) if broker_status else []
            
            # Get queue lengths (requires Redis inspection)
            queue_info = {}
            try:
                from redis import Redis
                from config import settings
                
                # Parse Redis URL
                redis_url = settings.CELERY_BROKER_URL
                if redis_url.startswith('redis://'):
                    redis_client = Redis.from_url(redis_url)
                    
                    for queue_name in ['high_priority', 'default', 'ai_tasks', 'data_pipeline', 'low_priority']:
                        queue_length = redis_client.llen(queue_name)
                        queue_info[queue_name] = queue_length
                        
            except Exception as e:
                logger.warning(f"Could not get queue info: {e}")
                queue_info = {'error': 'Could not connect to Redis'}
            
            health_status = {
                'broker_connected': broker_status is not None,
                'active_workers': active_workers,
                'worker_count': len(active_workers),
                'queue_lengths': queue_info,
                'timestamp': datetime.now().isoformat(),
                'status': 'healthy' if broker_status and active_workers else 'unhealthy'
            }
            
            return health_status
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def start_beat_scheduler(self, detach: bool = False) -> bool:
        """
        Start Celery Beat scheduler for periodic tasks
        
        Args:
            detach: Whether to run in background
            
        Returns:
            bool: True if scheduler started successfully
        """
        cmd = [
            'celery',
            '-A', 'workers.celery_app',
            'beat',
            '--loglevel=info'
        ]
        
        if detach:
            cmd.append('--detach')
            cmd.extend(['--pidfile', '/tmp/celery_beat.pid'])
            cmd.extend(['--logfile', '/tmp/celery_beat.log'])
        
        try:
            logger.info("Starting Celery Beat scheduler")
            logger.info(f"Command: {' '.join(cmd)}")
            
            if detach:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                logger.info(f"Beat scheduler started in background (PID: {process.pid})")
            else:
                subprocess.run(cmd, check=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start beat scheduler: {e}")
            return False
        except KeyboardInterrupt:
            logger.info("Beat scheduler stopped by user")
            return True
    
    def stop_beat_scheduler(self) -> bool:
        """Stop Celery Beat scheduler"""
        try:
            pidfile = '/tmp/celery_beat.pid'
            if os.path.exists(pidfile):
                with open(pidfile, 'r') as f:
                    pid = int(f.read().strip())
                
                try:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(2)
                    os.kill(pid, signal.SIGKILL)
                    os.remove(pidfile)
                    logger.info(f"Beat scheduler stopped (PID: {pid})")
                    return True
                except ProcessLookupError:
                    logger.warning("Beat scheduler process not found")
                    os.remove(pidfile)
                    return True
            
            logger.warning("Beat scheduler not running")
            return False
            
        except Exception as e:
            logger.error(f"Failed to stop beat scheduler: {e}")
            return False
    
    def monitor_workers(self, interval: int = 30) -> None:
        """
        Monitor workers continuously
        
        Args:
            interval: Monitoring interval in seconds
        """
        logger.info(f"Starting worker monitoring (interval: {interval}s)")
        
        try:
            while True:
                status = self.worker_status()
                health = self.health_check()
                
                print(f"\n{'='*60}")
                print(f"Worker Status - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*60}")
                
                print(f"Health Status: {health['status'].upper()}")
                print(f"Active Workers: {health['worker_count']}")
                print(f"Workers: {', '.join(health['active_workers'])}")
                
                if 'queue_lengths' in health and isinstance(health['queue_lengths'], dict):
                    print("\nQueue Lengths:")
                    for queue, length in health['queue_lengths'].items():
                        print(f"  {queue}: {length}")
                
                if status.get('active_tasks'):
                    print(f"\nActive Tasks: {sum(len(tasks) for tasks in status['active_tasks'].values())}")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description='Celery Worker Manager for AIR MVP')
    parser.add_argument('command', choices=[
        'start', 'stop', 'restart', 'status', 'health', 'list', 'monitor', 
        'start-beat', 'stop-beat', 'stop-all'
    ], help='Command to execute')
    parser.add_argument('--worker', '-w', help='Worker name (for start/stop/status commands)')
    parser.add_argument('--detach', '-d', action='store_true', help='Run in background')
    parser.add_argument('--interval', '-i', type=int, default=30, help='Monitoring interval (seconds)')
    
    args = parser.parse_args()
    
    manager = WorkerManager()
    
    if args.command == 'list':
        print("Available Worker Configurations:")
        print("=" * 50)
        for name, config in manager.list_workers().items():
            print(f"\n{name}:")
            print(f"  Queues: {', '.join(config['queues'])}")
            print(f"  Concurrency: {config['concurrency']}")
            print(f"  Max Tasks/Child: {config['max_tasks_per_child']}")
            print(f"  Description: {config['description']}")
    
    elif args.command == 'start':
        if not args.worker:
            print("Error: --worker is required for start command")
            sys.exit(1)
        
        success = manager.start_worker(args.worker, args.detach)
        sys.exit(0 if success else 1)
    
    elif args.command == 'stop':
        if not args.worker:
            print("Error: --worker is required for stop command")
            sys.exit(1)
        
        success = manager.stop_worker(args.worker)
        sys.exit(0 if success else 1)
    
    elif args.command == 'stop-all':
        success = manager.stop_all_workers()
        sys.exit(0 if success else 1)
    
    elif args.command == 'restart':
        if not args.worker:
            print("Error: --worker is required for restart command")
            sys.exit(1)
        
        manager.stop_worker(args.worker)
        time.sleep(2)
        success = manager.start_worker(args.worker, args.detach)
        sys.exit(0 if success else 1)
    
    elif args.command == 'status':
        status = manager.worker_status(args.worker)
        print(json.dumps(status, indent=2))
    
    elif args.command == 'health':
        health = manager.health_check()
        print(json.dumps(health, indent=2))
    
    elif args.command == 'monitor':
        manager.monitor_workers(args.interval)
    
    elif args.command == 'start-beat':
        success = manager.start_beat_scheduler(args.detach)
        sys.exit(0 if success else 1)
    
    elif args.command == 'stop-beat':
        success = manager.stop_beat_scheduler()
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main() 