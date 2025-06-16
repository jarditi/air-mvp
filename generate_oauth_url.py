#!/usr/bin/env python3
"""Generate OAuth URL directly using the service"""

import sys
import os
import asyncio
from uuid import UUID

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from lib.database import get_db_session
from services.oauth_service import OAuthService
from lib.oauth_client import OAuthProvider

async def generate_oauth_url():
    """Generate a new OAuth URL for testing"""
    try:
        # Get database session
        db = get_db_session()
        
        # Create OAuth service
        oauth_service = OAuthService(db)
        
        # User ID from previous testing - need to convert from Clerk ID to UUID
        # Let's try to find the user in the database first
        from models.orm.user import User
        user = db.query(User).filter(User.auth_provider_id == "user_2yZ2mD697whSd0ThTH1Q5BlbDUk").first()
        
        if not user:
            print("❌ User not found in database")
            return
        
        print(f"👤 Found user: {user.email} (ID: {user.id})")
        
        # Generate OAuth URL
        auth_url, state = await oauth_service.initiate_oauth_flow(
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            redirect_uri='http://localhost:8000/auth/google/callback',
            scopes=[
                'https://www.googleapis.com/auth/gmail.readonly',
                'https://www.googleapis.com/auth/gmail.send',
                'https://www.googleapis.com/auth/calendar.readonly',
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/userinfo.profile'
            ]
        )
        
        print("✅ OAuth URL Generated Successfully!")
        print(f"🔗 Authorization URL: {auth_url}")
        print(f"🔑 State: {state}")
        print(f"👤 User ID: {user.id}")
        print()
        print("📋 Instructions:")
        print("1. Copy the authorization URL above")
        print("2. Open it in your browser")
        print("3. Complete the Google OAuth consent")
        print("4. You'll be redirected back with the authorization code")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Error generating OAuth URL: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(generate_oauth_url()) 