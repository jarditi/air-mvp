#!/usr/bin/env python3
"""
Create a proper JWT token for the test user

This script creates a valid JWT token that can be used to authenticate
with the calendar integration endpoints.
"""

import sys
import os
from datetime import datetime
from uuid import UUID

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from lib.database import SessionLocal
from models.orm.user import User
from services.auth import get_auth_service


def create_jwt_token_for_test_user():
    """Create a proper JWT token for the test user"""
    
    print("🔑 Creating JWT token for test user...")
    
    db = SessionLocal()
    
    try:
        # Find the most recent test user
        test_user = db.query(User).filter(
            User.email.like("calendar_test_%@example.com")
        ).order_by(User.created_at.desc()).first()
        
        if not test_user:
            print("❌ No test user found. Please run create_simple_test_user.py first.")
            return None
        
        print(f"✅ Found test user: {test_user.email}")
        print(f"   User ID: {test_user.id}")
        
        # Create JWT token using the auth service
        auth_service = get_auth_service()
        jwt_token = auth_service.create_internal_token(test_user)
        
        print(f"✅ Created JWT token: {jwt_token[:50]}...")
        
        return jwt_token, test_user
        
    except Exception as e:
        print(f"❌ Failed to create JWT token: {e}")
        return None, None
        
    finally:
        db.close()


def test_token_authentication(token: str, user_id: str):
    """Test the token authentication"""
    
    print("\n🧪 Testing token authentication...")
    
    try:
        import requests
        
        # Test the auth endpoint
        response = requests.get(
            "http://localhost:8000/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            user_data = response.json()
            print("✅ Token authentication successful!")
            print(f"   Authenticated as: {user_data.get('email')}")
            print(f"   User ID: {user_data.get('id')}")
            return True
        else:
            print(f"❌ Token authentication failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Token test failed: {e}")
        return False


if __name__ == "__main__":
    token, user = create_jwt_token_for_test_user()
    
    if token and user:
        # Test the token
        auth_success = test_token_authentication(token, str(user.id))
        
        if auth_success:
            print("\n📋 Ready for Calendar Integration Testing!")
            print("=" * 60)
            print("1. Use this JWT token in FastAPI docs:")
            print(f"   - Go to http://localhost:8000/docs")
            print(f"   - Click 'Authorize' button")
            print(f"   - Enter: Bearer {token}")
            print()
            print("2. Now test the OAuth initiate endpoint:")
            print("   - POST /api/v1/integrations/oauth/initiate")
            print("   - Request body: {}")
            print()
            print("3. After OAuth, test calendar extraction:")
            print("   - POST /api/v1/extract")
            print("   - Request body: {\"days_back\": 30}")
            print()
            print("🎉 Your Google Calendar integration is ready to test!")
        else:
            print("\n❌ Token authentication failed. Please check the backend logs.")
    else:
        print("\n❌ Failed to create JWT token. Please check the error above.") 