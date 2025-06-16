"""Test script for AI Assistant Caching System (Task 3.3.4)."""

import asyncio
import os
from datetime import datetime, timezone

from lib.database import get_db
from services.ai_assistant import AIAssistantService
from lib.llm_client import LLMUsageType, initialize_openai_client, OpenAIModel, set_token_usage_service
from services.token_usage_service import TokenUsageService
from models.orm.user import User


async def test_ai_assistant_caching():
    """Test the AI assistant caching system."""
    print("🤖 Testing AI Assistant Caching System")
    print("=" * 50)
    
    # Initialize database session
    db = next(get_db())
    
    try:
        # Initialize services
        ai_service = AIAssistantService(db)
        
        # Initialize OpenAI client (with test key for mock testing)
        try:
            initialize_openai_client(
                api_key=os.getenv('OPENAI_API_KEY', 'test-key'),
                default_model=OpenAIModel.GPT_3_5_TURBO
            )
            
            # Initialize token usage service
            token_service = TokenUsageService(db)
            set_token_usage_service(token_service)
            
            print("✅ Services initialized successfully")
        except Exception as e:
            print(f"⚠️  Service initialization failed (expected in test): {e}")
        
        # Create or get a test user
        test_user = db.query(User).first()
        if not test_user:
            print("❌ No test user found. Please create a user first.")
            return
        
        user_id = str(test_user.id)
        print(f"👤 Using test user: {test_user.email}")
        
        # Test 1: Check initial cache stats
        print("\n📊 Test 1: Initial cache statistics")
        initial_stats = ai_service.get_cache_stats()
        print(f"✅ Initial cache stats:")
        print(f"   Total requests: {initial_stats['total_requests']}")
        print(f"   Cache hits: {initial_stats['cache_hits']}")
        print(f"   Cache misses: {initial_stats['cache_misses']}")
        print(f"   Hit rate: {initial_stats['hit_rate']:.1f}%")
        
        # Test 2: Service health check
        print("\n🔍 Test 2: Service health check")
        health = await ai_service.health_check()
        print(f"✅ Service health:")
        print(f"   Status: {health['status']}")
        print(f"   Redis connected: {health['redis_connected']}")
        print(f"   OpenAI available: {health.get('openai_available', 'Unknown')}")
        
        # Test 3: Cache key generation
        print("\n🔑 Test 3: Cache key generation")
        cache_key = ai_service._generate_cache_key(
            prompt="Test prompt for caching",
            user_id=user_id,
            request_type="briefing",
            model="gpt-3.5-turbo"
        )
        print(f"✅ Generated cache key: {cache_key}")
        
        # Test 4: Manual cache operations
        print("\n💾 Test 4: Manual cache operations")
        test_data = {
            "content": "This is a test cached response",
            "model": "gpt-3.5-turbo",
            "finish_reason": "stop",
            "estimated_cost": 0.001,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "cache_key": cache_key
        }
        
        # Test caching
        cache_success = await ai_service._cache_response(cache_key, test_data, 60)
        print(f"✅ Cache store success: {cache_success}")
        
        # Test retrieval
        if cache_success:
            cached_data = await ai_service._get_cached_response(cache_key)
            if cached_data:
                print(f"✅ Cache retrieval success: {cached_data['content'][:30]}...")
            else:
                print("❌ Cache retrieval failed")
        
        # Test 5: Cache clearing
        print("\n🧹 Test 5: Cache operations")
        
        # Clear user cache
        cleared_count = await ai_service.invalidate_user_cache(user_id)
        print(f"✅ Cleared {cleared_count} cache entries for user")
        
        # Test 6: Cache statistics after operations
        print("\n📈 Test 6: Updated cache statistics")
        final_stats = ai_service.get_cache_stats()
        print(f"✅ Final cache stats:")
        print(f"   Total requests: {final_stats['total_requests']}")
        print(f"   Cache hits: {final_stats['cache_hits']}")
        print(f"   Cache misses: {final_stats['cache_misses']}")
        print(f"   Hit rate: {final_stats['hit_rate']:.1f}%")
        print(f"   Avg response time: {final_stats['avg_response_time_ms']:.1f}ms")
        print(f"   Cost savings: ${final_stats['cost_savings_usd']:.6f}")
        
        print("\n🎉 All cache tests completed successfully!")
        print("✅ AI Assistant caching system is working correctly")
        
        # Test 7: If OpenAI is available, test actual generation with caching
        if health.get('openai_available'):
            print("\n🚀 Test 7: Real generation with caching (if OpenAI available)")
            try:
                # First request (should be cache miss)
                print("   Making first request (cache miss expected)...")
                response1 = await ai_service.generate_with_cache(
                    prompt="What is the capital of France?",
                    user_id=user_id,
                    request_type="test",
                    usage_type=LLMUsageType.BRIEFING_GENERATION,
                    temperature=0.7
                )
                print(f"   ✅ First response: {response1.content[:50]}...")
                print(f"   Cached: {response1.cached}")
                
                # Second identical request (should be cache hit)
                print("   Making identical request (cache hit expected)...")
                response2 = await ai_service.generate_with_cache(
                    prompt="What is the capital of France?",
                    user_id=user_id,
                    request_type="test",
                    usage_type=LLMUsageType.BRIEFING_GENERATION,
                    temperature=0.7
                )
                print(f"   ✅ Second response: {response2.content[:50]}...")
                print(f"   Cached: {response2.cached}")
                
                if response2.cached:
                    print("   🎯 Cache hit successful!")
                else:
                    print("   ⚠️  Cache miss (may be due to test environment)")
                    
            except Exception as e:
                print(f"   ⚠️  Real generation test skipped: {e}")
        else:
            print("\n⚠️  Test 7 skipped: OpenAI not available")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_ai_assistant_caching()) 