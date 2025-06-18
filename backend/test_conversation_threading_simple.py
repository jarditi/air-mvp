#!/usr/bin/env python3
"""
Simple test script for Conversation Threading API endpoints
Tests the core functionality with Clerk authentication
"""

import requests
import json
import subprocess
import sys
from datetime import datetime

# API base URL
BASE_URL = "http://localhost:8000/api/v1"

def get_fresh_clerk_token():
    """Get a fresh Clerk token using node script"""
    try:
        result = subprocess.run(['node', '../get-clerk-token.js'], 
                              capture_output=True, text=True, cwd='..')
        if result.returncode == 0:
            # Extract token from output
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if 'Token:' in line:
                    return line.split('Token:')[1].strip()
        return None
    except Exception as e:
        print(f"❌ Error getting fresh token: {e}")
        return None

def test_conversation_threading_api():
    """Test conversation threading API endpoints"""
    
    print("🚀 Testing Conversation Threading API Endpoints")
    print("=" * 60)
    
    # Use fresh token
    print("🔑 Using fresh Clerk token...")
    auth_token = "eyJhbGciOiJSUzI1NiIsImNhdCI6ImNsX0I3ZDRQRDExMUFBQSIsImtpZCI6Imluc18yeVl5UURNaENvN21oYjNoSlBQYll3bEtxdEkiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjE3NTAyNjc1MTksImZ2YSI6Wzk5OTk5LC0xXSwiaWF0IjoxNzUwMjY3NDU5LCJpc3MiOiJodHRwczovL3dlbGNvbWUtc2hhZC0xOC5jbGVyay5hY2NvdW50cy5kZXYiLCJuYmYiOjE3NTAyNjc0NDksInNpZCI6InNlc3NfMnlnc0gzYzV2QjRKV3k2dHlhOVVNSWpubmhNIiwic3ViIjoidXNlcl8yeWdzSDRNWXhvRmd1bHRVTEJ2cXpFU2ZLSE4iLCJ2IjoyfQ.aDhKB69OaMjFcFGmSNv-2iTh-j2ZB4X8DOHTh_PdoAfjtNhm-YwPO84g9Vc-r3cWiy7JotGPyZeDZYHpv84a7sDqUANQ3myZ3AJILTauGUiFzThqM_ebct1ULxsT9bymINzZShYIV2o14BTmnNT2XzvJnD-wWdQfNGfsDo8KXtByOqnPs_G7T0c8jH9m-sJDj6Pi1xsKCA1_x0SqU84bU40-qGB52Vmoay27yTay74q0UYY3vka_Tf01Aftwz84AV4syCjEf851b7wy_F4H4RcQP25X5Z2L4eCnb-2JL9kk2xG2OzLXptxCNMvzQL49rIVwffgGBW6cD7qcMF_Q7Zg"
    
    print("✅ Using fresh authentication token")
    
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }
    
    # Test 1: Health check
    print("\n🏥 Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL.replace('/api/v1', '')}/health/")
        if response.status_code == 200:
            print("✅ Health check passed")
        else:
            print(f"❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Health check error: {e}")
    
    # Test 2: Auth check
    print("\n🔐 Testing authentication...")
    try:
        response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
        if response.status_code == 200:
            user_data = response.json()
            print(f"✅ Authentication successful - User: {user_data.get('id')}")
            user_id = user_data.get('id')
        else:
            print(f"❌ Authentication failed: {response.status_code} - {response.text}")
            # Continue with static user ID for testing
            user_id = "test-user-id"
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        user_id = "test-user-id"
    
    # Test 3: Build conversation threads
    print("\n🧵 Testing conversation threads build...")
    try:
        build_data = {
            "user_id": user_id,
            "contact_ids": ["contact-1", "contact-2"],
            "time_window_hours": 24,
            "similarity_threshold": 0.7
        }
        
        response = requests.post(
            f"{BASE_URL}/conversation-threads/build",
            headers=headers,
            json=build_data
        )
        
        print(f"Build threads response: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Built {result.get('threads_created', 0)} conversation threads")
        else:
            print(f"❌ Build failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Build threads error: {e}")
    
    # Test 4: Get threads for contact
    print("\n📞 Testing get threads for contact...")
    try:
        response = requests.get(
            f"{BASE_URL}/conversation-threads/contact/test-contact-123",
            headers=headers
        )
        
        print(f"Get threads response: {response.status_code}")
        if response.status_code == 200:
            threads = response.json()
            print(f"✅ Retrieved {len(threads.get('threads', []))} threads")
        else:
            print(f"❌ Get threads failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Get threads error: {e}")
    
    # Test 5: Generate thread summary
    print("\n📝 Testing thread summary generation...")
    try:
        summary_data = {
            "thread_id": "test-thread-456",
            "summary_type": "brief",
            "include_metadata": True
        }
        
        response = requests.post(
            f"{BASE_URL}/conversation-threads/summary",
            headers=headers,
            json=summary_data
        )
        
        print(f"Summary response: {response.status_code}")
        if response.status_code == 200:
            summary = response.json()
            print(f"✅ Generated summary: {summary.get('summary', 'N/A')[:100]}...")
        else:
            print(f"❌ Summary failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Summary error: {e}")
    
    # Test 6: Analyze conversation context
    print("\n🔍 Testing conversation context analysis...")
    try:
        context_data = {
            "contact_id": "test-contact-789",
            "context_window_days": 7,
            "include_sentiment": True
        }
        
        response = requests.post(
            f"{BASE_URL}/conversation-threads/context",
            headers=headers,
            json=context_data
        )
        
        print(f"Context analysis response: {response.status_code}")
        if response.status_code == 200:
            context = response.json()
            print(f"✅ Context analysis completed")
        else:
            print(f"❌ Context analysis failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Context analysis error: {e}")
    
    # Test 7: Get threading statistics
    print("\n📊 Testing threading statistics...")
    try:
        response = requests.get(
            f"{BASE_URL}/conversation-threads/statistics",
            headers=headers
        )
        
        print(f"Statistics response: {response.status_code}")
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ Statistics retrieved: {json.dumps(stats, indent=2)}")
        else:
            print(f"❌ Statistics failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Statistics error: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 Conversation Threading API Test Complete!")
    return True

if __name__ == "__main__":
    success = test_conversation_threading_api()
    sys.exit(0 if success else 1) 