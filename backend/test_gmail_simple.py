#!/usr/bin/env python3
"""
Simple Gmail Integration Test for AIR MVP

This test demonstrates the Gmail integration functionality.
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent))

# Set required environment variables
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

def test_google_cloud_config():
    """Test Google Cloud configuration"""
    print("🧪 Testing Google Cloud Configuration...")
    
    try:
        from lib.google_cloud_config import GoogleCloudManager
        
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

def test_gmail_client_basic():
    """Test basic Gmail client functionality"""
    print("🧪 Testing Gmail Client (Basic)...")
    
    try:
        from lib.gmail_client import GmailClient, EmailMessage
        from unittest.mock import Mock, AsyncMock
        
        # Mock dependencies
        mock_integration_service = Mock()
        mock_status_service = AsyncMock()
        
        # Create Gmail client
        client = GmailClient(mock_integration_service, mock_status_service)
        
        # Test email parsing utilities
        email = client._extract_email('Test User <test@example.com>')
        assert email == 'test@example.com'
        print("✅ Email extraction works")
        
        # Test recipients parsing
        recipients = client._parse_recipients('user1@example.com, User Two <user2@example.com>')
        assert 'user1@example.com' in recipients
        assert 'user2@example.com' in recipients
        print("✅ Recipients parsing works")
        
        print("✅ Gmail client basic test passed\n")
        return True
        
    except Exception as e:
        print(f"❌ Gmail client basic test failed: {e}\n")
        return False

def test_setup_instructions():
    """Test setup instructions generation"""
    print("🧪 Testing Setup Instructions...")
    
    try:
        from lib.google_cloud_config import GoogleCloudManager
        
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

def main():
    """Run all tests"""
    print("🚀 Starting Gmail Integration Tests")
    print("=" * 50)
    
    tests = [
        test_google_cloud_config,
        test_gmail_client_basic,
        test_setup_instructions
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            result = test()
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
        print("1. Set up your Google Cloud project:")
        print("   - Go to https://console.cloud.google.com/")
        print("   - Create a new project")
        print("   - Enable Gmail API")
        print("   - Create OAuth 2.0 credentials")
        print("2. Configure your environment variables in .env file")
        print("3. Start the application and test the Gmail integration")
        print("4. Visit /docs to see the Gmail API endpoints")
        print("\n🔧 Available API Endpoints:")
        print("   GET  /api/v1/integrations/gmail/setup-instructions")
        print("   POST /api/v1/integrations/gmail/oauth/initiate")
        print("   POST /api/v1/integrations/gmail/oauth/callback")
        print("   GET  /api/v1/integrations/gmail/integrations")
        print("   POST /api/v1/integrations/gmail/integrations/{id}/sync")
    else:
        print("❌ Some tests failed. Please check the implementation.")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 