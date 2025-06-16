#!/usr/bin/env python3
"""
Celery Setup Test Script (Task 3.1.1)

This script tests the complete Celery infrastructure to ensure
all workers, queues, and tasks are functioning correctly.
"""

import asyncio
import time
import json
from datetime import datetime, timezone
from typing import Dict, List, Any

from workers.celery_app import celery_app, debug_task
from workers.tasks import (
    token_refresh_task,
    critical_alert_task,
    user_notification_task,
    contact_processing_task,
    interaction_analysis_task,
    relationship_scoring_task,
    ai_analysis_task,
    data_export_task,
    analytics_task
)
from lib.logger import logger


class CelerySetupTester:
    """Test suite for Celery infrastructure"""
    
    def __init__(self):
        self.test_results = []
        self.failed_tests = []
    
    def log_test_result(self, test_name: str, success: bool, details: str = "", duration: float = 0):
        """Log test result"""
        result = {
            'test_name': test_name,
            'success': success,
            'details': details,
            'duration': duration,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        self.test_results.append(result)
        
        if success:
            print(f"✅ {test_name} - {details} ({duration:.2f}s)")
        else:
            print(f"❌ {test_name} - {details} ({duration:.2f}s)")
            self.failed_tests.append(result)
    
    def test_broker_connection(self) -> bool:
        """Test Redis broker connection"""
        start_time = time.time()
        
        try:
            # Test broker connection via ping
            inspect = celery_app.control.inspect()
            result = inspect.ping()
            
            duration = time.time() - start_time
            
            if result:
                self.log_test_result(
                    "Broker Connection", 
                    True, 
                    f"Connected to Redis broker, {len(result)} workers responding",
                    duration
                )
                return True
            else:
                self.log_test_result(
                    "Broker Connection", 
                    False, 
                    "No workers responding to ping",
                    duration
                )
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result(
                "Broker Connection", 
                False, 
                f"Connection failed: {str(e)}",
                duration
            )
            return False
    
    def test_worker_registration(self) -> bool:
        """Test that workers are registered and responding"""
        start_time = time.time()
        
        try:
            inspect = celery_app.control.inspect()
            
            # Get active workers
            active_workers = inspect.active()
            registered_tasks = inspect.registered()
            
            duration = time.time() - start_time
            
            if active_workers and registered_tasks:
                worker_count = len(active_workers)
                task_count = sum(len(tasks) for tasks in registered_tasks.values())
                
                self.log_test_result(
                    "Worker Registration", 
                    True, 
                    f"{worker_count} workers active, {task_count} tasks registered",
                    duration
                )
                
                # Log worker details
                for worker_name in active_workers.keys():
                    print(f"  📋 Worker: {worker_name}")
                
                return True
            else:
                self.log_test_result(
                    "Worker Registration", 
                    False, 
                    "No active workers or registered tasks found",
                    duration
                )
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result(
                "Worker Registration", 
                False, 
                f"Registration check failed: {str(e)}",
                duration
            )
            return False
    
    def test_queue_configuration(self) -> bool:
        """Test queue configuration"""
        start_time = time.time()
        
        try:
            # Test Redis queue inspection
            from redis import Redis
            from config import settings
            
            redis_client = Redis.from_url(settings.CELERY_BROKER_URL)
            
            expected_queues = ['high_priority', 'default', 'ai_tasks', 'data_pipeline', 'low_priority']
            queue_info = {}
            
            for queue_name in expected_queues:
                try:
                    # Check if queue exists (length will be 0 if empty but exists)
                    length = redis_client.llen(queue_name)
                    queue_info[queue_name] = length
                except Exception as e:
                    queue_info[queue_name] = f"Error: {str(e)}"
            
            duration = time.time() - start_time
            
            # All queues should be accessible
            accessible_queues = [q for q, info in queue_info.items() if isinstance(info, int)]
            
            if len(accessible_queues) == len(expected_queues):
                self.log_test_result(
                    "Queue Configuration", 
                    True, 
                    f"All {len(expected_queues)} queues accessible",
                    duration
                )
                
                # Log queue details
                for queue, length in queue_info.items():
                    print(f"  📬 Queue {queue}: {length} messages")
                
                return True
            else:
                self.log_test_result(
                    "Queue Configuration", 
                    False, 
                    f"Only {len(accessible_queues)}/{len(expected_queues)} queues accessible",
                    duration
                )
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result(
                "Queue Configuration", 
                False, 
                f"Queue check failed: {str(e)}",
                duration
            )
            return False
    
    def test_task_execution(self) -> bool:
        """Test basic task execution"""
        start_time = time.time()
        
        try:
            # Test debug task
            result = debug_task.delay()
            
            # Wait for result with timeout
            task_result = result.get(timeout=30)
            
            duration = time.time() - start_time
            
            if task_result and task_result.get('status') == 'success':
                self.log_test_result(
                    "Task Execution", 
                    True, 
                    f"Debug task executed successfully, worker_id: {task_result.get('worker_id', 'unknown')}",
                    duration
                )
                return True
            else:
                self.log_test_result(
                    "Task Execution", 
                    False, 
                    f"Debug task failed or returned unexpected result: {task_result}",
                    duration
                )
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result(
                "Task Execution", 
                False, 
                f"Task execution failed: {str(e)}",
                duration
            )
            return False
    
    def test_high_priority_tasks(self) -> bool:
        """Test high priority task queue"""
        start_time = time.time()
        
        try:
            # Test critical alert task
            result = critical_alert_task.delay(
                alert_type="test_alert",
                user_id="test_user_123",
                message="Test critical alert from Celery setup test",
                metadata={"test": True}
            )
            
            task_result = result.get(timeout=30)
            
            duration = time.time() - start_time
            
            if task_result and task_result.get('status') == 'sent':
                self.log_test_result(
                    "High Priority Tasks", 
                    True, 
                    f"Critical alert task executed, alert_id: {task_result.get('alert_id')}",
                    duration
                )
                return True
            else:
                self.log_test_result(
                    "High Priority Tasks", 
                    False, 
                    f"Critical alert task failed: {task_result}",
                    duration
                )
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result(
                "High Priority Tasks", 
                False, 
                f"High priority task test failed: {str(e)}",
                duration
            )
            return False
    
    def test_default_priority_tasks(self) -> bool:
        """Test default priority task queue"""
        start_time = time.time()
        
        try:
            # Test contact processing task
            result = contact_processing_task.delay(
                user_id="test_user_123",
                contact_ids=["contact_1", "contact_2"],
                operation="score",
                parameters={"test": True}
            )
            
            task_result = result.get(timeout=30)
            
            duration = time.time() - start_time
            
            if task_result and task_result.get('processed_count') == 2:
                self.log_test_result(
                    "Default Priority Tasks", 
                    True, 
                    f"Contact processing task executed, processed {task_result.get('processed_count')} contacts",
                    duration
                )
                return True
            else:
                self.log_test_result(
                    "Default Priority Tasks", 
                    False, 
                    f"Contact processing task failed: {task_result}",
                    duration
                )
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result(
                "Default Priority Tasks", 
                False, 
                f"Default priority task test failed: {str(e)}",
                duration
            )
            return False
    
    def test_ai_tasks(self) -> bool:
        """Test AI task queue"""
        start_time = time.time()
        
        try:
            # Test AI analysis task
            result = ai_analysis_task.delay(
                user_id="test_user_123",
                content_type="email",
                content_ids=["email_1", "email_2"],
                analysis_type="sentiment"
            )
            
            task_result = result.get(timeout=30)
            
            duration = time.time() - start_time
            
            if task_result and task_result.get('analyzed_count') == 2:
                self.log_test_result(
                    "AI Tasks", 
                    True, 
                    f"AI analysis task executed, analyzed {task_result.get('analyzed_count')} items",
                    duration
                )
                return True
            else:
                self.log_test_result(
                    "AI Tasks", 
                    False, 
                    f"AI analysis task failed: {task_result}",
                    duration
                )
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result(
                "AI Tasks", 
                False, 
                f"AI task test failed: {str(e)}",
                duration
            )
            return False
    
    def test_data_pipeline_tasks(self) -> bool:
        """Test data pipeline task queue"""
        start_time = time.time()
        
        try:
            # Test data export task
            result = data_export_task.delay(
                user_id="test_user_123",
                export_type="contacts",
                export_format="json",
                filters={"test": True}
            )
            
            task_result = result.get(timeout=30)
            
            duration = time.time() - start_time
            
            if task_result and task_result.get('export_url'):
                self.log_test_result(
                    "Data Pipeline Tasks", 
                    True, 
                    f"Data export task executed, export_url: {task_result.get('export_url')}",
                    duration
                )
                return True
            else:
                self.log_test_result(
                    "Data Pipeline Tasks", 
                    False, 
                    f"Data export task failed: {task_result}",
                    duration
                )
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result(
                "Data Pipeline Tasks", 
                False, 
                f"Data pipeline task test failed: {str(e)}",
                duration
            )
            return False
    
    def test_low_priority_tasks(self) -> bool:
        """Test low priority task queue"""
        start_time = time.time()
        
        try:
            # Test analytics task
            result = analytics_task.delay(
                user_id="test_user_123",
                analytics_type="daily"
            )
            
            task_result = result.get(timeout=30)
            
            duration = time.time() - start_time
            
            if task_result and task_result.get('analytics_type') == 'daily':
                self.log_test_result(
                    "Low Priority Tasks", 
                    True, 
                    f"Analytics task executed, type: {task_result.get('analytics_type')}",
                    duration
                )
                return True
            else:
                self.log_test_result(
                    "Low Priority Tasks", 
                    False, 
                    f"Analytics task failed: {task_result}",
                    duration
                )
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result(
                "Low Priority Tasks", 
                False, 
                f"Low priority task test failed: {str(e)}",
                duration
            )
            return False
    
    def test_task_routing(self) -> bool:
        """Test that tasks are routed to correct queues"""
        start_time = time.time()
        
        try:
            # Submit tasks to different queues without waiting for results
            tasks = [
                critical_alert_task.delay("test", "user1", "test message"),
                contact_processing_task.delay("user1", ["c1"], "score"),
                ai_analysis_task.delay("user1", "email", ["e1"], "sentiment"),
                data_export_task.delay("user1", "contacts", "json"),
                analytics_task.delay("user1", "daily")
            ]
            
            # Check task routing via inspection
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active()
            
            duration = time.time() - start_time
            
            if active_tasks:
                # Count tasks by worker/queue
                queue_counts = {}
                for worker_name, worker_tasks in active_tasks.items():
                    queue_name = worker_name.split('@')[0]  # Extract queue from worker name
                    queue_counts[queue_name] = queue_counts.get(queue_name, 0) + len(worker_tasks)
                
                self.log_test_result(
                    "Task Routing", 
                    True, 
                    f"Tasks routed to queues: {queue_counts}",
                    duration
                )
                
                # Clean up - revoke pending tasks
                for task in tasks:
                    try:
                        celery_app.control.revoke(task.id, terminate=True)
                    except:
                        pass
                
                return True
            else:
                self.log_test_result(
                    "Task Routing", 
                    False, 
                    "No active tasks found during routing test",
                    duration
                )
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result(
                "Task Routing", 
                False, 
                f"Task routing test failed: {str(e)}",
                duration
            )
            return False
    
    def test_periodic_tasks(self) -> bool:
        """Test periodic task configuration"""
        start_time = time.time()
        
        try:
            # Check beat schedule configuration
            beat_schedule = celery_app.conf.beat_schedule
            
            duration = time.time() - start_time
            
            if beat_schedule:
                scheduled_count = len(beat_schedule)
                self.log_test_result(
                    "Periodic Tasks", 
                    True, 
                    f"{scheduled_count} periodic tasks configured",
                    duration
                )
                
                # Log scheduled tasks
                for task_name, config in beat_schedule.items():
                    print(f"  ⏰ {task_name}: {config['task']} ({config['schedule']})")
                
                return True
            else:
                self.log_test_result(
                    "Periodic Tasks", 
                    False, 
                    "No periodic tasks configured",
                    duration
                )
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result(
                "Periodic Tasks", 
                False, 
                f"Periodic task check failed: {str(e)}",
                duration
            )
            return False
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all Celery setup tests"""
        print("🧪 Starting Celery Setup Tests")
        print("=" * 60)
        
        start_time = time.time()
        
        # Run all tests
        tests = [
            self.test_broker_connection,
            self.test_worker_registration,
            self.test_queue_configuration,
            self.test_task_execution,
            self.test_high_priority_tasks,
            self.test_default_priority_tasks,
            self.test_ai_tasks,
            self.test_data_pipeline_tasks,
            self.test_low_priority_tasks,
            self.test_task_routing,
            self.test_periodic_tasks
        ]
        
        passed_tests = 0
        for test_func in tests:
            try:
                if test_func():
                    passed_tests += 1
            except Exception as e:
                print(f"❌ {test_func.__name__} - Unexpected error: {str(e)}")
        
        total_duration = time.time() - start_time
        
        # Generate summary
        summary = {
            'total_tests': len(tests),
            'passed_tests': passed_tests,
            'failed_tests': len(tests) - passed_tests,
            'success_rate': (passed_tests / len(tests)) * 100,
            'total_duration': total_duration,
            'test_results': self.test_results,
            'failed_test_details': self.failed_tests,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Print summary
        print("\n" + "=" * 60)
        print("🏁 Test Summary")
        print("=" * 60)
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']} ✅")
        print(f"Failed: {summary['failed_tests']} ❌")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        print(f"Total Duration: {summary['total_duration']:.2f}s")
        
        if summary['failed_tests'] > 0:
            print(f"\n❌ Failed Tests:")
            for failed_test in self.failed_tests:
                print(f"  • {failed_test['test_name']}: {failed_test['details']}")
        
        return summary


def main():
    """Main test execution"""
    tester = CelerySetupTester()
    
    try:
        summary = tester.run_all_tests()
        
        # Save results to file
        with open('/tmp/celery_test_results.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: /tmp/celery_test_results.json")
        
        # Exit with appropriate code
        exit_code = 0 if summary['failed_tests'] == 0 else 1
        exit(exit_code)
        
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n💥 Test suite failed with error: {str(e)}")
        exit(1)


if __name__ == '__main__':
    main() 