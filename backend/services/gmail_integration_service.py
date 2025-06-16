"""
Gmail Integration Service

This service handles Gmail OAuth integration, email synchronization,
and contact extraction from Gmail messages.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from lib.gmail_client import GmailClient, GmailSyncResult
from lib.google_cloud_config import google_cloud_manager
from models.orm.integration import Integration
from models.orm.user import User
from services.integration_service import IntegrationService
from services.integration_status_service import IntegrationStatusService
from lib.database import get_db
from services.oauth_service import OAuthService
from lib.oauth_client import OAuthProvider
from uuid import UUID

logger = logging.getLogger(__name__)


class GmailIntegrationService:
    """
    Service for managing Gmail integrations and email synchronization
    """
    
    def __init__(self, db: Session):
        """
        Initialize Gmail integration service
        
        Args:
            db: Database session
        """
        self.db = db
        self.integration_service = IntegrationService(db)
        self.status_service = IntegrationStatusService(db)
        self.gmail_client = GmailClient(self.integration_service, self.status_service)
    
    async def initiate_oauth_flow(self, user_id: str, 
                                 redirect_uri: str = None) -> Dict[str, Any]:
        """
        Initiate Gmail OAuth flow
        
        Args:
            user_id: User identifier
            redirect_uri: Optional custom redirect URI
            
        Returns:
            OAuth flow information including authorization URL
        """
        try:
            # Use the proper OAuth service
            oauth_service = OAuthService(self.db)
            
            # Convert user_id to UUID if it's a string
            if isinstance(user_id, str):
                user_uuid = UUID(user_id)
            else:
                user_uuid = user_id
            
            # Use default redirect URI if not provided
            if not redirect_uri:
                redirect_uri = 'http://localhost:8000/auth/google/callback'
            
            # Initiate OAuth flow through the proper service
            auth_url, state = await oauth_service.initiate_oauth_flow(
                user_id=user_uuid,
                provider=OAuthProvider.GOOGLE,
                redirect_uri=redirect_uri,
                scopes=self.gmail_client.SCOPES
            )
            
            oauth_flow_data = {
                'authorization_url': auth_url,
                'state': state,
                'user_id': user_id,
                'provider': 'gmail',
                'scopes': self.gmail_client.SCOPES,
                'initiated_at': datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"Gmail OAuth flow initiated for user {user_id}")
            return oauth_flow_data
            
        except Exception as e:
            logger.error(f"Failed to initiate Gmail OAuth flow: {e}")
            raise
    
    async def handle_oauth_callback(self, user_id: str, code: str, 
                                  state: str = None) -> Integration:
        """
        Handle Gmail OAuth callback and create integration
        
        Args:
            user_id: User identifier
            code: Authorization code from OAuth callback
            state: State parameter for verification
            
        Returns:
            Created Gmail integration
        """
        try:
            # Use the proper OAuth service to complete the flow
            oauth_service = OAuthService(self.db)
            
            # Complete OAuth flow - this validates the state and creates the integration
            integration = await oauth_service.complete_oauth_flow(
                code=code,
                state=state,
                redirect_uri='http://localhost:8000/auth/google/callback'
            )
            
            # Perform initial sync
            await self.perform_initial_sync(integration)
            
            logger.info(f"Gmail integration created successfully for user {user_id}")
            return integration
            
        except Exception as e:
            logger.error(f"Failed to handle Gmail OAuth callback: {e}")
            raise
    
    async def perform_initial_sync(self, integration: Integration) -> GmailSyncResult:
        """
        Perform initial Gmail sync for new integration
        
        Args:
            integration: Gmail integration record
            
        Returns:
            Sync result
        """
        try:
            # Fetch recent messages (last 30 days)
            query = f"newer_than:{30}d"
            
            sync_result = await self.gmail_client.fetch_messages(
                integration=integration,
                query=query,
                max_results=100
            )
            
            # Update integration metadata with sync info
            await self.integration_service.update_integration_metadata(
                integration_id=integration.id,
                metadata_updates={
                    'last_sync_at': datetime.now(timezone.utc).isoformat(),
                    'initial_sync_completed': True,
                    'messages_synced': sync_result.messages_processed,
                    'sync_errors': len(sync_result.errors)
                }
            )
            
            self.status_service.log_event(
                integration_id=integration.id,
                event_type='initial_sync_completed',
                severity='info',
                message=f'Initial Gmail sync completed: {sync_result.messages_processed} messages',
                details={
                    'messages_fetched': sync_result.messages_fetched,
                    'messages_processed': sync_result.messages_processed,
                    'errors_count': len(sync_result.errors)
                }
            )
            
            return sync_result
            
        except Exception as e:
            logger.error(f"Failed to perform initial Gmail sync: {e}")
            self.status_service.log_event(
                integration_id=integration.id,
                event_type='initial_sync_failed',
                severity='error',
                message=f'Initial Gmail sync failed: {str(e)}',
                details={'error': str(e)}
            )
            raise
    
    async def sync_messages(self, integration: Integration, 
                          incremental: bool = True,
                          max_results: int = 100) -> GmailSyncResult:
        """
        Sync Gmail messages for an integration
        
        Args:
            integration: Gmail integration record
            incremental: Whether to perform incremental sync
            max_results: Maximum number of messages to fetch
            
        Returns:
            Sync result
        """
        try:
            query = None
            
            if incremental:
                # Get last sync timestamp from metadata
                last_sync = integration.platform_metadata.get('last_sync_at')
                if last_sync:
                    # Convert to Gmail query format
                    last_sync_dt = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
                    days_since = (datetime.now(timezone.utc) - last_sync_dt).days
                    if days_since > 0:
                        query = f"newer_than:{days_since}d"
                else:
                    # First incremental sync, get last 7 days
                    query = "newer_than:7d"
            
            # Fetch messages
            sync_result = await self.gmail_client.fetch_messages(
                integration=integration,
                query=query,
                max_results=max_results
            )
            
            # Update integration metadata
            await self.integration_service.update_integration_metadata(
                integration_id=integration.id,
                metadata_updates={
                    'last_sync_at': datetime.now(timezone.utc).isoformat(),
                    'last_sync_messages': sync_result.messages_processed,
                    'total_syncs': integration.platform_metadata.get('total_syncs', 0) + 1
                }
            )
            
            self.status_service.log_event(
                integration_id=integration.id,
                event_type='sync_completed',
                severity='info',
                message=f'Gmail sync completed: {sync_result.messages_processed} messages',
                details={
                    'incremental': incremental,
                    'messages_fetched': sync_result.messages_fetched,
                    'messages_processed': sync_result.messages_processed,
                    'errors_count': len(sync_result.errors),
                    'query': query
                }
            )
            
            return sync_result
            
        except Exception as e:
            logger.error(f"Failed to sync Gmail messages: {e}")
            self.status_service.log_event(
                integration_id=integration.id,
                event_type='sync_failed',
                severity='error',
                message=f'Gmail sync failed: {str(e)}',
                details={'error': str(e), 'incremental': incremental}
            )
            raise
    
    async def sync_messages_with_contacts(self, integration: Integration, 
                                         incremental: bool = True,
                                         max_results: int = 100,
                                         extract_contacts: bool = True) -> Dict[str, Any]:
        """
        Sync Gmail messages and optionally extract/update contacts
        
        Args:
            integration: Gmail integration record
            incremental: Whether to perform incremental sync
            max_results: Maximum number of messages to fetch
            extract_contacts: Whether to extract contacts from messages
            
        Returns:
            Combined sync result with contact information
        """
        try:
            # Perform regular message sync
            sync_result = await self.sync_messages(
                integration=integration,
                incremental=incremental,
                max_results=max_results
            )
            
            result_data = {
                'sync_result': sync_result,
                'contacts_extracted': 0,
                'contacts_created': 0,
                'contacts_updated': 0,
                'contacts_data': []
            }
            
            if extract_contacts and hasattr(sync_result, 'messages') and sync_result.messages:
                # Extract contacts from the synced messages
                user_email = integration.platform_metadata.get('email_address', '')
                contacts_data = await self.gmail_client.extract_contacts_from_messages(
                    messages=sync_result.messages,
                    user_id=user_email
                )
                
                result_data['contacts_extracted'] = len(contacts_data)
                result_data['contacts_data'] = contacts_data
                
                # Here you would typically save contacts to database
                # This would require a ContactService - placeholder for now
                self.status_service.log_event(
                    integration_id=integration.id,
                    event_type='contacts_extracted',
                    severity='info',
                    message=f'Extracted {len(contacts_data)} contacts from {sync_result.messages_processed} messages',
                    details={
                        'contacts_extracted': len(contacts_data),
                        'messages_processed': sync_result.messages_processed
                    }
                )
            
            return result_data
            
        except Exception as e:
            logger.error(f"Failed to sync messages with contacts: {e}")
            self.status_service.log_event(
                integration_id=integration.id,
                event_type='sync_with_contacts_failed',
                severity='error',
                message=f'Failed to sync messages with contacts: {str(e)}',
                details={'error': str(e)}
            )
            raise

    async def get_contact_email_history(self, integration_id: str, 
                                      contact_email: str,
                                      max_results: int = 50) -> Dict[str, Any]:
        """
        Get email history for a specific contact
        
        Args:
            integration_id: Integration identifier
            contact_email: Contact's email address
            max_results: Maximum number of messages to retrieve
            
        Returns:
            Contact email history
        """
        try:
            # Get integration record
            integration = self.integration_service.get_integration(integration_id)
            if not integration or integration.provider != 'gmail':
                raise ValueError("Gmail integration not found")
            
            # Fetch messages for the specific contact
            sync_result = await self.gmail_client.fetch_messages_for_contact(
                integration=integration,
                contact_email=contact_email,
                max_results=max_results
            )
            
            # Organize messages by thread and date
            messages_by_thread = {}
            for message in getattr(sync_result, 'messages', []):
                thread_id = message.thread_id
                if thread_id not in messages_by_thread:
                    messages_by_thread[thread_id] = []
                messages_by_thread[thread_id].append({
                    'id': message.id,
                    'subject': message.subject,
                    'sender': message.sender,
                    'sender_email': message.sender_email,
                    'date': message.date.isoformat(),
                    'snippet': message.snippet,
                    'is_read': message.is_read,
                    'labels': message.labels
                })
            
            # Sort threads by most recent message
            sorted_threads = []
            for thread_id, messages in messages_by_thread.items():
                messages.sort(key=lambda x: x['date'], reverse=True)
                sorted_threads.append({
                    'thread_id': thread_id,
                    'message_count': len(messages),
                    'latest_date': messages[0]['date'],
                    'subject': messages[0]['subject'],
                    'messages': messages
                })
            
            sorted_threads.sort(key=lambda x: x['latest_date'], reverse=True)
            
            return {
                'contact_email': contact_email,
                'total_messages': sync_result.messages_processed,
                'total_threads': len(sorted_threads),
                'threads': sorted_threads,
                'sync_timestamp': sync_result.sync_timestamp.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get contact email history: {e}")
            raise
    
    async def get_integration_status(self, integration_id: str) -> Dict[str, Any]:
        """
        Get comprehensive status of Gmail integration
        
        Args:
            integration_id: Integration identifier
            
        Returns:
            Integration status information
        """
        try:
            # Get integration record
            integration = self.integration_service.get_integration(integration_id)
            if not integration or integration.provider != 'gmail':
                raise ValueError("Gmail integration not found")
            
            # Perform health check
            health_data = await self.gmail_client.check_health(integration)
            
            # Get recent events
            recent_events = await self.status_service.get_events(
                integration_id=integration_id,
                limit=10
            )
            
            # Get active alerts
            active_alerts = await self.status_service.get_active_alerts(
                integration_id=integration_id
            )
            
            # Compile status information
            status_data = {
                'integration_id': integration_id,
                'provider': integration.provider,
                'email_address': integration.platform_metadata.get('email_address'),
                'status': integration.status,
                'health': health_data,
                'last_sync_at': integration.platform_metadata.get('last_sync_at'),
                'messages_synced': integration.platform_metadata.get('messages_synced', 0),
                'total_syncs': integration.platform_metadata.get('total_syncs', 0),
                'recent_events': [
                    {
                        'event_type': event.event_type,
                        'severity': event.severity,
                        'message': event.message,
                        'created_at': event.created_at.isoformat()
                    }
                    for event in recent_events
                ],
                'active_alerts': [
                    {
                        'alert_type': alert.alert_type,
                        'severity': alert.severity,
                        'message': alert.message,
                        'created_at': alert.created_at.isoformat()
                    }
                    for alert in active_alerts
                ],
                'created_at': integration.created_at.isoformat(),
                'updated_at': integration.updated_at.isoformat()
            }
            
            return status_data
            
        except Exception as e:
            logger.error(f"Failed to get Gmail integration status: {e}")
            raise
    
    async def disconnect_integration(self, integration_id: str) -> bool:
        """
        Disconnect Gmail integration
        
        Args:
            integration_id: Integration identifier
            
        Returns:
            Success status
        """
        try:
            # Get integration record
            integration = self.integration_service.get_integration(integration_id)
            if not integration or integration.provider != 'gmail':
                raise ValueError("Gmail integration not found")
            
            # Revoke tokens (if possible)
            # Note: Google doesn't provide a direct API to revoke tokens programmatically
            # This would typically be done through the Google Account settings by the user
            
            # Update integration status
            await self.integration_service.update_integration_status(
                integration_id=integration_id,
                status='disconnected'
            )
            
            # Log disconnection
            self.status_service.log_event(
                integration_id=integration_id,
                event_type='integration_disconnected',
                severity='info',
                message='Gmail integration disconnected by user'
            )
            
            logger.info(f"Gmail integration {integration_id} disconnected successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to disconnect Gmail integration: {e}")
            self.status_service.log_event(
                integration_id=integration_id,
                event_type='disconnect_failed',
                severity='error',
                message=f'Failed to disconnect Gmail integration: {str(e)}',
                details={'error': str(e)}
            )
            raise
    
    async def get_user_integrations(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all Gmail integrations for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            List of Gmail integrations
        """
        try:
            integrations = self.integration_service.get_user_integrations(
                user_id=UUID(user_id),
                platform_filter=['google']
            )
            
            integration_data = []
            for integration in integrations:
                # Get basic status for each integration
                try:
                    health_data = await self.gmail_client.check_health(integration)
                    status = health_data.get('status', 'unknown')
                except:
                    status = 'error'
                
                integration_data.append({
                    'integration_id': integration.id,
                    'email_address': integration.platform_metadata.get('email_address'),
                    'status': integration.status,
                    'health_status': status,
                    'last_sync_at': integration.platform_metadata.get('last_sync_at'),
                    'messages_synced': integration.platform_metadata.get('messages_synced', 0),
                    'created_at': integration.created_at.isoformat()
                })
            
            return integration_data
            
        except Exception as e:
            logger.error(f"Failed to get user Gmail integrations: {e}")
            raise
    
    async def trigger_sync(self, integration_id: str, 
                          force_full_sync: bool = False) -> GmailSyncResult:
        """
        Manually trigger Gmail sync
        
        Args:
            integration_id: Integration identifier
            force_full_sync: Whether to force a full sync instead of incremental
            
        Returns:
            Sync result
        """
        try:
            # Get integration record
            integration = self.integration_service.get_integration(integration_id)
            if not integration or integration.provider != 'gmail':
                raise ValueError("Gmail integration not found")
            
            # Perform sync
            sync_result = await self.sync_messages(
                integration=integration,
                incremental=not force_full_sync,
                max_results=200 if force_full_sync else 100
            )
            
            logger.info(f"Manual Gmail sync triggered for integration {integration_id}")
            return sync_result
            
        except Exception as e:
            logger.error(f"Failed to trigger Gmail sync: {e}")
            raise
    
    def get_setup_instructions(self) -> Dict[str, Any]:
        """
        Get Gmail setup instructions
        
        Returns:
            Setup instructions and configuration
        """
        return google_cloud_manager.get_setup_instructions()
    
    def get_oauth_config(self) -> Dict[str, Any]:
        """
        Get OAuth configuration for Gmail
        
        Returns:
            OAuth configuration
        """
        return google_cloud_manager.get_oauth_config() 