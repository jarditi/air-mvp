#!/usr/bin/env python3
"""Test script to validate all ORM models and their relationships."""

import asyncio
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


async def test_model_imports():
    """Test that all models can be imported."""
    print("🔍 Testing model imports...")
    
    try:
        from models.orm import (
            BaseModel, User, Contact, Interaction, Interest,
            Integration, Relationship, AIMemory, Notification, 
            SyncJob, AuditLog
        )
        print("✅ All 11 models imported successfully")
        return True
    except Exception as e:
        print(f"❌ ERROR: Model import failed: {e}")
        return False


async def test_model_instantiation():
    """Test that all models can be instantiated."""
    print("\n🔍 Testing model instantiation...")
    
    try:
        from models.orm import (
            User, Contact, Interaction, Interest,
            Integration, Relationship, AIMemory, Notification, 
            SyncJob, AuditLog
        )
        
        # Test core models
        user = User(email="test@example.com", auth_provider="test", auth_provider_id="123")
        contact = Contact(full_name="Test Contact", email="contact@example.com")
        interaction = Interaction(interaction_type="email", direction="outbound", interaction_date="2024-01-01")
        interest = Interest(interest_category="technology", interest_topic="AI", confidence_score=0.8)
        
        # Test additional models
        integration = Integration(platform="gmail", status="connected")
        relationship = Relationship(relationship_type="colleague", strength_score=0.7)
        ai_memory = AIMemory(memory_type="summary", content="Test memory content")
        notification = Notification(notification_type="follow_up", title="Test", message="Test message")
        sync_job = SyncJob(job_type="full_sync", status="pending")
        audit_log = AuditLog(action="create", resource_type="contact")
        
        print("✅ All 10 models can be instantiated")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: Model instantiation failed: {e}")
        return False


async def test_model_attributes():
    """Test that models have expected attributes."""
    print("\n🔍 Testing model attributes...")
    
    try:
        from models.orm import User, Contact, Integration
        
        # Test User model attributes
        user_attrs = ['email', 'auth_provider', 'full_name', 'subscription_tier', 'created_at']
        user = User(email="test@example.com", auth_provider="test", auth_provider_id="123")
        for attr in user_attrs:
            if not hasattr(user, attr):
                print(f"❌ ERROR: User missing attribute: {attr}")
                return False
        
        # Test Contact model attributes
        contact_attrs = ['full_name', 'email', 'company', 'relationship_strength', 'tags']
        contact = Contact(full_name="Test Contact")
        for attr in contact_attrs:
            if not hasattr(contact, attr):
                print(f"❌ ERROR: Contact missing attribute: {attr}")
                return False
        
        # Test Integration model attributes
        integration_attrs = ['platform', 'status', 'access_token', 'scope', 'platform_metadata']
        integration = Integration(platform="gmail")
        for attr in integration_attrs:
            if not hasattr(integration, attr):
                print(f"❌ ERROR: Integration missing attribute: {attr}")
                return False
        
        print("✅ All models have expected attributes")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: Model attribute test failed: {e}")
        return False


async def test_model_relationships():
    """Test that model relationships are properly defined."""
    print("\n🔍 Testing model relationships...")
    
    try:
        from models.orm import User, Contact, Interaction, Integration
        
        # Test User relationships
        user = User(email="test@example.com", auth_provider="test", auth_provider_id="123")
        expected_user_rels = ['contacts', 'interactions', 'interests', 'integrations', 'relationships', 'ai_memories', 'notifications', 'sync_jobs', 'audit_logs']
        for rel in expected_user_rels:
            if not hasattr(user, rel):
                print(f"❌ ERROR: User missing relationship: {rel}")
                return False
        
        # Test Contact relationships
        contact = Contact(full_name="Test Contact")
        expected_contact_rels = ['user', 'interactions', 'interests', 'ai_memories', 'notifications', 'relationships_as_a', 'relationships_as_b']
        for rel in expected_contact_rels:
            if not hasattr(contact, rel):
                print(f"❌ ERROR: Contact missing relationship: {rel}")
                return False
        
        print("✅ All model relationships are properly defined")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: Model relationship test failed: {e}")
        return False


async def test_model_table_names():
    """Test that models have correct table names."""
    print("\n🔍 Testing model table names...")
    
    try:
        from models.orm import (
            User, Contact, Interaction, Interest,
            Integration, Relationship, AIMemory, Notification, 
            SyncJob, AuditLog
        )
        
        expected_tables = {
            User: 'users',
            Contact: 'contacts', 
            Interaction: 'interactions',
            Interest: 'interests',
            Integration: 'integrations',
            Relationship: 'relationships',
            AIMemory: 'ai_memories',
            Notification: 'notifications',
            SyncJob: 'sync_jobs',
            AuditLog: 'audit_logs'
        }
        
        for model_class, expected_table in expected_tables.items():
            if model_class.__tablename__ != expected_table:
                print(f"❌ ERROR: {model_class.__name__} has wrong table name: {model_class.__tablename__} (expected: {expected_table})")
                return False
        
        print("✅ All models have correct table names")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: Table name test failed: {e}")
        return False


async def main():
    """Run all model tests."""
    print("🚀 Starting comprehensive ORM model tests...\n")
    
    tests = [
        test_model_imports(),
        test_model_instantiation(),
        test_model_attributes(),
        test_model_relationships(),
        test_model_table_names()
    ]
    
    results = await asyncio.gather(*tests, return_exceptions=True)
    
    passed = sum(1 for result in results if result is True)
    total = len(results)
    
    if passed == total:
        print(f"\n🎉 All {total} tests passed! ORM models are ready.")
        return 0
    else:
        print(f"\n❌ {total - passed} out of {total} tests failed.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 