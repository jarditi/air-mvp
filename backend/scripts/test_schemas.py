#!/usr/bin/env python3
"""Test script to validate all Pydantic schemas."""

import sys
import traceback
from datetime import datetime, date
from decimal import Decimal
from uuid import uuid4
from typing import Dict, Any

# Add the backend directory to the path
sys.path.insert(0, '/app')

def test_schema_imports():
    """Test that all schemas can be imported successfully."""
    print("Testing schema imports...")
    
    try:
        from models.schemas import (
            # Base schemas
            BaseSchema, PaginationParams, PaginatedResponse,
            
            # User schemas
            UserCreateSchema, UserUpdateSchema, UserResponseSchema,
            UserLoginSchema, UserPasswordChangeSchema,
            
            # Contact schemas
            ContactCreateSchema, ContactUpdateSchema, ContactResponseSchema,
            ContactSearchSchema, ContactImportSchema,
            
            # Interaction schemas
            InteractionCreateSchema, InteractionUpdateSchema, InteractionResponseSchema,
            InteractionSearchSchema, InteractionStatsResponseSchema,
            
            # Interest schemas
            InterestCreateSchema, InterestUpdateSchema, InterestResponseSchema,
            InterestSearchSchema, InterestStatsResponseSchema,
            
            # Integration schemas
            IntegrationCreateSchema, IntegrationUpdateSchema, IntegrationResponseSchema,
            IntegrationAuthSchema, IntegrationSyncSchema,
            
            # Relationship schemas
            RelationshipCreateSchema, RelationshipUpdateSchema, RelationshipResponseSchema,
            RelationshipNetworkSchema, RelationshipStatsResponseSchema,
            
            # AI Memory schemas
            AIMemoryCreateSchema, AIMemoryUpdateSchema, AIMemoryResponseSchema,
            AIMemoryGenerateSchema, AIMemoryStatsResponseSchema,
            
            # Notification schemas
            NotificationCreateSchema, NotificationUpdateSchema, NotificationResponseSchema,
            NotificationReminderSchema, NotificationStatsResponseSchema,
            
            # Sync Job schemas
            SyncJobCreateSchema, SyncJobUpdateSchema, SyncJobResponseSchema,
            SyncJobRetrySchema, SyncJobStatsResponseSchema,
            
            # Audit Log schemas
            AuditLogCreateSchema, AuditLogUpdateSchema, AuditLogResponseSchema,
            AuditLogExportSchema, AuditLogStatsResponseSchema,
        )
        print("✅ All schema imports successful")
        return True
    except Exception as e:
        print(f"❌ Schema import failed: {e}")
        traceback.print_exc()
        return False


def test_user_schemas():
    """Test User schemas."""
    print("\nTesting User schemas...")
    
    try:
        from models.schemas.user import UserCreateSchema, UserUpdateSchema, UserResponseSchema
        
        # Test UserCreateSchema
        user_data = {
            "email": "test@example.com",
            "password": "password123",
            "first_name": "John",
            "last_name": "Doe",
            "timezone": "UTC"
        }
        user_create = UserCreateSchema(**user_data)
        assert user_create.email == "test@example.com"
        assert user_create.timezone == "UTC"
        
        # Test UserUpdateSchema
        user_update = UserUpdateSchema(first_name="Jane")
        assert user_update.first_name == "Jane"
        
        # Test UserResponseSchema
        response_data = {
            "id": uuid4(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "timezone": "UTC",
            "preferences": {},
            "is_active": True,
            "last_login": None
        }
        user_response = UserResponseSchema(**response_data)
        assert user_response.full_name == "John Doe"
        
        print("✅ User schemas validation successful")
        return True
    except Exception as e:
        print(f"❌ User schemas validation failed: {e}")
        traceback.print_exc()
        return False


def test_contact_schemas():
    """Test Contact schemas."""
    print("\nTesting Contact schemas...")
    
    try:
        from models.schemas.contact import ContactCreateSchema, ContactResponseSchema
        
        # Test ContactCreateSchema
        contact_data = {
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "phone": "+1-555-123-4567",
            "company": "Tech Corp",
            "tags": ["client", "important"]
        }
        contact_create = ContactCreateSchema(**contact_data)
        assert contact_create.first_name == "Alice"
        assert len(contact_create.tags) == 2
        
        # Test ContactResponseSchema
        response_data = {
            "id": uuid4(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "user_id": uuid4(),
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "phone": "+1-555-123-4567",
            "company": "Tech Corp",
            "job_title": None,
            "location": None,
            "birthday": None,
            "notes": None,
            "tags": ["client", "important"],
            "social_profiles": {},
            "custom_fields": {},
            "relationship_strength": None,
            "last_contact_date": None,
            "contact_frequency": None
        }
        contact_response = ContactResponseSchema(**response_data)
        assert contact_response.full_name == "Alice Smith"
        assert contact_response.display_name == "Alice Smith (Tech Corp)"
        
        print("✅ Contact schemas validation successful")
        return True
    except Exception as e:
        print(f"❌ Contact schemas validation failed: {e}")
        traceback.print_exc()
        return False


def test_interaction_schemas():
    """Test Interaction schemas."""
    print("\nTesting Interaction schemas...")
    
    try:
        from models.schemas.interaction import InteractionCreateSchema, InteractionResponseSchema
        
        # Test InteractionCreateSchema
        interaction_data = {
            "contact_id": uuid4(),
            "type": "email",
            "direction": "outbound",
            "subject": "Follow up meeting",
            "content": "Let's schedule a follow-up meeting next week.",
            "occurred_at": datetime.utcnow(),
            "duration_minutes": 30,
            "sentiment_score": Decimal("0.8"),
            "importance_score": Decimal("0.7")
        }
        interaction_create = InteractionCreateSchema(**interaction_data)
        assert interaction_create.type == "email"
        assert interaction_create.direction == "outbound"
        
        # Test InteractionResponseSchema
        response_data = {
            "id": uuid4(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "user_id": uuid4(),
            "contact_id": uuid4(),
            "type": "email",
            "direction": "outbound",
            "subject": "Follow up meeting",
            "content": "Let's schedule a follow-up meeting next week.",
            "occurred_at": datetime.utcnow(),
            "duration_minutes": 30,
            "location": None,
            "attendees": [],
            "sentiment_score": Decimal("0.8"),
            "importance_score": Decimal("0.7"),
            "platform_data": {}
        }
        interaction_response = InteractionResponseSchema(**response_data)
        assert interaction_response.duration_display == "30m"
        
        print("✅ Interaction schemas validation successful")
        return True
    except Exception as e:
        print(f"❌ Interaction schemas validation failed: {e}")
        traceback.print_exc()
        return False


def test_integration_schemas():
    """Test Integration schemas."""
    print("\nTesting Integration schemas...")
    
    try:
        from models.schemas.integration import IntegrationCreateSchema, IntegrationResponseSchema
        from pydantic import SecretStr
        
        # Test IntegrationCreateSchema
        integration_data = {
            "platform": "gmail",
            "platform_user_id": "user123",
            "access_token": SecretStr("secret_token"),
            "scopes": ["read", "write"]
        }
        integration_create = IntegrationCreateSchema(**integration_data)
        assert integration_create.platform == "gmail"
        assert len(integration_create.scopes) == 2
        
        # Test IntegrationResponseSchema
        response_data = {
            "id": uuid4(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "user_id": uuid4(),
            "platform": "gmail",
            "platform_user_id": "user123",
            "token_expires_at": None,
            "scopes": ["read", "write"],
            "settings": {},
            "is_active": True,
            "last_sync_at": None
        }
        integration_response = IntegrationResponseSchema(**response_data)
        assert integration_response.sync_status == "Never Synced"
        
        print("✅ Integration schemas validation successful")
        return True
    except Exception as e:
        print(f"❌ Integration schemas validation failed: {e}")
        traceback.print_exc()
        return False


def test_pagination_schemas():
    """Test pagination schemas."""
    print("\nTesting Pagination schemas...")
    
    try:
        from models.schemas.base import PaginationParams, PaginatedResponse
        
        # Test PaginationParams
        pagination = PaginationParams(page=2, page_size=10)
        assert pagination.get_offset() == 10
        
        # Test PaginatedResponse
        items = [{"id": 1}, {"id": 2}]
        paginated = PaginatedResponse.create(
            items=items,
            total=25,
            page=2,
            page_size=10
        )
        assert paginated.total_pages == 3
        assert len(paginated.items) == 2
        
        print("✅ Pagination schemas validation successful")
        return True
    except Exception as e:
        print(f"❌ Pagination schemas validation failed: {e}")
        traceback.print_exc()
        return False


def test_validation_errors():
    """Test that validation errors are properly raised."""
    print("\nTesting validation errors...")
    
    try:
        from models.schemas.user import UserCreateSchema
        from models.schemas.contact import ContactCreateSchema
        from pydantic import ValidationError
        
        # Test invalid email
        try:
            UserCreateSchema(
                email="invalid-email",
                password="password123",
                first_name="John",
                last_name="Doe"
            )
            assert False, "Should have raised validation error for invalid email"
        except ValidationError:
            pass  # Expected
        
        # Test missing required field
        try:
            ContactCreateSchema()  # Missing required first_name
            assert False, "Should have raised validation error for missing field"
        except ValidationError:
            pass  # Expected
        
        # Test invalid phone number
        try:
            ContactCreateSchema(
                first_name="John",
                phone="123"  # Too short
            )
            assert False, "Should have raised validation error for invalid phone"
        except ValidationError:
            pass  # Expected
        
        print("✅ Validation errors working correctly")
        return True
    except Exception as e:
        print(f"❌ Validation error testing failed: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all schema tests."""
    print("🧪 Starting Pydantic Schema Validation Tests")
    print("=" * 50)
    
    tests = [
        test_schema_imports,
        test_user_schemas,
        test_contact_schemas,
        test_interaction_schemas,
        test_integration_schemas,
        test_pagination_schemas,
        test_validation_errors,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All schema tests passed!")
        return 0
    else:
        print("💥 Some schema tests failed!")
        return 1


if __name__ == "__main__":
    exit(main()) 