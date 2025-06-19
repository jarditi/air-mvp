#!/usr/bin/env python3
"""
API Test script for Contact Summarization endpoints

This script tests the REST API endpoints for contact summarization
through HTTP requests to verify the complete functionality.
"""

import requests
import json
import sys
from datetime import datetime, timedelta
from uuid import uuid4

# API base URL
BASE_URL = "http://localhost:8000/api/v1"

# Test token (replace with actual token)
AUTH_TOKEN = "eyJhbGciOiJSUzI1NiIsImNhdCI6ImNsX0I3ZDRQRDExMUFBQSIsImtpZCI6Imluc18yeVl5UURNaENvN21oYjNoSlBQYll3bEtxdEkiLCJ0eXAiOiJKV1QifQ.eyJleHAiOjE3NTAyNjc1MTksImZ2YSI6Wzk5OTk5LC0xXSwiaWF0IjoxNzUwMjY3NDU5LCJpc3MiOiJodHRwczovL3dlbGNvbWUtc2hhZC0xOC5jbGVyay5hY2NvdW50cy5kZXYiLCJuYmYiOjE3NTAyNjc0NDksInNpZCI6InNlc3NfMnlnc0gzYzV2QjRKV3k2dHlhOVVNSWpubmhNIiwic3ViIjoidXNlcl8yeWdzSDRNWXhvRmd1bHRVTEJ2cXpFU2ZLSE4iLCJ2IjoyfQ.aDhKB69OaMjFcFGmSNv-2iTh-j2ZB4X8DOHTh_PdoAfjtNhm-YwPO84g9Vc-r3cWiy7JotGPyZeDZYHpv84a7sDqUANQ3myZ3AJILTauGUiFzThqM_ebct1ULxsT9bymINzZShYIV2o14BTmnNT2XzvJnD-wWdQfNGfsDo8KXtByOqnPs_G7T0c8jH9m-sJDj6Pi1xsKCA1_x0SqU84bU40-qGB52Vmoay27yTay74q0UYY3vka_Tf01Aftwz84AV4syCjEf851b7wy_F4H4RcQP25X5Z2L4eCnb-2JL9kk2xG2OzLXptxCNMvzQL49rIVwffgGBW6cD7qcMF_Q7Zg"

HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json"
}


def test_contact_summarization_api():
    """Test contact summarization API endpoints."""
    
    print("🚀 Testing Contact Summarization API Endpoints")
    print("=" * 60)
    
    # Test contact ID (you'd need to replace with actual contact ID)
    test_contact_id = "550e8400-e29b-41d4-a716-446655440000"  # UUID format
    
    # Test 1: Get Available Summary Types
    print("\n📋 Testing Available Summary Types...")
    try:
        response = requests.get(f"{BASE_URL}/summary-types", headers=HEADERS)
        if response.status_code == 200:
            types_data = response.json()
            print(f"✅ Retrieved {len(types_data['summary_types'])} summary types")
            for summary_type in types_data['summary_types']:
                print(f"   - {summary_type['name']}: {summary_type['description']}")
        else:
            print(f"❌ Failed to get summary types: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error getting summary types: {e}")
    
    # Test 2: Generate Comprehensive Summary
    print("\n📊 Testing Comprehensive Summary Generation...")
    try:
        data = {
            "summary_type": "comprehensive",
            "force_refresh": True
        }
        response = requests.post(
            f"{BASE_URL}/contacts/{test_contact_id}/summary",
            headers=HEADERS,
            json=data
        )
        
        if response.status_code == 200:
            summary = response.json()
            print(f"✅ Generated comprehensive summary")
            print(f"   📝 Contact: {summary['contact_name']}")
            print(f"   📄 Summary length: {len(summary['summary'])} chars")
            print(f"   💡 Talking points: {len(summary['talking_points'])}")
            print(f"   🤖 Model used: {summary['model_used']}")
            print(f"   💾 Cached: {summary['cached']}")
        else:
            print(f"❌ Failed to generate summary: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error generating comprehensive summary: {e}")
    
    # Test 3: Get Brief Summary
    print("\n⚡ Testing Brief Summary...")
    try:
        response = requests.get(
            f"{BASE_URL}/contacts/{test_contact_id}/summary/brief",
            headers=HEADERS
        )
        
        if response.status_code == 200:
            summary = response.json()
            print(f"✅ Generated brief summary")
            print(f"   📝 Contact: {summary['contact_name']}")
            print(f"   📄 Summary length: {len(summary['summary'])} chars")
            print(f"   💡 Talking points: {len(summary['talking_points'])}")
        else:
            print(f"❌ Failed to get brief summary: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error getting brief summary: {e}")
    
    # Test 4: Generate Pre-Meeting Summary
    print("\n🤝 Testing Pre-Meeting Summary...")
    try:
        data = {
            "meeting_context": "Quarterly review meeting to discuss project progress and Q2 goals",
            "meeting_date": (datetime.utcnow() + timedelta(hours=2)).isoformat()
        }
        response = requests.post(
            f"{BASE_URL}/contacts/{test_contact_id}/summary/meeting",
            headers=HEADERS,
            json=data
        )
        
        if response.status_code == 200:
            summary = response.json()
            print(f"✅ Generated pre-meeting summary")
            print(f"   📝 Contact: {summary['contact_name']}")
            print(f"   📅 Meeting context: {summary['meeting_context']}")
            print(f"   💡 Talking points: {len(summary['talking_points'])}")
        else:
            print(f"❌ Failed to generate pre-meeting summary: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error generating pre-meeting summary: {e}")
    
    # Test 5: Get Relationship Status
    print("\n❤️ Testing Relationship Status...")
    try:
        response = requests.get(
            f"{BASE_URL}/contacts/{test_contact_id}/summary/relationship-status",
            headers=HEADERS
        )
        
        if response.status_code == 200:
            summary = response.json()
            print(f"✅ Generated relationship status summary")
            print(f"   📝 Contact: {summary['contact_name']}")
            print(f"   💪 Relationship insights: {len(summary['relationship_insights'])}")
            print(f"   📊 Relationship strength: {summary['relationship_strength']}/10")
        else:
            print(f"❌ Failed to get relationship status: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error getting relationship status: {e}")
    
    # Test 6: Get Updates Summary
    print("\n🔄 Testing Updates Summary...")
    try:
        response = requests.get(
            f"{BASE_URL}/contacts/{test_contact_id}/summary/updates",
            headers=HEADERS
        )
        
        if response.status_code == 200:
            summary = response.json()
            print(f"✅ Generated updates summary")
            print(f"   📝 Contact: {summary['contact_name']}")
            print(f"   📄 Summary length: {len(summary['summary'])} chars")
        else:
            print(f"❌ Failed to get updates summary: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error getting updates summary: {e}")
    
    # Test 7: Batch Summary Generation
    print("\n📦 Testing Batch Summary Generation...")
    try:
        data = {
            "contact_ids": [
                test_contact_id,
                "550e8400-e29b-41d4-a716-446655440001"  # Another test UUID
            ],
            "summary_type": "brief",
            "max_contacts": 10
        }
        response = requests.post(
            f"{BASE_URL}/contacts/summaries/batch",
            headers=HEADERS,
            json=data
        )
        
        if response.status_code == 200:
            batch_result = response.json()
            print(f"✅ Generated batch summaries")
            print(f"   📊 Requested: {batch_result['total_requested']}")
            print(f"   ✅ Generated: {batch_result['total_generated']}")
            for i, summary in enumerate(batch_result['summaries']):
                print(f"   {i+1}. {summary['contact_name']}: {len(summary['summary'])} chars")
        else:
            print(f"❌ Failed to generate batch summaries: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error generating batch summaries: {e}")
    
    # Test 8: Cache Invalidation
    print("\n🗑️ Testing Cache Invalidation...")
    try:
        response = requests.delete(
            f"{BASE_URL}/contacts/{test_contact_id}/summary/cache",
            headers=HEADERS
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Cache invalidated successfully")
            print(f"   📝 Message: {result['message']}")
        else:
            print(f"❌ Failed to invalidate cache: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error invalidating cache: {e}")
    
    # Test 9: Get Summary with Parameters
    print("\n🔍 Testing Summary with Parameters...")
    try:
        params = {
            "summary_type": "comprehensive",
            "max_age_hours": 24
        }
        response = requests.get(
            f"{BASE_URL}/contacts/{test_contact_id}/summary",
            headers=HEADERS,
            params=params
        )
        
        if response.status_code == 200:
            summary = response.json()
            print(f"✅ Retrieved summary with parameters")
            print(f"   📝 Contact: {summary['contact_name']}")
            print(f"   📄 Type: {summary['summary_type']}")
            print(f"   💾 Cached: {summary['cached']}")
        else:
            print(f"❌ Failed to get summary with parameters: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error getting summary with parameters: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 Contact Summarization API Testing Complete!")


def test_auth_endpoint():
    """Test authentication before running main tests."""
    print("🔐 Testing Authentication...")
    try:
        response = requests.get(f"{BASE_URL}/auth/me", headers=HEADERS)
        if response.status_code == 200:
            user_data = response.json()
            print(f"✅ Authentication successful - User: {user_data.get('id', 'Unknown')}")
            return True
        else:
            print(f"❌ Authentication failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return False


def test_health_check():
    """Test health endpoint to verify API is running."""
    print("🏥 Testing API Health...")
    try:
        response = requests.get(f"{BASE_URL.replace('/api/v1', '')}/health/")
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ API is healthy - Status: {health_data.get('status', 'unknown')}")
            return True
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False


if __name__ == "__main__":
    print("🧪 Starting Contact Summarization API Tests...")
    
    # Check API health first
    if not test_health_check():
        print("❌ API is not healthy. Please start the backend service.")
        sys.exit(1)
    
    # Check authentication
    if not test_auth_endpoint():
        print("❌ Authentication failed. Please check your token.")
        print("ℹ️ Continuing with tests (some may fail due to auth issues)...")
    
    # Run main tests
    try:
        test_contact_summarization_api()
        print("\n✅ All API tests completed!")
    except Exception as e:
        print(f"\n❌ API tests failed: {e}")
        sys.exit(1) 