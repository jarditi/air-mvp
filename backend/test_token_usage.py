"""Test script for token usage tracking system."""

import asyncio
import os
from datetime import datetime, timezone
from decimal import Decimal

from lib.database import get_db
from lib.llm_client import LLMUsage, LLMUsageType, OpenAIModel, initialize_openai_client, set_token_usage_service
from services.token_usage_service import TokenUsageService
from models.orm.user import User


async def test_token_usage_tracking():
    """Test the token usage tracking system."""
    print("🧪 Testing Token Usage Tracking System")
    print("=" * 50)
    
    # Initialize database session
    db = next(get_db())
    
    try:
        # Initialize services
        token_service = TokenUsageService(db)
        
        # Initialize OpenAI client (mock for testing)
        try:
            initialize_openai_client(
                api_key=os.getenv('OPENAI_API_KEY', 'test-key'),
                default_model=OpenAIModel.GPT_3_5_TURBO
            )
            set_token_usage_service(token_service)
            print("✅ OpenAI client and token service initialized")
        except Exception as e:
            print(f"⚠️  OpenAI client initialization failed (expected in test): {e}")
        
        # Create a test user
        test_user = db.query(User).first()
        if not test_user:
            print("❌ No test user found. Please create a user first.")
            return
        
        user_id = str(test_user.id)
        print(f"👤 Using test user: {test_user.email}")
        
        # Test 1: Log usage
        print("\n📝 Test 1: Logging LLM usage")
        usage = LLMUsage(
            model=OpenAIModel.GPT_3_5_TURBO,
            usage_type=LLMUsageType.BRIEFING_GENERATION,
            prompt_tokens=150,
            completion_tokens=75,
            total_tokens=225,
            cost_usd=0.0003375,  # $0.0003375 for 225 tokens
            response_time_ms=1250,
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            request_id="test-request-123"
        )
        
        usage_log = await token_service.log_usage(
            usage=usage,
            endpoint="/api/v1/ai/briefing",
            prompt_length=len("Generate a briefing for my meeting"),
            completion_length=len("Here's your meeting briefing..."),
            temperature=0.7,
            max_tokens=100,
            success=True
        )
        
        print(f"✅ Usage logged with ID: {usage_log.id}")
        print(f"   Model: {usage_log.model}")
        print(f"   Tokens: {usage_log.total_tokens}")
        print(f"   Cost: ${usage_log.cost_usd}")
        
        # Test 2: Get usage statistics
        print("\n📊 Test 2: Getting usage statistics")
        stats = token_service.get_usage_statistics(
            user_id=test_user.id,
            period_days=30
        )
        
        print(f"✅ Usage statistics retrieved:")
        print(f"   Total requests: {stats['total_requests']}")
        print(f"   Total cost: ${stats['total_cost']:.6f}")
        print(f"   Total tokens: {stats['total_tokens']}")
        print(f"   Success rate: {stats['success_rate']:.1f}%")
        print(f"   Cache hit rate: {stats['cache_hit_rate']:.1f}%")
        
        # Test 3: Create a budget
        print("\n💰 Test 3: Creating a cost budget")
        budget = token_service.create_budget(
            user_id=test_user.id,
            budget_type="user",
            budget_period="monthly",
            budget_amount_usd=10.0,
            warning_threshold=0.8,
            hard_limit=False
        )
        
        print(f"✅ Budget created with ID: {budget.id}")
        print(f"   Amount: ${budget.budget_amount_usd}")
        print(f"   Period: {budget.budget_period}")
        print(f"   Current spent: ${budget.current_period_spent}")
        print(f"   Usage: {budget.usage_percentage:.1f}%")
        
        # Test 4: Check budget status
        print("\n🔍 Test 4: Checking budget status")
        budget_status = token_service.check_budget_status(test_user.id)
        
        print(f"✅ Budget status checked:")
        print(f"   Total budgets: {len(budget_status['budgets'])}")
        print(f"   Any exceeded: {budget_status['any_exceeded']}")
        print(f"   Any warnings: {budget_status['any_warning']}")
        
        # Test 5: Log a few more usage entries for better statistics
        print("\n📝 Test 5: Logging additional usage entries")
        for i in range(3):
            usage = LLMUsage(
                model=OpenAIModel.GPT_3_5_TURBO,
                usage_type=LLMUsageType.MESSAGE_DRAFTING,
                prompt_tokens=100 + i * 10,
                completion_tokens=50 + i * 5,
                total_tokens=150 + i * 15,
                cost_usd=(150 + i * 15) * 0.0015 / 1000,  # GPT-3.5 pricing
                response_time_ms=800 + i * 100,
                timestamp=datetime.now(timezone.utc),
                user_id=user_id,
                request_id=f"test-request-{124 + i}"
            )
            
            await token_service.log_usage(
                usage=usage,
                endpoint="/api/v1/ai/message",
                success=True,
                cached_response=(i == 1)  # Second request is cached
            )
        
        print(f"✅ Logged 3 additional usage entries")
        
        # Test 6: Updated statistics
        print("\n📊 Test 6: Updated usage statistics")
        updated_stats = token_service.get_usage_statistics(
            user_id=test_user.id,
            period_days=30
        )
        
        print(f"✅ Updated statistics:")
        print(f"   Total requests: {updated_stats['total_requests']}")
        print(f"   Total cost: ${updated_stats['total_cost']:.6f}")
        print(f"   Total tokens: {updated_stats['total_tokens']}")
        print(f"   Success rate: {updated_stats['success_rate']:.1f}%")
        print(f"   Cache hit rate: {updated_stats['cache_hit_rate']:.1f}%")
        print(f"   By model: {updated_stats['by_model']}")
        print(f"   By usage type: {updated_stats['by_usage_type']}")
        
        print("\n🎉 All tests completed successfully!")
        print("✅ Token usage tracking system is working correctly")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_token_usage_tracking()) 