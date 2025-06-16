#!/usr/bin/env python3
"""
Create a test user for calendar integration testing

This script creates a test user in the database that can be used
to test the Google Calendar integration functionality.
"""

import sys
import os
from datetime import datetime
from uuid import uuid4

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from lib.database import SessionLocal
from models.orm.user import User


def create_test_user():
    """Create a test user for calendar integration testing"""
    
    print("👤 Creating test user for calendar integration...")
    
    db = SessionLocal()
    
    try:
        # Create unique email to avoid conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_email = f"calendar_test_{timestamp}@example.com"
        
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == test_email).first()
        if existing_user:
            print(f"✅ Test user already exists: {existing_user.email} (ID: {existing_user.id})")
            return existing_user
        
        # Create test user with all required fields
        test_user = User(
            id=str(uuid4()),
            email=test_email,
            full_name="Calendar Test User",
            auth_provider="test",  # Required field
            auth_provider_id=f"test-calendar-{timestamp}",  # Required field
            subscription_tier="free",
            subscription_status="active",
            is_active=True,
            is_verified=True,
            onboarding_completed=True,
            timezone="UTC"
        )
        
        db.add(test_user)
        db.commit()
        
        print(f"✅ Created test user: {test_user.email}")
        print(f"   User ID: {test_user.id}")
        print(f"   Auth Provider: {test_user.auth_provider}")
        print(f"   Full Name: {test_user.full_name}")
        
        return test_user
        
    except Exception as e:
        print(f"❌ Failed to create test user: {e}")
        db.rollback()
        return None
        
    finally:
        db.close()


def create_test_token(user_id: str):
    """Create a simple test token for the user"""
    
    # For testing purposes, we'll create a simple token
    # In a real system, this would be a proper JWT token
    test_token = f"test-token-{user_id}"
    
    print(f"🔑 Test token created: {test_token}")
    print(f"   Use this in Authorization header: Bearer {test_token}")
    
    return test_token


if __name__ == "__main__":
    user = create_test_user()
    if user:
        token = create_test_token(user.id)
        
        print("\n📋 Next Steps:")
        print("=" * 50)
        print("1. Use the test token in FastAPI docs:")
        print(f"   - Click 'Authorize' button in http://localhost:8000/docs")
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