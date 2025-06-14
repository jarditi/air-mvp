#!/usr/bin/env python3
"""
Simple API Test Script

This script tests the contact scoring API endpoints using direct HTTP requests
to the running FastAPI server.
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

def test_health_endpoint():
    """Test the health endpoint"""
    print("🏥 Testing health endpoint...")
    
    try:
        response = requests.get(f"{API_BASE}/contact-scoring/health", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health endpoint: {data['status']} - {data['service']}")
            return True
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health endpoint error: {e}")
        return False

def test_tiers_endpoint():
    """Test the tiers endpoint"""
    print("\n🎯 Testing tiers endpoint...")
    
    try:
        response = requests.get(f"{API_BASE}/contact-scoring/tiers", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Tiers endpoint: {len(data)} tiers returned")
            for tier, description in data.items():
                print(f"   - {tier}: {description[:50]}...")
            return True
        else:
            print(f"❌ Tiers endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Tiers endpoint error: {e}")
        return False

def test_weights_endpoint():
    """Test the weights endpoint"""
    print("\n⚖️ Testing weights endpoint...")
    
    try:
        response = requests.get(f"{API_BASE}/contact-scoring/scoring-weights", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            total_weight = sum(data.values())
            print(f"✅ Weights endpoint: {len(data)} weights, sum = {total_weight:.3f}")
            for weight_name, weight_value in data.items():
                print(f"   - {weight_name}: {weight_value}")
            return True
        else:
            print(f"❌ Weights endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Weights endpoint error: {e}")
        return False

def test_server_connectivity():
    """Test basic server connectivity"""
    print("🔗 Testing server connectivity...")
    
    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server is running: {data.get('message', 'OK')}")
            return True
        else:
            print(f"❌ Server connectivity failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Server connectivity error: {e}")
        return False

def test_api_routes():
    """Test API routes discovery"""
    print("\n📋 Testing API routes...")
    
    try:
        # Try to get OpenAPI docs
        response = requests.get(f"{BASE_URL}/docs", timeout=10)
        
        if response.status_code == 200:
            print("✅ API documentation is accessible")
            return True
        else:
            print(f"❌ API docs failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API docs error: {e}")
        return False

def main():
    """Main test function"""
    
    print("🔍 Contact Scoring API Simple Testing")
    print("=" * 60)
    
    # Wait for server to be ready
    print("⏳ Waiting for server to be ready...")
    time.sleep(5)
    
    tests = [
        test_server_connectivity,
        test_api_routes,
        test_health_endpoint,
        test_tiers_endpoint,
        test_weights_endpoint
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    exit(main()) 