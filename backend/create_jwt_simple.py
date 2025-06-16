#!/usr/bin/env python3
"""
Simple JWT token creation for test user

This script creates a JWT token without importing problematic models.
"""

import sys
import os
import jwt
from datetime import datetime, timedelta
from uuid import UUID

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import get_settings
from sqlalchemy import create_engine, text


def create_jwt_token_simple():
    """Create a JWT token for the test user using raw SQL"""
    
    print("🔑 Creating JWT token (simple approach)...")
    
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # Find the most recent test user
            result = conn.execute(text("""
                SELECT id, email, full_name, auth_provider 
                FROM users 
                WHERE email LIKE 'calendar_test_%@example.com' 
                ORDER BY created_at DESC 
                LIMIT 1
            """))
            
            user_row = result.fetchone()
            if not user_row:
                print("❌ No test user found. Please run create_simple_test_user.py first.")
                return None, None
            
            user_id, email, full_name, auth_provider = user_row
            
            print(f"✅ Found test user: {email}")
            print(f"   User ID: {user_id}")
            
            # Create JWT payload
            payload = {
                "sub": str(user_id),
                "email": email,
                "auth_provider": auth_provider,
                "iat": datetime.utcnow(),
                "exp": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            }
            
            # Create JWT token
            jwt_token = jwt.encode(
                payload,
                settings.SECRET_KEY,
                algorithm=settings.ALGORITHM
            )
            
            print(f"✅ Created JWT token: {jwt_token[:50]}...")
            
            return jwt_token, user_id
            
    except Exception as e:
        print(f"❌ Failed to create JWT token: {e}")
        return None, None


def test_token_authentication(token: str):
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
    token, user_id = create_jwt_token_simple()
    
    if token and user_id:
        # Test the token
        auth_success = test_token_authentication(token)
        
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