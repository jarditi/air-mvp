"""
Test Gmail Integration for AIR MVP

This test demonstrates the Gmail integration functionality including
OAuth flow, email syncing, and integration management.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent))

# Mock environment variables for testing
os.environ.update({
    'DATABASE_URL': 'sqlite:///test.db',
    'REDIS_URL': 'redis://localhost:6379/0',
    'WEAVIATE_URL': 'http://localhost:8080',
    'SECRET_KEY': 'test-secret-key',
    'OPENAI_API_KEY': 'test-openai-key',
    'CELERY_BROKER_URL': 'redis://localhost:6379/0',
    'CELERY_RESULT_BACKEND': 'redis://localhost:6379/0',
    'GOOGLE_CLOUD_PROJECT_ID': 'test-project-123',
    'GOOGLE_OAUTH_CLIENT_ID': 'test-client-id.apps.googleusercontent.com',
    'GOOGLE_OAUTH_CLIENT_SECRET': 'test-client-secret',
    'GOOGLE_OAUTH_REDIRECT_URI': 'http://localhost:8000/auth/google/callback'
})

from lib.google_cloud_config import GoogleCloudManager
from services.gmail_integration_service import GmailIntegrationService
from lib.gmail_client import GmailClient, EmailMessage, GmailSyncResult


class MockDatabase:
    """Mock database session for testing"""
    
    def __init__(self):
        self.committed = False
        self.rolled_back = False
    
    def commit(self):
        self.committed = True
    
    def rollback(self):
        self.rolled_back = True
    
    def close(self):
        pass


class MockIntegration:
    """Mock integration object for testing"""
    
    def __init__(self):
        self.id = "test-integration-123"
        self.user_id = "test-user-456"
        self.provider = "gmail"
        self.provider_user_id = "test@example.com"
        self.status = "active"
        self.access_token = "test-access-token"
        self.refresh_token = "test-refresh-token"
        self.scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
        self.metadata = {
            "email_address": "test@example.com",
            "messages_total": 100,
            "last_sync_at": datetime.now(timezone.utc).isoformat()
        }
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)


async def test_google_cloud_config():
    """Test Google Cloud configuration"""
    print("🧪 Testing Google Cloud Configuration...")
    
    try:
        # Test configuration loading
        manager = GoogleCloudManager()
        
        print(f"✅ Project ID: {manager.config.project_id}")
        print(f"✅ Client ID: {manager.config.client_id[:20]}...")
        print(f"✅ Redirect URI: {manager.config.redirect_uri}")
        print(f"✅ Scopes: {len(manager.config.scopes)} configured")
        
        # Test OAuth config
        oauth_config = manager.get_oauth_config()
        assert 'client_id' in oauth_config
        assert 'scopes' in oauth_config
        print("✅ OAuth configuration valid")
        
        # Test setup instructions
        instructions = manager.get_setup_instructions()
        assert 'project_setup' in instructions
        assert 'security_notes' in instructions
        print("✅ Setup instructions available")
        
        print("✅ Google Cloud configuration test passed\n")
        return True
        
    except Exception as e:
        print(f"❌ Google Cloud configuration test failed: {e}\n")
        return False


async def test_gmail_client():
    """Test Gmail client functionality"""
    print("🧪 Testing Gmail Client...")
    
    try:
        # Mock dependencies
        mock_integration_service = Mock()
        mock_status_service = AsyncMock()
        
        # Create Gmail client
        client = GmailClient(mock_integration_service, mock_status_service)
        
        # Test authorization URL generation
        with patch.object(client.oauth_client, 'get_authorization_url') as mock_auth:
            mock_auth.return_value = "https://accounts.google.com/oauth/authorize?..."
            
            auth_url = await client.get_authorization_url("test-user-123")
            assert auth_url.startswith("https://accounts.google.com")
            print("✅ Authorization URL generation works")
        
        # Test OAuth callback handling
        mock_integration = MockIntegration()
        with patch.object(client.oauth_client, 'exchange_code_for_tokens') as mock_exchange:
            with patch('googleapiclient.discovery.build') as mock_build:
                # Mock token exchange
                mock_exchange.return_value = {
                    'access_token': 'test-token',
                    'refresh_token': 'test-refresh',
                    'expires_at': 1234567890
                }
                
                # Mock Gmail service
                mock_service = Mock()
                mock_service.users().getProfile().execute.return_value = {
                    'emailAddress': 'test@example.com',
                    'messagesTotal': 100,
                    'threadsTotal': 50
                }
                mock_build.return_value = mock_service
                
                # Mock integration service
                mock_integration_service.create_integration = AsyncMock(return_value=mock_integration)
                
                integration = await client.handle_oauth_callback("test-user", "auth-code")
                assert integration.provider == "gmail"
                print("✅ OAuth callback handling works")
        
        # Test health check
        with patch.object(client, '_get_service') as mock_get_service:
            mock_service = Mock()
            mock_service.users().getProfile().execute.return_value = {
                'emailAddress': 'test@example.com',
                'messagesTotal': 100
            }
            mock_get_service.return_value = mock_service
            
            health_data = await client.check_health(mock_integration)
            assert health_data['status'] == 'healthy'
            assert 'email_address' in health_data
            print("✅ Health check works")
        
        print("✅ Gmail client test passed\n")
        return True
        
    except Exception as e:
        print(f"❌ Gmail client test failed: {e}\n")
        return False


async def test_gmail_integration_service():
    """Test Gmail integration service"""
    print("🧪 Testing Gmail Integration Service...")
    
    try:
        # Mock database
        mock_db = MockDatabase()
        
        # Create service with mocked dependencies
        service = GmailIntegrationService(mock_db)
        
        # Mock the underlying services
        service.integration_service = AsyncMock()
        service.status_service = AsyncMock()
        service.gmail_client = AsyncMock()
        
        # Test OAuth flow initiation
        mock_auth_data = {
            'authorization_url': 'https://accounts.google.com/oauth/authorize?...',
            'state': 'test-state-123',
            'user_id': 'test-user',
            'provider': 'gmail'
        }
        service.gmail_client.get_authorization_url.return_value = mock_auth_data['authorization_url']
        
        oauth_data = await service.initiate_oauth_flow("test-user")
        assert 'authorization_url' in oauth_data
        assert oauth_data['provider'] == 'gmail'
        print("✅ OAuth flow initiation works")
        
        # Test OAuth callback handling
        mock_integration = MockIntegration()
        service.gmail_client.handle_oauth_callback.return_value = mock_integration
        service.gmail_client.fetch_messages.return_value = GmailSyncResult(
            messages_fetched=10,
            messages_processed=10,
            errors=[],
            next_page_token=None,
            history_id="12345",
            sync_timestamp=datetime.now(timezone.utc)
        )
        
        integration = await service.handle_oauth_callback("test-user", "auth-code", "test-state")
        assert integration.provider == "gmail"
        print("✅ OAuth callback handling works")
        
        # Test message syncing
        sync_result = await service.sync_messages(mock_integration)
        assert sync_result.messages_processed >= 0
        print("✅ Message syncing works")
        
        # Test integration status
        service.integration_service.get_integration.return_value = mock_integration
        service.gmail_client.check_health.return_value = {'status': 'healthy'}
        service.status_service.get_events.return_value = []
        service.status_service.get_active_alerts.return_value = []
        
        status_data = await service.get_integration_status("test-integration-123")
        assert 'integration_id' in status_data
        assert 'health' in status_data
        print("✅ Integration status retrieval works")
        
        # Test user integrations
        service.integration_service.get_user_integrations.return_value = [mock_integration]
        
        user_integrations = await service.get_user_integrations("test-user")
        assert len(user_integrations) > 0
        print("✅ User integrations retrieval works")
        
        print("✅ Gmail integration service test passed\n")
        return True
        
    except Exception as e:
        print(f"❌ Gmail integration service test failed: {e}\n")
        return False


async def test_email_parsing():
    """Test email message parsing"""
    print("🧪 Testing Email Parsing...")
    
    try:
        # Mock Gmail message data
        mock_message_data = {
            'id': 'msg123',
            'threadId': 'thread456',
            'labelIds': ['INBOX', 'UNREAD'],
            'snippet': 'This is a test email...',
            'payload': {
                'headers': [
                    {'name': 'From', 'value': 'Test User <test@example.com>'},
                    {'name': 'To', 'value': 'recipient@example.com'},
                    {'name': 'Subject', 'value': 'Test Email Subject'},
                    {'name': 'Date', 'value': 'Mon, 1 Jan 2024 12:00:00 +0000'}
                ],
                'mimeType': 'text/plain',
                'body': {
                    'data': 'VGhpcyBpcyBhIHRlc3QgZW1haWwgYm9keQ=='  # Base64 encoded "This is a test email body"
                }
            }
        }
        
        # Create Gmail client for testing
        mock_integration_service = Mock()
        mock_status_service = AsyncMock()
        client = GmailClient(mock_integration_service, mock_status_service)
        
        # Test message parsing
        parsed_message = client._parse_message(mock_message_data)
        
        assert parsed_message.id == 'msg123'
        assert parsed_message.subject == 'Test Email Subject'
        assert parsed_message.sender_email == 'test@example.com'
        assert 'recipient@example.com' in parsed_message.recipients
        assert not parsed_message.is_read  # UNREAD label present
        print("✅ Email message parsing works")
        
        # Test email extraction
        email = client._extract_email('Test User <test@example.com>')
        assert email == 'test@example.com'
        print("✅ Email extraction works")
        
        # Test recipients parsing
        recipients = client._parse_recipients('user1@example.com, User Two <user2@example.com>')
        assert 'user1@example.com' in recipients
        assert 'user2@example.com' in recipients
        print("✅ Recipients parsing works")
        
        print("✅ Email parsing test passed\n")
        return True
        
    except Exception as e:
        print(f"❌ Email parsing test failed: {e}\n")
        return False


async def test_setup_instructions():
    """Test setup instructions generation"""
    print("🧪 Testing Setup Instructions...")
    
    try:
        manager = GoogleCloudManager()
        instructions = manager.get_setup_instructions()
        
        # Validate instruction structure
        assert 'project_setup' in instructions
        assert 'optional_setup' in instructions
        assert 'security_notes' in instructions
        assert 'current_config' in instructions
        
        # Check project setup steps
        project_steps = instructions['project_setup']['steps']
        assert len(project_steps) >= 5  # Should have at least 5 steps
        
        for step in project_steps:
            assert 'step' in step
            assert 'title' in step
            assert 'description' in step
            assert 'details' in step
        
        print(f"✅ Found {len(project_steps)} setup steps")
        
        # Check security notes
        security_notes = instructions['security_notes']
        assert len(security_notes) > 0
        print(f"✅ Found {len(security_notes)} security notes")
        
        # Test environment template generation
        env_template = manager.generate_env_template()
        assert 'GOOGLE_CLOUD_PROJECT_ID' in env_template
        assert 'GOOGLE_OAUTH_CLIENT_ID' in env_template
        print("✅ Environment template generation works")
        
        print("✅ Setup instructions test passed\n")
        return True
        
    except Exception as e:
        print(f"❌ Setup instructions test failed: {e}\n")
        return False


async def run_all_tests():
    """Run all Gmail integration tests"""
    print("🚀 Starting Gmail Integration Tests")
    print("=" * 50)
    
    tests = [
        test_google_cloud_config,
        test_gmail_client,
        test_gmail_integration_service,
        test_email_parsing,
        test_setup_instructions
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            result = await test()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}\n")
            failed += 1
    
    print("=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All Gmail integration tests passed!")
        print("\n📋 Next Steps:")
        print("1. Set up your Google Cloud project using the setup script:")
        print("   python scripts/setup_google_cloud.py")
        print("2. Configure your environment variables in .env file")
        print("3. Start the application and test the Gmail integration")
        print("4. Visit /docs to see the Gmail API endpoints")
    else:
        print("❌ Some tests failed. Please check the implementation.")
    
    return failed == 0


if __name__ == "__main__":
    asyncio.run(run_all_tests()) 