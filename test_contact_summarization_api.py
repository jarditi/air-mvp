#!/usr/bin/env python3
"""
Test script for Contact Summarization API endpoints (Task 3.6.2)
Tests the AI-powered contact summarization functionality
"""

import json
import requests
import uuid
from datetime import datetime, timedelta

# API Configuration
BASE_URL = "http://localhost:8000/api/v1"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0NDk0MjgwNS0zY2E1LTQ3MDAtODc4Ni0yNTEzZjc4ZmJiM2IiLCJlbWFpbCI6ImNhbGVuZGFyX3Rlc3RfMjAyNTA2MThfMTQyNzM5QGV4YW1wbGUuY29tIiwiYXV0aF9wcm92aWRlciI6InRlc3QiLCJpYXQiOjE3NTAzNzIyMTksImV4cCI6MTc1MDM3NDAxOX0._gmhxCPYdEMjJc-4tYeTwIo6JyrNcsyS_RFkN6tQ3No"  # Valid JWT token for test user
}

def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'='*60}")
    print(f"🧠 {title}")
    print('='*60)

def print_test(test_name: str):
    """Print a formatted test header"""
    print(f"\n📋 Testing: {test_name}")
    print("-" * 40)

def test_contact_summarization_endpoints():
    """Test all contact summarization API endpoints"""
    
    print_section("CONTACT SUMMARIZATION API TESTS - TASK 3.6.2")
    print("Testing AI-powered contact summarization functionality")
    
    # Test contact ID (existing contact in database)
    test_contact_id = "550e8400-e29b-41d4-a716-446655440000"
    
    # Test 1: Generate Comprehensive Summary
    print_test("Comprehensive Contact Summary")
    try:
        summary_request = {
            "summary_type": "comprehensive",
            "force_refresh": True
        }
        
        response = requests.post(
            f"{BASE_URL}/contacts/{test_contact_id}/summary",
            headers=HEADERS,
            json=summary_request,
            timeout=30
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            summary_data = response.json()
            print(f"   ✅ Generated comprehensive summary")
            print(f"   - Summary Type: {summary_data.get('summary_type', 'N/A')}")
            print(f"   - Generated At: {summary_data.get('generated_at', 'N/A')}")
            print(f"   - Cache TTL: {summary_data.get('cache_ttl_hours', 'N/A')} hours")
            
            # Show summary content (truncated)
            summary_text = summary_data.get('summary', {}).get('summary', 'N/A')
            if summary_text and len(summary_text) > 150:
                print(f"   - Summary: {summary_text[:150]}...")
            else:
                print(f"   - Summary: {summary_text}")
                
            # Show talking points if available
            talking_points = summary_data.get('summary', {}).get('talking_points', [])
            if talking_points:
                print(f"   - Talking Points: {len(talking_points)} items")
                
        elif response.status_code == 404:
            print(f"   ⚠️  Contact not found (expected for test contact)")
            print(f"   Response: {response.text}")
        else:
            print(f"   ❌ Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
    
    # Test 2: Generate Brief Summary
    print_test("Brief Contact Summary")
    try:
        summary_request = {
            "summary_type": "brief",
            "force_refresh": False
        }
        
        response = requests.post(
            f"{BASE_URL}/contacts/{test_contact_id}/summary",
            headers=HEADERS,
            json=summary_request,
            timeout=30
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            summary_data = response.json()
            print(f"   ✅ Generated brief summary")
            print(f"   - Summary Type: {summary_data.get('summary_type', 'N/A')}")
            print(f"   - From Cache: {'Yes' if summary_data.get('from_cache') else 'No'}")
            
        elif response.status_code == 404:
            print(f"   ⚠️  Contact not found (expected for test contact)")
        else:
            print(f"   ❌ Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
    
    # Test 3: Generate Pre-Meeting Summary
    print_test("Pre-Meeting Contact Summary")
    try:
        meeting_request = {
            "meeting_context": "Quarterly business review meeting to discuss project collaboration",
            "meeting_date": (datetime.now() + timedelta(days=1)).isoformat(),
            "include_recent_interactions": True
        }
        
        response = requests.post(
            f"{BASE_URL}/contacts/{test_contact_id}/summary/meeting",
            headers=HEADERS,
            json=meeting_request,
            timeout=30
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            meeting_data = response.json()
            print(f"   ✅ Generated pre-meeting summary")
            print(f"   - Meeting Context: {meeting_data.get('meeting_context', 'N/A')}")
            print(f"   - Meeting Date: {meeting_data.get('meeting_date', 'N/A')}")
            
            # Show meeting notes if available
            meeting_notes = meeting_data.get('summary', {}).get('meeting_notes', [])
            if meeting_notes:
                print(f"   - Meeting Notes: {len(meeting_notes)} items")
                
        elif response.status_code == 404:
            print(f"   ⚠️  Contact not found (expected for test contact)")
        else:
            print(f"   ❌ Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
    
    # Test 4: Generate Relationship Status Summary
    print_test("Relationship Status Summary")
    try:
        summary_request = {
            "summary_type": "relationship_status",
            "force_refresh": True
        }
        
        response = requests.post(
            f"{BASE_URL}/contacts/{test_contact_id}/summary",
            headers=HEADERS,
            json=summary_request,
            timeout=30
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            status_data = response.json()
            print(f"   ✅ Generated relationship status summary")
            
            # Show insights if available
            insights = status_data.get('summary', {}).get('insights', {})
            if insights:
                print(f"   - Insights: {len(insights)} categories")
                
            # Show recommendations if available
            recommendations = status_data.get('summary', {}).get('recommendations', [])
            if recommendations:
                print(f"   - Recommendations: {len(recommendations)} items")
                
        elif response.status_code == 404:
            print(f"   ⚠️  Contact not found (expected for test contact)")
        else:
            print(f"   ❌ Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
    
    # Test 5: Generate Updates Summary
    print_test("Contact Updates Summary")
    try:
        summary_request = {
            "summary_type": "updates",
            "force_refresh": False
        }
        
        response = requests.post(
            f"{BASE_URL}/contacts/{test_contact_id}/summary",
            headers=HEADERS,
            json=summary_request,
            timeout=30
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            updates_data = response.json()
            print(f"   ✅ Generated contact updates summary")
            
            # Show recent changes if available
            recent_changes = updates_data.get('summary', {}).get('recent_changes', [])
            if recent_changes:
                print(f"   - Recent Changes: {len(recent_changes)} items")
                
            # Show action items if available
            action_items = updates_data.get('summary', {}).get('action_items', [])
            if action_items:
                print(f"   - Action Items: {len(action_items)} items")
                
        elif response.status_code == 404:
            print(f"   ⚠️  Contact not found (expected for test contact)")
        else:
            print(f"   ❌ Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
    
    # Test 6: Bulk Contact Summaries
    print_test("Bulk Contact Summaries")
    try:
        bulk_request = {
            "contact_ids": [test_contact_id, str(uuid.uuid4())],
            "summary_type": "brief",
            "max_contacts": 10
        }
        
        response = requests.post(
            f"{BASE_URL}/contacts/summaries/bulk",
            headers=HEADERS,
            json=bulk_request,
            timeout=30
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            bulk_data = response.json()
            summaries = bulk_data.get('summaries', [])
            print(f"   ✅ Generated {len(summaries)} bulk summaries")
            print(f"   - Processing Time: {bulk_data.get('processing_time_seconds', 'N/A')}s")
            print(f"   - Success Rate: {bulk_data.get('success_count', 0)}/{bulk_data.get('total_requested', 0)}")
            
        elif response.status_code == 404:
            print(f"   ⚠️  Bulk endpoint not found (may not be implemented)")
        else:
            print(f"   ❌ Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
    
    # Test 7: Summary History
    print_test("Contact Summary History")
    try:
        response = requests.get(
            f"{BASE_URL}/contacts/{test_contact_id}/summaries/history",
            headers=HEADERS,
            params={"limit": 5},
            timeout=30
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            history_data = response.json()
            summaries = history_data.get('summaries', [])
            print(f"   ✅ Retrieved {len(summaries)} historical summaries")
            
            for summary in summaries[:2]:  # Show first 2
                print(f"   - {summary.get('summary_type', 'N/A')} from {summary.get('generated_at', 'N/A')}")
                
        elif response.status_code == 404:
            print(f"   ⚠️  History endpoint not found or no history available")
        else:
            print(f"   ❌ Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
    
    print_section("CONTACT SUMMARIZATION TESTS COMPLETE")
    print("Task 3.6.2 (Intelligent Contact Summarization) endpoint testing finished")

if __name__ == "__main__":
    test_contact_summarization_endpoints() 