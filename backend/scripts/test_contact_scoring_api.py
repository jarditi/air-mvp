#!/usr/bin/env python3
"""
Contact Scoring API Endpoint Testing Script

This script tests all contact scoring API endpoints to ensure they work correctly:
1. Health check endpoint
2. Score individual contact
3. Batch scoring
4. Score all contacts with filters
5. Scoring statistics
6. Get tiers and weights
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import json
import uuid

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from lib.database import get_db
from models.orm.contact import Contact
from models.orm.interaction import Interaction
from models.orm.user import User
from main import app

# Test configuration
TEST_USER_EMAIL = f"api-test-{int(datetime.now().timestamp())}@example.com"
SAMPLE_CONTACTS = [
    {
        "name": "Alice Johnson",
        "email": "alice.johnson@techcorp.com",
        "company": "TechCorp Inc",
        "job_title": "VP of Engineering",
        "interactions": [
            {"type": "meeting", "direction": "mutual", "days_ago": 2, "duration": 60},
            {"type": "email", "direction": "inbound", "days_ago": 5, "content": "Thanks for the great meeting!"},
            {"type": "meeting", "direction": "mutual", "days_ago": 14, "duration": 45},
        ]
    },
    {
        "name": "Bob Smith",
        "email": "bob.smith@startup.io",
        "company": "Startup.io",
        "job_title": "Founder & CEO",
        "interactions": [
            {"type": "email", "direction": "outbound", "days_ago": 45, "content": "Hi Bob, great to meet you."},
            {"type": "meeting", "direction": "mutual", "days_ago": 60, "duration": 90},
        ]
    },
    {
        "name": "Carol Davis",
        "email": "carol.davis@enterprise.com",
        "company": "Enterprise Solutions",
        "job_title": "Senior Manager",
        "interactions": [
            {"type": "meeting", "direction": "mutual", "days_ago": 1, "duration": 30},
            {"type": "email", "direction": "inbound", "days_ago": 3, "content": "Quick update on the project."},
            {"type": "email", "direction": "outbound", "days_ago": 7, "content": "Thanks for the update."},
        ]
    }
]


class ContactScoringAPITester:
    """Tester for contact scoring API endpoints"""
    
    def __init__(self):
        self.client = TestClient(app)
        self.db = next(get_db())
        self.test_user_id = None
        self.test_contacts = []
        self.auth_headers = {}
    
    async def run_tests(self):
        """Run comprehensive API endpoint tests"""
        
        print("🔍 Contact Scoring API Endpoint Testing")
        print("=" * 60)
        
        try:
            # Setup test data
            await self._setup_test_data()
            
            # Run API tests
            await self._test_health_endpoint()
            await self._test_get_tiers_endpoint()
            await self._test_get_weights_endpoint()
            await self._test_score_individual_contact()
            await self._test_batch_scoring()
            await self._test_score_all_contacts()
            await self._test_scoring_stats()
            await self._test_error_handling()
            
            print("\n✅ All API endpoint tests completed successfully!")
            
        except Exception as e:
            print(f"\n❌ API testing failed: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            # Cleanup test data
            await self._cleanup_test_data()
    
    async def _setup_test_data(self):
        """Setup test user and contacts"""
        
        print("\n📋 Setting up test data...")
        
        # Create test user
        test_user = User(
            email=TEST_USER_EMAIL,
            auth_provider="test",
            auth_provider_id="test-api-user-123",
            full_name="API Test User",
            is_active=True
        )
        self.db.add(test_user)
        self.db.commit()
        self.test_user_id = test_user.id
        
        # Mock auth headers (in real app, this would come from JWT)
        self.auth_headers = {"Authorization": f"Bearer test-token-{self.test_user_id}"}
        
        # Create test contacts with interactions
        for contact_data in SAMPLE_CONTACTS:
            contact = Contact(
                user_id=self.test_user_id,
                email=contact_data["email"],
                full_name=contact_data["name"],
                first_name=contact_data["name"].split()[0],
                last_name=contact_data["name"].split()[-1],
                company=contact_data["company"],
                job_title=contact_data["job_title"],
                contact_source="test"
            )
            self.db.add(contact)
            self.db.commit()
            
            # Create interactions
            for interaction_data in contact_data["interactions"]:
                interaction_date = datetime.now(timezone.utc) - timedelta(days=interaction_data["days_ago"])
                
                interaction = Interaction(
                    user_id=self.test_user_id,
                    contact_id=contact.id,
                    interaction_type=interaction_data["type"],
                    direction=interaction_data["direction"],
                    interaction_date=interaction_date,
                    content=interaction_data.get("content", ""),
                    duration_minutes=interaction_data.get("duration"),
                    source_platform="test"
                )
                self.db.add(interaction)
            
            self.db.commit()
            self.test_contacts.append(contact)
        
        print(f"✅ Created {len(self.test_contacts)} test contacts with interactions")
    
    async def _test_health_endpoint(self):
        """Test health check endpoint"""
        
        print("\n🏥 Testing health endpoint...")
        
        response = self.client.get("/api/v1/contact-scoring/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "contact-scoring"
        assert "timestamp" in data
        
        print("✅ Health endpoint working correctly")
    
    async def _test_get_tiers_endpoint(self):
        """Test get contact tiers endpoint"""
        
        print("\n🎯 Testing get tiers endpoint...")
        
        response = self.client.get("/api/v1/contact-scoring/tiers")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check all expected tiers are present
        expected_tiers = ["inner_circle", "strong_network", "active_network", "peripheral", "dormant"]
        for tier in expected_tiers:
            assert tier in data
            assert len(data[tier]) > 10  # Description should be meaningful
        
        print(f"✅ Tiers endpoint returned {len(data)} contact tiers")
    
    async def _test_get_weights_endpoint(self):
        """Test get default scoring weights endpoint"""
        
        print("\n⚖️ Testing get weights endpoint...")
        
        response = self.client.get("/api/v1/contact-scoring/scoring-weights")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check all expected weights are present
        expected_weights = [
            "frequency_weight", "recency_weight", "meeting_consistency_weight",
            "response_reliability_weight", "communication_quality_weight",
            "sentiment_weight", "professional_context_weight", "relationship_trajectory_weight"
        ]
        
        for weight in expected_weights:
            assert weight in data
            assert 0.0 <= data[weight] <= 1.0
        
        # Check weights sum to 1.0
        total_weight = sum(data.values())
        assert abs(total_weight - 1.0) < 0.001
        
        print(f"✅ Weights endpoint returned {len(data)} weights (sum: {total_weight:.3f})")
    
    async def _test_score_individual_contact(self):
        """Test scoring individual contact endpoint"""
        
        print("\n👤 Testing individual contact scoring...")
        
        # Test with first contact
        contact = self.test_contacts[0]
        
        # Mock the auth dependency for testing
        def mock_get_current_user():
            return self.db.query(User).filter(User.id == self.test_user_id).first()
        
        # Override the dependency
        from api.routes.contact_scoring import get_current_user
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            response = self.client.post(
                f"/api/v1/contact-scoring/score-contact/{contact.id}",
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Validate response structure
            assert data["contact_id"] == str(contact.id)
            assert 0.0 <= data["overall_score"] <= 1.0
            assert data["tier"] in ["inner_circle", "strong_network", "active_network", "peripheral", "dormant"]
            assert "tier_description" in data
            assert "score_interpretation" in data
            
            # Check component scores
            component_scores = [
                "frequency_score", "recency_score", "meeting_consistency_score",
                "response_reliability_score", "communication_quality_score",
                "sentiment_score", "professional_context_score", "trajectory_score"
            ]
            
            for score in component_scores:
                assert score in data
                assert 0.0 <= data[score] <= 1.0
            
            # Check metrics
            assert "metrics" in data
            metrics = data["metrics"]
            assert metrics["total_interactions"] >= 0
            assert metrics["days_since_last_interaction"] >= 0
            
            # Check insights and recommendations
            assert isinstance(data["insights"], list)
            assert isinstance(data["recommendations"], list)
            assert 0.0 <= data["confidence_level"] <= 1.0
            
            print(f"✅ Individual scoring: {contact.full_name} scored {data['overall_score']:.3f} ({data['tier']})")
            
        finally:
            # Clean up dependency override
            app.dependency_overrides.clear()
    
    async def _test_batch_scoring(self):
        """Test batch scoring endpoint"""
        
        print("\n📦 Testing batch scoring...")
        
        # Mock auth dependency
        def mock_get_current_user():
            return self.db.query(User).filter(User.id == self.test_user_id).first()
        
        from api.routes.contact_scoring import get_current_user
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            # Test batch scoring with custom weights
            contact_ids = [str(contact.id) for contact in self.test_contacts[:2]]
            
            request_data = {
                "contact_ids": contact_ids,
                "custom_weights": {
                    "frequency_weight": 0.4,
                    "recency_weight": 0.3,
                    "meeting_consistency_weight": 0.1,
                    "response_reliability_weight": 0.1,
                    "communication_quality_weight": 0.05,
                    "sentiment_weight": 0.03,
                    "professional_context_weight": 0.01,
                    "relationship_trajectory_weight": 0.01
                }
            }
            
            response = self.client.post(
                "/api/v1/contact-scoring/score-contacts-batch",
                json=request_data,
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should return results for requested contacts
            assert len(data) == len(contact_ids)
            
            for result in data:
                assert result["contact_id"] in contact_ids
                assert 0.0 <= result["overall_score"] <= 1.0
                assert result["tier"] in ["inner_circle", "strong_network", "active_network", "peripheral", "dormant"]
            
            print(f"✅ Batch scoring: {len(data)} contacts scored with custom weights")
            
        finally:
            app.dependency_overrides.clear()
    
    async def _test_score_all_contacts(self):
        """Test score all contacts endpoint with filters"""
        
        print("\n🌐 Testing score all contacts...")
        
        # Mock auth dependency
        def mock_get_current_user():
            return self.db.query(User).filter(User.id == self.test_user_id).first()
        
        from api.routes.contact_scoring import get_current_user
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            # Test without filters
            response = self.client.get(
                "/api/v1/contact-scoring/score-all-contacts",
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should return all test contacts
            assert len(data) == len(self.test_contacts)
            
            # Should be sorted by score (highest first)
            scores = [result["overall_score"] for result in data]
            assert scores == sorted(scores, reverse=True)
            
            print(f"✅ Score all contacts: {len(data)} contacts returned, properly sorted")
            
            # Test with filters
            response = self.client.get(
                "/api/v1/contact-scoring/score-all-contacts?limit=2&min_score=0.0",
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            filtered_data = response.json()
            
            # Should respect limit
            assert len(filtered_data) <= 2
            
            print(f"✅ Filtered results: {len(filtered_data)} contacts with limit=2")
            
        finally:
            app.dependency_overrides.clear()
    
    async def _test_scoring_stats(self):
        """Test scoring statistics endpoint"""
        
        print("\n📊 Testing scoring statistics...")
        
        # Mock auth dependency
        def mock_get_current_user():
            return self.db.query(User).filter(User.id == self.test_user_id).first()
        
        from api.routes.contact_scoring import get_current_user
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            response = self.client.get(
                "/api/v1/contact-scoring/scoring-stats",
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Check required fields
            assert data["total_contacts"] == len(self.test_contacts)
            assert "tier_distribution" in data
            assert "average_score" in data
            assert "score_distribution" in data
            assert "top_contacts" in data
            
            # Check tier distribution
            tier_dist = data["tier_distribution"]
            total_in_tiers = sum(tier_dist.values())
            assert total_in_tiers == len(self.test_contacts)
            
            # Check score distribution
            score_dist = data["score_distribution"]
            expected_ranges = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
            for range_key in expected_ranges:
                assert range_key in score_dist
            
            # Check average score
            assert 0.0 <= data["average_score"] <= 1.0
            
            # Check top contacts
            assert len(data["top_contacts"]) <= 5
            
            print(f"✅ Statistics: {data['total_contacts']} contacts, avg score {data['average_score']:.3f}")
            
        finally:
            app.dependency_overrides.clear()
    
    async def _test_error_handling(self):
        """Test error handling scenarios"""
        
        print("\n⚠️ Testing error handling...")
        
        # Mock auth dependency
        def mock_get_current_user():
            return self.db.query(User).filter(User.id == self.test_user_id).first()
        
        from api.routes.contact_scoring import get_current_user
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            # Test invalid contact ID
            response = self.client.post(
                "/api/v1/contact-scoring/score-contact/invalid-id",
                headers=self.auth_headers
            )
            
            assert response.status_code == 404
            
            # Test invalid tier filter
            response = self.client.get(
                "/api/v1/contact-scoring/score-all-contacts?tier_filter=invalid_tier",
                headers=self.auth_headers
            )
            
            assert response.status_code == 400
            
            # Test batch scoring with invalid contact IDs
            request_data = {
                "contact_ids": ["invalid-id-1", "invalid-id-2"]
            }
            
            response = self.client.post(
                "/api/v1/contact-scoring/score-contacts-batch",
                json=request_data,
                headers=self.auth_headers
            )
            
            # Should return 200 but with empty results (graceful handling)
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 0
            
            print("✅ Error handling working correctly")
            
        finally:
            app.dependency_overrides.clear()
    
    async def _cleanup_test_data(self):
        """Clean up test data"""
        
        print("\n🧹 Cleaning up test data...")
        
        if self.test_user_id:
            # Delete interactions
            self.db.query(Interaction).filter(
                Interaction.user_id == self.test_user_id
            ).delete()
            
            # Delete contacts
            self.db.query(Contact).filter(
                Contact.user_id == self.test_user_id
            ).delete()
            
            # Delete user
            self.db.query(User).filter(
                User.id == self.test_user_id
            ).delete()
            
            self.db.commit()
        
        print("✅ Test data cleaned up")


async def main():
    """Main testing function"""
    
    tester = ContactScoringAPITester()
    await tester.run_tests()


if __name__ == "__main__":
    asyncio.run(main()) 