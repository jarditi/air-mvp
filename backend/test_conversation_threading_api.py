"""
Test script for Conversation Threading API endpoints

This script tests the REST API endpoints for Task 3.6.1: Cross-Platform Conversation Threading
"""

import requests
import json
import time
from datetime import datetime, timezone, timedelta

# API base URL
BASE_URL = "http://localhost:8000/api/v1"

# Authentication token (Clerk JWT token)
AUTH_TOKEN = "eyJhbGciOiJSUzI1NiIsImNhdCI6ImNsX0I3ZDRQRDExMUFBQSIsImtpZCI6Imluc18yeVl5UURNaENvN21oYjNoSlBQYll3bEtxdEkiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjE3NTAyNTcxNTAsImZ2YSI6Wzk5OTk5LC0xXSwiaWF0IjoxNzUwMjU3MDkwLCJpc3MiOiJodHRwczovL3dlbGNvbWUtc2hhZC0xOC5jbGVyay5hY2NvdW50cy5kZXYiLCJuYmYiOjE3NTAyNTcwODAsInNpZCI6InNlc3NfMnlnWEZqNnlYUGFSd3FlOEE0SnZ4aGk5cGx6Iiwic3ViIjoidXNlcl8yeWdYNzJZR0xveU9Vb0hVSTg5MHRjSWpmSzkiLCJ2IjoyfQ.yLLEUA49VcpitjWe7z2gOas-rCDbTkOhHUVZnMRYgfu8NuIzAvJRIfjAaTnH1zVLeIyKyDbnMwfpRPQ8BBeUm2Asr9KkZrV2731l3-6Mlhn9UtthO1yq1O2ttp5g1FdyWMfOXNl5AnONEySTmQP_1tVQCAXFqMfb_BWrCcI16i4QLJWbl31u4nnwurwg17DCKEpQ9hhw2c4GhvaZ0UPVlN7fXXKeYx0_FDDmHZOrl56m0Bcz0AI5n_x-DplC5X5AdCra1A0wiERIWlnP95yZjTz6hKw7Q1L5udQRcEBstTUoEoXO9ZVJkd1Dj3fgwzKoOBzeKiKlSTcMX2ZDTgnneA"
HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json"
}

def test_conversation_threading_api():
    """Test conversation threading API endpoints"""
    
    print("🚀 Testing Conversation Threading API Endpoints")
    print("=" * 60)
    
    # Test data
    test_user_id = "user_2ygX72YGLoyOUoHUI890tcIjfK9"  # Clerk user ID from token
    test_contact_id = "test-contact-456"
    
    # Test 1: Build conversation threads
    print("\n1. Testing thread building API...")
    try:
        response = requests.post(
            f"{BASE_URL}/conversation-threads/build",
            json={
                "contact_id": None,
                "days_back": 30,
                "include_platforms": None,
                "force_rebuild": False
            },
            headers=HEADERS,
            timeout=30
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Successfully built threads")
            print(f"   - Total threads: {data.get('total_threads', 0)}")
            print(f"   - Processing time: {data.get('processing_time_seconds', 0):.2f}s")
            print(f"   - Statistics: {data.get('statistics', {})}")
            print(f"   - Merge candidates: {len(data.get('merge_candidates', []))}")
            
            # Show first thread if available
            if data.get('threads'):
                thread = data['threads'][0]
                print(f"   - Sample thread: {thread.get('thread_id')}")
                print(f"     * Platforms: {thread.get('platforms', [])}")
                print(f"     * Interactions: {thread.get('total_interactions', 0)}")
                print(f"     * Context score: {thread.get('context_score', 0):.3f}")
        else:
            print(f"   ❌ Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
    
    # Test 2: Get threads for specific contact
    print("\n2. Testing contact-specific threads...")
    try:
        response = requests.get(
            f"{BASE_URL}/conversation-threads/contact/{test_contact_id}",
            params={
                "days_back": 30
            },
            headers=HEADERS,
            timeout=30
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            threads = response.json()
            print(f"   ✅ Retrieved {len(threads)} threads for contact")
            
            if threads:
                thread = threads[0]
                print(f"   - Thread ID: {thread.get('thread_id')}")
                print(f"   - Context score: {thread.get('context_score', 0):.3f}")
                print(f"   - Thread type: {thread.get('thread_type')}")
        else:
            print(f"   ❌ Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
    
    # Test 3: Get threading statistics
    print("\n3. Testing threading statistics...")
    try:
        response = requests.get(
            f"{BASE_URL}/conversation-threads/statistics",
            params={
                "days_back": 30
            },
            headers=HEADERS,
            timeout=30
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            stats = response.json()
            print(f"   ✅ Retrieved threading statistics")
            print(f"   - Total threads: {stats.get('total_threads', 0)}")
            print(f"   - Cross-platform threads: {stats.get('cross_platform_threads', 0)}")
            print(f"   - Platform distribution: {stats.get('platform_distribution', {})}")
            print(f"   - Thread types: {stats.get('thread_types', {})}")
            print(f"   - Average context score: {stats.get('average_context_score', 0):.3f}")
        else:
            print(f"   ❌ Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
    
    # Test 4: Generate thread summary
    print("\n4. Testing thread summary generation...")
    try:
        # First, let's try to get a thread ID from the build response
        build_response = requests.post(
            f"{BASE_URL}/conversation-threads/build",
            json={
                "contact_id": None,
                "days_back": 30,
                "include_platforms": None,
                "force_rebuild": False
            },
            headers=HEADERS,
            timeout=30
        )
        
        if build_response.status_code == 200:
            build_data = build_response.json()
            threads = build_data.get('threads', [])
            
            if threads:
                thread_id = threads[0]['thread_id']
                
                response = requests.post(
                    f"{BASE_URL}/conversation-threads/summary",
                    json={
                        "thread_id": thread_id
                    },
                    headers=HEADERS,
                    timeout=30
                )
                
                print(f"   Status Code: {response.status_code}")
                
                if response.status_code == 200:
                    summary_data = response.json()
                    print(f"   ✅ Generated thread summary")
                    print(f"   - Summary: {summary_data.get('summary', 'N/A')[:100]}...")
                    print(f"   - Generated at: {summary_data.get('generated_at', 'N/A')}")
                else:
                    print(f"   ❌ Failed with status {response.status_code}")
                    print(f"   Response: {response.text}")
            else:
                print("   ⚠️  No threads available for summary test")
        else:
            print("   ⚠️  Could not build threads for summary test")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
    
    print("\n" + "=" * 60)
    print("🏁 Conversation Threading API Tests Complete")

if __name__ == "__main__":
    test_conversation_threading_api() 