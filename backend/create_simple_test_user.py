#!/usr/bin/env python3
"""
Simple test user creation script

Creates a test user directly in the database without importing
problematic models that have relationship issues.
"""

import sys
import os
from datetime import datetime
from uuid import uuid4

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from config import settings


def create_test_user_simple():
    """Create a test user using raw SQL to avoid model issues"""
    
    print("👤 Creating test user (simple approach)...")
    
    # Create database engine
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # Create unique email to avoid conflicts
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            test_email = f"calendar_test_{timestamp}@example.com"
            user_id = str(uuid4())
            
            # Check if user already exists
            result = conn.execute(text("""
                SELECT id, email FROM users WHERE email = :email
            """), {"email": test_email})
            
            existing_user = result.fetchone()
            if existing_user:
                print(f"✅ Test user already exists: {existing_user[1]} (ID: {existing_user[0]})")
                return existing_user[0], existing_user[1]
            
            # Create test user with raw SQL
            conn.execute(text("""
                INSERT INTO users (
                    id, email, full_name, auth_provider, auth_provider_id,
                    subscription_tier, subscription_status, is_active, is_verified,
                    onboarding_completed, timezone, created_at, updated_at
                ) VALUES (
                    :id, :email, :full_name, :auth_provider, :auth_provider_id,
                    :subscription_tier, :subscription_status, :is_active, :is_verified,
                    :onboarding_completed, :timezone, :created_at, :updated_at
                )
            """), {
                "id": user_id,
                "email": test_email,
                "full_name": "Calendar Test User",
                "auth_provider": "test",
                "auth_provider_id": f"test-calendar-{timestamp}",
                "subscription_tier": "free",
                "subscription_status": "active",
                "is_active": True,
                "is_verified": True,
                "onboarding_completed": True,
                "timezone": "UTC",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
            
            conn.commit()
            
            print(f"✅ Created test user: {test_email}")
            print(f"   User ID: {user_id}")
            print(f"   Auth Provider: test")
            print(f"   Full Name: Calendar Test User")
            
            return user_id, test_email
            
    except Exception as e:
        print(f"❌ Failed to create test user: {e}")
        return None, None


def create_test_token(user_id: str):
    """Create a simple test token for the user"""
    
    # For testing purposes, we'll create a simple token
    # In a real system, this would be a proper JWT token
    test_token = f"test-token-{user_id}"
    
    print(f"🔑 Test token created: {test_token}")
    print(f"   Use this in Authorization header: Bearer {test_token}")
    
    return test_token


if __name__ == "__main__":
    user_id, email = create_test_user_simple()
    if user_id:
        token = create_test_token(user_id)
        
        print("\n📋 Next Steps:")
        print("=" * 50)
        print("1. Use the test token in FastAPI docs:")
        print(f"   - Go to http://localhost:8000/docs")
        print(f"   - Click 'Authorize' button")
        print(f"   - Enter: Bearer {token}")
        print()
        print("2. Now you can test the OAuth initiate endpoint:")
        print("   - POST /api/v1/integrations/oauth/initiate")
        print("   - Request body: {}")
        print()
        print("3. After OAuth, test calendar extraction:")
        print("   - POST /api/v1/extract")
        print("   - Request body: {\"days_back\": 30}")
        print()
        print("🎉 Ready to test Google Calendar integration!")
    else:
        print("❌ Failed to create test user. Please check the error above.") 