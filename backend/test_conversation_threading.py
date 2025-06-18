"""
Test script for Cross-Platform Conversation Threading Service

This script tests Task 3.6.1: Cross-Platform Conversation Threading functionality
including unified conversation assembly, smart thread merging, and context linking.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = "postgresql://postgres:password@db:5432/airmvp"

def create_test_data(engine):
    """Create test data for conversation threading"""
    
    print("🔧 Creating test data for conversation threading...")
    
    with engine.begin() as conn:
        # Create test user with unique email
        user_id = str(uuid4())
        test_email = f"testuser_{int(time.time())}@example.com"
        conn.execute(text("""
            INSERT INTO users (id, email, full_name, auth_provider, auth_provider_id, created_at, updated_at)
            VALUES (:user_id, :email, 'Test User', 'test', 'test_123', NOW(), NOW())
        """), {"user_id": user_id, "email": test_email})
        
        # Create test contacts
        contact1_id = str(uuid4())
        contact2_id = str(uuid4())
        
        conn.execute(text("""
            INSERT INTO contacts (id, user_id, email, full_name, first_name, last_name, contact_source, created_at, updated_at)
            VALUES 
                (:contact1_id, :user_id, 'alice@example.com', 'Alice Smith', 'Alice', 'Smith', 'email', NOW(), NOW()),
                (:contact2_id, :user_id, 'bob@company.com', 'Bob Johnson', 'Bob', 'Johnson', 'calendar', NOW(), NOW())
            ON CONFLICT (id) DO NOTHING
        """), {
            "contact1_id": contact1_id,
            "contact2_id": contact2_id,
            "user_id": user_id
        })
        
        # Create test interactions that should form conversation threads
        now = datetime.now(timezone.utc)
        
        # Thread 1: Alice - Email conversation followed by meeting
        interactions = [
            # Email thread
            {
                "id": str(uuid4()),
                "user_id": user_id,
                "contact_id": contact1_id,
                "interaction_type": "email",
                "direction": "outbound",
                "subject": "Project Discussion",
                "content": "Hi Alice, let's discuss the new project timeline.",
                "sentiment_score": 0.6,
                "interaction_date": now - timedelta(days=5),
                "source_platform": "gmail",
                "platform_metadata": json.dumps({"thread_id": "thread_alice_1"})
            },
            {
                "id": str(uuid4()),
                "user_id": user_id,
                "contact_id": contact1_id,
                "interaction_type": "email",
                "direction": "inbound",
                "subject": "Re: Project Discussion",
                "content": "Sounds great! I'm available next week.",
                "sentiment_score": 0.8,
                "interaction_date": now - timedelta(days=4, hours=2),
                "source_platform": "gmail",
                "platform_metadata": json.dumps({"thread_id": "thread_alice_1"})
            },
            {
                "id": str(uuid4()),
                "user_id": user_id,
                "contact_id": contact1_id,
                "interaction_type": "email",
                "direction": "outbound",
                "subject": "Re: Project Discussion",
                "content": "Perfect! Let's schedule a meeting for Tuesday.",
                "sentiment_score": 0.7,
                "interaction_date": now - timedelta(days=4),
                "source_platform": "gmail",
                "platform_metadata": json.dumps({"thread_id": "thread_alice_1"})
            },
            # Meeting that should be linked to email thread
            {
                "id": str(uuid4()),
                "user_id": user_id,
                "contact_id": contact1_id,
                "interaction_type": "meeting",
                "direction": "mutual",
                "subject": "Project Kickoff",
                "sentiment_score": 0.7,
                "interaction_date": now - timedelta(days=3),
                "source_platform": "calendar",
                "meeting_attendees": [test_email, "alice@example.com"],
                "platform_metadata": json.dumps({"meeting_id": "meet_alice_1"})
            },
            # Follow-up email after meeting
            {
                "id": str(uuid4()),
                "user_id": user_id,
                "contact_id": contact1_id,
                "interaction_type": "email",
                "direction": "outbound",
                "subject": "Follow up on our meeting",
                "content": "Thanks for the productive meeting! Here are the action items...",
                "sentiment_score": 0.8,
                "interaction_date": now - timedelta(days=2),
                "source_platform": "gmail",
                "platform_metadata": json.dumps({"thread_id": "thread_alice_2"})
            },
        ]
        
        # Thread 2: Bob - Separate conversation thread
        bob_interactions = [
            {
                "id": str(uuid4()),
                "user_id": user_id,
                "contact_id": contact2_id,
                "interaction_type": "meeting",
                "direction": "mutual",
                "subject": "Quarterly Review",
                "sentiment_score": 0.6,
                "interaction_date": now - timedelta(days=10),
                "source_platform": "calendar",
                "meeting_attendees": [test_email, "bob@company.com"],
                "platform_metadata": json.dumps({"meeting_id": "meet_bob_1"})
            },
            {
                "id": str(uuid4()),
                "user_id": user_id,
                "contact_id": contact2_id,
                "interaction_type": "email",
                "direction": "inbound",
                "subject": "Budget Planning",
                "content": "Let's discuss the budget for next quarter.",
                "sentiment_score": 0.5,
                "interaction_date": now - timedelta(days=1),
                "source_platform": "gmail",
                "platform_metadata": json.dumps({"thread_id": "thread_bob_1"})
            }
        ]
        
        interactions.extend(bob_interactions)
        
        # Insert interactions
        for interaction in interactions:
            # Ensure all required fields are present
            if 'meeting_attendees' not in interaction:
                interaction['meeting_attendees'] = None
            if 'content' not in interaction:
                interaction['content'] = None
                
            conn.execute(text("""
                INSERT INTO interactions (
                    id, user_id, contact_id, interaction_type, direction, subject, content,
                    sentiment_score, interaction_date, source_platform,
                    meeting_attendees, platform_metadata, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :contact_id, :interaction_type, :direction, :subject, :content,
                    :sentiment_score, :interaction_date, :source_platform,
                    :meeting_attendees, :platform_metadata, NOW(), NOW()
                )
            """), interaction)
        
        print(f"✅ Created test user: {user_id}")
        print(f"✅ Created test contacts: {contact1_id}, {contact2_id}")
        print(f"✅ Created {len(interactions)} test interactions")
        
        return user_id, contact1_id, contact2_id


async def test_conversation_threading():
    """Test conversation threading functionality"""
    
    print("\n🧵 Testing Conversation Threading Service")
    print("=" * 50)
    
    # Set up database
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create test data
    user_id, contact1_id, contact2_id = create_test_data(engine)
    
    # Import service
    from services.conversation_threading_service import ConversationThreadingService
    
    # Test 1: Build conversation threads for user
    print("\n1. Testing thread building for user...")
    try:
        db = SessionLocal()
        service = ConversationThreadingService(db)
        
        threads = await service.build_conversation_threads(
            user_id=user_id,
            days_back=30
        )
        
        print(f"✅ Built {len(threads)} conversation threads")
        
        for i, thread in enumerate(threads):
            print(f"\n   Thread {i+1}: {thread.thread_id}")
            print(f"   - Contact: {thread.contact_id}")
            print(f"   - Platforms: {thread.platforms}")
            print(f"   - Interactions: {thread.total_interactions}")
            print(f"   - Thread depth: {thread.thread_depth}")
            print(f"   - Thread type: {thread.thread_type}")
            print(f"   - Context score: {thread.context_score:.3f}")
            print(f"   - Subject themes: {thread.subject_themes}")
            print(f"   - Duration: {thread.start_date.date()} to {thread.end_date.date()}")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Thread building failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 2: Build threads for specific contact
    print("\n2. Testing thread building for specific contact...")
    try:
        db = SessionLocal()
        service = ConversationThreadingService(db)
        
        alice_threads = await service.build_conversation_threads(
            user_id=user_id,
            contact_id=contact1_id,
            days_back=30
        )
        
        print(f"✅ Built {len(alice_threads)} threads for Alice")
        
        if alice_threads:
            thread = alice_threads[0]
            print(f"   - Cross-platform thread: {len(thread.platforms) > 1}")
            print(f"   - Platforms involved: {thread.platforms}")
            print(f"   - Dominant platform: {thread.dominant_platform}")
            
            # Check for email-to-meeting transitions
            email_interactions = [i for i in thread.interactions if i['interaction_type'] == 'email']
            meeting_interactions = [i for i in thread.interactions if i['interaction_type'] == 'meeting']
            
            print(f"   - Email interactions: {len(email_interactions)}")
            print(f"   - Meeting interactions: {len(meeting_interactions)}")
            
            if email_interactions and meeting_interactions:
                print("   ✅ Successfully linked email and meeting interactions")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Contact-specific threading failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 3: Thread summary generation
    print("\n3. Testing thread summary generation...")
    try:
        db = SessionLocal()
        service = ConversationThreadingService(db)
        
        if alice_threads:
            summary = await service.generate_thread_summary(alice_threads[0])
            print(f"✅ Generated thread summary:")
            print(f"   \"{summary}\"")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Thread summary generation failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 4: Thread merging logic
    print("\n4. Testing thread merging logic...")
    try:
        db = SessionLocal()
        service = ConversationThreadingService(db)
        
        # Get all threads
        all_threads = await service.build_conversation_threads(
            user_id=user_id,
            days_back=30
        )
        
        # Find merge candidates
        merge_candidates = await service._find_thread_merge_candidates(all_threads)
        
        print(f"✅ Found {len(merge_candidates)} merge candidates")
        
        for candidate in merge_candidates:
            print(f"   - Merge confidence: {candidate.merge_confidence:.3f}")
            print(f"   - Strategy: {candidate.merge_strategy}")
            print(f"   - Action: {candidate.recommended_action}")
            print(f"   - Evidence: {candidate.evidence}")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Thread merging test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n🎉 Conversation Threading Tests Complete!")


async def test_api_endpoints():
    """Test conversation threading API endpoints"""
    
    print("\n🌐 Testing Conversation Threading API Endpoints")
    print("=" * 50)
    
    import requests
    
    # Base URL for API
    BASE_URL = "http://localhost:8000/api/v1/conversation-threads"
    
    # Test headers (you'll need to add proper auth)
    headers = {
        "Content-Type": "application/json",
        # "Authorization": "Bearer YOUR_JWT_TOKEN"  # Add when auth is set up
    }
    
    # Test 1: Build threads endpoint
    print("\n1. Testing POST /conversation-threads/build...")
    try:
        payload = {
            "days_back": 30,
            "include_platforms": ["gmail", "calendar"],
            "force_rebuild": False
        }
        
        response = requests.post(f"{BASE_URL}/build", json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API responded successfully")
            print(f"   - Total threads: {data.get('total_threads', 0)}")
            print(f"   - Processing time: {data.get('processing_time_seconds', 0):.2f}s")
            print(f"   - Statistics: {data.get('statistics', {})}")
        else:
            print(f"❌ API error: {response.status_code} - {response.text}")
    
    except requests.exceptions.ConnectionError:
        print("❌ API server not running or not accessible")
        print("   Start the server with: docker-compose up backend")
    except Exception as e:
        print(f"❌ API test failed: {e}")
    
    # Test 2: Statistics endpoint
    print("\n2. Testing GET /conversation-threads/statistics...")
    try:
        response = requests.get(f"{BASE_URL}/statistics?days_back=30", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Statistics endpoint responded successfully")
            print(f"   - Overview: {data.get('overview', {})}")
            print(f"   - Platform distribution: {data.get('platform_distribution', {})}")
            print(f"   - Thread types: {data.get('thread_type_distribution', {})}")
        else:
            print(f"❌ Statistics API error: {response.status_code} - {response.text}")
    
    except requests.exceptions.ConnectionError:
        print("❌ API server not running or not accessible")
    except Exception as e:
        print(f"❌ Statistics test failed: {e}")


def test_thread_merging_strategies():
    """Test different thread merging strategies"""
    
    print("\n🔀 Testing Thread Merging Strategies")
    print("=" * 40)
    
    from services.conversation_threading_service import ConversationThreadingService
    from datetime import datetime, timezone, timedelta
    
    # Create service instance
    service = ConversationThreadingService(None)  # No DB needed for this test
    
    # Test 1: Subject similarity calculation
    print("\n1. Testing subject similarity...")
    
    test_cases = [
        ("Project Discussion", "Re: Project Discussion", 0.8),
        ("Meeting Follow-up", "Follow up on our meeting", 0.5),
        ("Budget Planning", "Quarterly Review", 0.1),
        ("Team Sync", "Re: Team Sync - Action Items", 0.7)
    ]
    
    for subject1, subject2, expected_min in test_cases:
        similarity = service._calculate_subject_similarity(subject1, subject2)
        result = "✅" if similarity >= expected_min else "❌"
        print(f"   {result} '{subject1}' vs '{subject2}': {similarity:.3f}")
    
    # Test 2: Platform transition logic
    print("\n2. Testing platform transitions...")
    
    from services.conversation_threading_service import ConversationThread
    
    # Mock thread objects
    email_thread = ConversationThread(
        thread_id="email_1", contact_id="contact_1", user_id="user_1",
        platforms={"gmail"}, interactions=[], start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc), total_interactions=1, thread_depth=1,
        subject_themes=[], dominant_platform="gmail", participant_count=1,
        thread_type="completed", context_score=0.5
    )
    
    meeting_thread = ConversationThread(
        thread_id="meeting_1", contact_id="contact_1", user_id="user_1",
        platforms={"calendar"}, interactions=[], start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc), total_interactions=1, thread_depth=1,
        subject_themes=[], dominant_platform="calendar", participant_count=1,
        thread_type="completed", context_score=0.5
    )
    
    is_natural = service._is_natural_platform_transition(email_thread, meeting_thread)
    print(f"   ✅ Email -> Meeting transition: {is_natural}")
    
    is_natural_reverse = service._is_natural_platform_transition(meeting_thread, email_thread)
    print(f"   ✅ Meeting -> Email transition: {is_natural_reverse}")
    
    print("\n🎉 Thread Merging Strategy Tests Complete!")


if __name__ == "__main__":
    print("🚀 Starting Conversation Threading Service Tests")
    print("=" * 60)
    
    # Run async tests
    asyncio.run(test_conversation_threading())
    
    # Run API tests
    asyncio.run(test_api_endpoints())
    
    # Run strategy tests
    test_thread_merging_strategies()
    
    print("\n✨ All tests completed!")
    print("\nNext steps:")
    print("1. Review thread building results")
    print("2. Test with real email/calendar data")
    print("3. Fine-tune merging algorithms")
    print("4. Add LinkedIn integration when available") 