"""
Quick test script for timeline API endpoints
"""

import requests
import json

def test_timeline_endpoints():
    """Test the timeline service API endpoints"""
    base_url = "http://localhost:8000/api/v1/timeline"
    
    print("🧪 Testing Timeline Service API Endpoints")
    print("=" * 50)
    
    # Test 1: Health endpoint
    print("\n📋 Test 1: Health endpoint")
    try:
        response = requests.get(f"{base_url}/health")
        print(f"✅ Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Service: {data.get('service')}")
            print(f"✅ Status: {data.get('status')}")
            print(f"✅ Features: {data.get('features', [])}")
        else:
            print(f"❌ Error: {response.text}")
    except Exception as e:
        print(f"❌ Failed: {e}")
    
    # Test 2: Stats endpoint (no auth needed for basic stats)
    print("\n📊 Test 2: Stats endpoint")
    try:
        response = requests.get(f"{base_url}/stats")
        print(f"Status: {response.status_code}")
        if response.status_code == 401:
            print("✅ Correctly requires authentication")
        elif response.status_code == 200:
            print("✅ Stats endpoint accessible")
        else:
            print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Failed: {e}")
    
    print("\n🎉 Timeline API endpoint tests completed!")

if __name__ == "__main__":
    test_timeline_endpoints() 