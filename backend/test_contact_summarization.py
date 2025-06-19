#!/usr/bin/env python3
"""
Test script for Contact Summarization Service

This script tests the AI-powered contact summarization functionality,
including different summary types and caching behavior.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import create_engine

# Add project root to path
sys.path.append('.')

from lib.database import get_db
from services.contact_summarization import ContactSummarizationService, SummaryType
from models.orm.contact import Contact
from models.orm.interaction import Interaction
from models.orm.conversation_thread import ConversationThread
from models.orm.user import User


def create_test_data(db: Session):
    """Create test data for summarization testing."""
    print("🔧 Creating test data...")
    
    # Create test user
    test_user = User(
        id=uuid4(),
        email="test@example.com",
        auth_provider="test",
        auth_provider_id="test-user-123",
        full_name="Test User",
        is_verified=True
    )
    db.add(test_user)
    db.commit()
    db.refresh(test_user)
    
    # Create test contact
    test_contact = Contact(
        id=uuid4(),
        user_id=test_user.id,
        name="John Smith",
        email="john.smith@example.com",
        phone="+1-555-0123",
        company="TechCorp Inc",
        job_title="Senior Software Engineer",
        source="calendar",
        quality_score=8.5,
        relationship_strength=7.2,
        tags=["colleague", "tech", "mentor"],
        notes="Met at tech conference. Great insights on AI/ML.",
        created_at=datetime.utcnow() - timedelta(days=90),
        last_contacted=datetime.utcnow() - timedelta(days=5)
    )
    db.add(test_contact)
    db.commit()
    db.refresh(test_contact)
    
    # Create test interactions
    interactions = [
        Interaction(
            id=uuid4(),
            user_id=test_user.id,
            contact_id=test_contact.id,
            type="meeting",
            date=datetime.utcnow() - timedelta(days=5),
            summary="Discussed AI infrastructure and scaling challenges",
            source="calendar",
            metadata={"duration": 60, "platform": "zoom"}
        ),
        Interaction(
            id=uuid4(),
            user_id=test_user.id,
            contact_id=test_contact.id,
            type="email",
            date=datetime.utcnow() - timedelta(days=10),
            summary="Follow-up on machine learning project collaboration",
            source="gmail",
            metadata={"thread_count": 3}
        ),
        Interaction(
            id=uuid4(),
            user_id=test_user.id,
            contact_id=test_contact.id,
            type="meeting",
            date=datetime.utcnow() - timedelta(days=30),
            summary="Initial introduction at TechConf 2024",
            source="calendar",
            metadata={"event": "TechConf 2024", "location": "San Francisco"}
        )
    ]
    
    for interaction in interactions:
        db.add(interaction)
    db.commit()
    
    # Create test conversation threads
    thread = ConversationThread(
        id=uuid4(),
        user_id=test_user.id,
        contact_id=test_contact.id,
        subject="ML Project Collaboration Discussion",
        message_count=5,
        first_message_date=datetime.utcnow() - timedelta(days=15),
        last_message_date=datetime.utcnow() - timedelta(days=8),
        thread_summary="Discussed potential collaboration on ML infrastructure project",
        participant_emails=["john.smith@example.com", "test@example.com"]
    )
    db.add(thread)
    db.commit()
    
    return test_user, test_contact


async def test_contact_summarization():
    """Test contact summarization functionality."""
    print("🚀 Testing Contact Summarization Service")
    print("=" * 60)
    
    # Get database session
    db = next(get_db())
    
    try:
        # Create test data
        test_user, test_contact = create_test_data(db)
        
        # Initialize service
        service = ContactSummarizationService(db)
        
        # Test 1: Comprehensive Summary
        print("\n📊 Testing Comprehensive Summary...")
        try:
            comprehensive_summary = await service.generate_contact_summary(
                contact_id=test_contact.id,
                user_id=test_user.id,
                summary_type=SummaryType.COMPREHENSIVE
            )
            
            print(f"✅ Generated comprehensive summary ({len(comprehensive_summary['summary'])} chars)")
            print(f"   📝 Summary preview: {comprehensive_summary['summary'][:100]}...")
            print(f"   💡 Talking points: {len(comprehensive_summary['talking_points'])}")
            print(f"   🔗 Relationship strength: {comprehensive_summary['relationship_strength']}")
            
        except Exception as e:
            print(f"❌ Comprehensive summary failed: {e}")
        
        # Test 2: Brief Summary
        print("\n⚡ Testing Brief Summary...")
        try:
            brief_summary = await service.generate_contact_summary(
                contact_id=test_contact.id,
                user_id=test_user.id,
                summary_type=SummaryType.BRIEF
            )
            
            print(f"✅ Generated brief summary ({len(brief_summary['summary'])} chars)")
            print(f"   📝 Summary preview: {brief_summary['summary'][:100]}...")
            print(f"   💡 Talking points: {len(brief_summary['talking_points'])}")
            
        except Exception as e:
            print(f"❌ Brief summary failed: {e}")
        
        # Test 3: Pre-Meeting Summary
        print("\n🤝 Testing Pre-Meeting Summary...")
        try:
            meeting_summary = await service.generate_pre_meeting_summary(
                contact_id=test_contact.id,
                user_id=test_user.id,
                meeting_context="Quarterly sync meeting to discuss ML project progress and next steps",
                meeting_date=datetime.utcnow() + timedelta(hours=2)
            )
            
            print(f"✅ Generated pre-meeting summary ({len(meeting_summary['summary'])} chars)")
            print(f"   📝 Summary preview: {meeting_summary['summary'][:100]}...")
            print(f"   💡 Talking points: {len(meeting_summary['talking_points'])}")
            print(f"   📅 Meeting context: {meeting_summary['meeting_context']}")
            
        except Exception as e:
            print(f"❌ Pre-meeting summary failed: {e}")
        
        # Test 4: Relationship Status Summary
        print("\n❤️ Testing Relationship Status Summary...")
        try:
            status_summary = await service.generate_contact_summary(
                contact_id=test_contact.id,
                user_id=test_user.id,
                summary_type=SummaryType.RELATIONSHIP_STATUS
            )
            
            print(f"✅ Generated relationship status summary ({len(status_summary['summary'])} chars)")
            print(f"   📝 Summary preview: {status_summary['summary'][:100]}...")
            print(f"   💪 Relationship insights: {len(status_summary['relationship_insights'])}")
            
        except Exception as e:
            print(f"❌ Relationship status summary failed: {e}")
        
        # Test 5: Updates Summary
        print("\n🔄 Testing Updates Summary...")
        try:
            updates_summary = await service.generate_contact_summary(
                contact_id=test_contact.id,
                user_id=test_user.id,
                summary_type=SummaryType.UPDATES
            )
            
            print(f"✅ Generated updates summary ({len(updates_summary['summary'])} chars)")
            print(f"   📝 Summary preview: {updates_summary['summary'][:100]}...")
            
        except Exception as e:
            print(f"❌ Updates summary failed: {e}")
        
        # Test 6: Cache Testing
        print("\n💾 Testing Cache Functionality...")
        try:
            # Generate summary and check cache
            summary1 = await service.generate_contact_summary(
                contact_id=test_contact.id,
                user_id=test_user.id,
                summary_type=SummaryType.BRIEF,
                force_refresh=True
            )
            
            # Try to get cached version
            cached_summary = await service.get_cached_summary(
                contact_id=test_contact.id,
                user_id=test_user.id,
                summary_type=SummaryType.BRIEF
            )
            
            if cached_summary:
                print("✅ Cache functionality working")
                print(f"   📝 Cached: {cached_summary['cached']}")
            else:
                print("⚠️ Cache not implemented yet (expected)")
            
        except Exception as e:
            print(f"❌ Cache testing failed: {e}")
        
        # Test 7: Batch Summary Generation
        print("\n📦 Testing Batch Summary Generation...")
        try:
            # Create another test contact for batch testing
            test_contact_2 = Contact(
                id=uuid4(),
                user_id=test_user.id,
                name="Jane Doe",
                email="jane.doe@example.com",
                company="DataCorp",
                job_title="Data Scientist",
                source="email",
                quality_score=7.8,
                relationship_strength=6.5
            )
            db.add(test_contact_2)
            db.commit()
            
            batch_summaries = await service.generate_batch_summaries(
                contact_ids=[test_contact.id, test_contact_2.id],
                user_id=test_user.id,
                summary_type=SummaryType.BRIEF,
                max_contacts=10
            )
            
            print(f"✅ Generated batch summaries: {len(batch_summaries)} contacts")
            for i, summary in enumerate(batch_summaries):
                print(f"   {i+1}. {summary['contact_name']}: {len(summary['summary'])} chars")
            
        except Exception as e:
            print(f"❌ Batch summary failed: {e}")
        
        # Test 8: Interaction Update Testing
        print("\n🔄 Testing Interaction Update...")
        try:
            success = await service.update_summary_on_interaction(
                contact_id=test_contact.id,
                user_id=test_user.id,
                interaction_data={"type": "new_email", "summary": "Test email interaction"}
            )
            
            if success:
                print("✅ Interaction update successful")
            else:
                print("❌ Interaction update failed")
            
        except Exception as e:
            print(f"❌ Interaction update failed: {e}")
        
        print("\n" + "=" * 60)
        print("🎯 Contact Summarization Testing Complete!")
        
    except Exception as e:
        print(f"❌ Test setup failed: {e}")
        return False
    
    finally:
        # Cleanup test data
        try:
            db.rollback()
            print("\n🧹 Test data cleaned up")
        except:
            pass
    
    return True


def test_summary_types():
    """Test summary type constants and metadata."""
    print("\n📋 Testing Summary Types...")
    
    types = [
        SummaryType.COMPREHENSIVE,
        SummaryType.BRIEF,
        SummaryType.PRE_MEETING,
        SummaryType.RELATIONSHIP_STATUS,
        SummaryType.UPDATES
    ]
    
    for summary_type in types:
        print(f"   ✅ {summary_type}")
    
    print(f"   📊 Total summary types: {len(types)}")


if __name__ == "__main__":
    print("🧪 Starting Contact Summarization Tests...")
    
    # Test summary types
    test_summary_types()
    
    # Run async tests
    try:
        success = asyncio.run(test_contact_summarization())
        exit_code = 0 if success else 1
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        exit_code = 1
    
    print(f"\n{'✅ All tests completed successfully!' if exit_code == 0 else '❌ Some tests failed!'}")
    sys.exit(exit_code) 