#!/usr/bin/env python3
"""
Test script for Google Calendar integration

This script helps test the calendar contact extraction functionality
by guiding through the OAuth authentication process.
"""

import requests
import json
import webbrowser
from urllib.parse import urlparse, parse_qs
import time

BASE_URL = "http://localhost:8000"

def test_calendar_integration():
    """Test the calendar integration with OAuth flow"""
    print("🗓️  Testing Google Calendar Integration")
    print("=" * 50)
    
    # Step 1: Check if backend is running
    print("\n📋 Step 1: Checking backend health")
    try:
        response = requests.get(f"{BASE_URL}/health/")
        if response.status_code == 200:
            print("✅ Backend is running")
        else:
            print("❌ Backend not accessible")
            return
    except Exception as e:
        print(f"❌ Backend connection failed: {e}")
        return
    
    # Step 2: Check calendar endpoints
    print("\n📋 Step 2: Checking calendar endpoints")
    try:
        # Check if calendar extract endpoint exists
        response = requests.post(f"{BASE_URL}/api/v1/extract", 
                               json={"days_back": 7},
                               headers={"Content-Type": "application/json"})
        
        if response.status_code == 401:
            print("✅ Calendar extract endpoint exists (requires auth)")
        elif response.status_code == 403:
            print("✅ Calendar extract endpoint exists (requires auth)")
        else:
            print(f"📝 Calendar extract response: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Calendar endpoint test failed: {e}")
    
    # Step 3: Test OAuth initiation
    print("\n📋 Step 3: Testing OAuth flow")
    print("To test with your actual Google Calendar, you need to:")
    print("1. Complete the OAuth authentication")
    print("2. This will require opening a browser window")
    print("3. You'll need to authorize the app to access your calendar")
    
    proceed = input("\n🤔 Do you want to proceed with OAuth? (y/n): ").lower().strip()
    if proceed != 'y':
        print("⏭️  Skipping OAuth test")
        return
    
    # For now, let's test the OAuth endpoints availability
    print("\n📋 Step 4: Checking OAuth endpoints")
    oauth_endpoints = [
        "/api/v1/integrations/oauth/initiate",
        "/api/v1/integrations/oauth/callback"
    ]
    
    for endpoint in oauth_endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}")
            if response.status_code in [401, 403, 405]:  # Method not allowed or auth required
                print(f"✅ {endpoint} - endpoint exists")
            else:
                print(f"📝 {endpoint} - status: {response.status_code}")
        except Exception as e:
            print(f"❌ {endpoint} - failed: {e}")
    
    print("\n📋 Manual OAuth Testing Instructions:")
    print("=" * 50)
    print("Since the OAuth flow requires user interaction, here's how to test manually:")
    print()
    print("1. 🌐 Open your browser and go to the FastAPI docs:")
    print(f"   {BASE_URL}/docs")
    print()
    print("2. 🔐 Find the OAuth endpoints in the 'Gmail Integration' section")
    print()
    print("3. 📝 Use the 'Try it out' feature to initiate OAuth:")
    print("   - Click on POST /api/v1/integrations/oauth/initiate")
    print("   - Click 'Try it out'")
    print("   - Enter request body: {}")
    print("   - Click 'Execute'")
    print()
    print("4. 🔗 Copy the authorization URL from the response")
    print()
    print("5. 🌐 Open the authorization URL in your browser")
    print()
    print("6. ✅ Complete the Google OAuth consent flow")
    print()
    print("7. 📅 After successful auth, test calendar extraction:")
    print("   - Use POST /api/v1/extract endpoint")
    print("   - Request body: {\"days_back\": 30}")
    print()
    print("🎉 This will extract contacts from your calendar events!")

def test_calendar_service_direct():
    """Test calendar service directly (without OAuth)"""
    print("\n🔧 Testing Calendar Service (Direct)")
    print("=" * 40)
    
    try:
        # This would require a valid database session and OAuth tokens
        print("📝 Direct service testing requires:")
        print("  - Valid database session")
        print("  - OAuth tokens for Google Calendar API")
        print("  - User authentication")
        print()
        print("💡 Use the API endpoints instead for full integration testing")
        
    except Exception as e:
        print(f"❌ Direct service test failed: {e}")

if __name__ == "__main__":
    test_calendar_integration()
    test_calendar_service_direct() 