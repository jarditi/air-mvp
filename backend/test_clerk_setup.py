#!/usr/bin/env python3
"""
Test Clerk authentication setup

This script tests if Clerk is properly configured and working.
"""

import sys
import os

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.auth import get_auth_service
from config import get_settings


def test_clerk_setup():
    """Test if Clerk is properly configured"""
    
    print("🔐 Testing Clerk Authentication Setup")
    print("=" * 50)
    
    settings = get_settings()
    auth_service = get_auth_service()
    
    # Check configuration
    print("\n📋 Configuration Check:")
    print(f"✅ Clerk Publishable Key: {'Set' if settings.CLERK_PUBLISHABLE_KEY else '❌ Not Set'}")
    print(f"✅ Clerk Secret Key: {'Set' if settings.CLERK_SECRET_KEY else '❌ Not Set'}")
    print(f"📝 Clerk JWT Key: {'Set' if settings.CLERK_JWT_VERIFICATION_KEY else 'Not Set (Optional)'}")
    print(f"✅ Clerk Client: {'Initialized' if auth_service.clerk_client else '❌ Not Initialized'}")
    
    # Test auth health endpoint
    print("\n🏥 Testing Auth Health Endpoint:")
    try:
        import requests
        response = requests.get("http://localhost:8000/api/v1/auth/health")
        if response.status_code == 200:
            health_data = response.json()
            print("✅ Auth service is healthy")
            print(f"   Clerk configured: {health_data.get('clerk_configured', False)}")
            print(f"   JWT verification: {health_data.get('jwt_verification_configured', False)}")
        else:
            print(f"❌ Auth health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Auth health check error: {e}")
    
    # Next steps
    print("\n📋 Next Steps:")
    if settings.CLERK_PUBLISHABLE_KEY and settings.CLERK_SECRET_KEY:
        print("✅ Clerk is configured! You can now:")
        print("   1. Go to http://localhost:8000/docs")
        print("   2. Use Clerk authentication in your frontend")
        print("   3. Get a JWT token from Clerk")
        print("   4. Use that token to test the calendar integration")
        print()
        print("💡 For the JWT verification key:")
        print("   - Go to Clerk Dashboard → Configure → JWT Templates")
        print("   - Copy the 'Signing Key' as CLERK_JWT_VERIFICATION_KEY")
    else:
        print("❌ Please set your Clerk keys in the .env file:")
        print("   CLERK_PUBLISHABLE_KEY=pk_test_...")
        print("   CLERK_SECRET_KEY=sk_test_...")


if __name__ == "__main__":
    test_clerk_setup() 