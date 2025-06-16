#!/usr/bin/env python3
"""
AI Assistant API Demo with Clerk Authentication

This script demonstrates how to use the AI assistant API endpoints with proper
Clerk authentication tokens.

Prerequisites:
1. Have a Clerk account and app set up
2. Have a valid Clerk JWT token from a frontend session
3. Backend running with proper Clerk configuration

For testing purposes, this script will show:
- How to structure API calls with Clerk tokens
- Example requests for all AI assistant endpoints
- Caching behavior demonstration
"""

import requests
import json
import time
from datetime import datetime
import sys

# API Configuration
BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api/v1"

class ClerkAIDemo:
    """Demo class for AI Assistant API with Clerk authentication."""
    
    def __init__(self, clerk_token: str = None):
        """
        Initialize with Clerk JWT token.
        
        Args:
            clerk_token: Valid Clerk JWT token from authenticated session
        """
        self.session = requests.Session()
        self.clerk_token = clerk_token
        
        if clerk_token:
            self.session.headers.update({
                "Authorization": f"Bearer {clerk_token}",
                "Content-Type": "application/json"
            })
    
    def test_auth(self):
        """Test authentication with current token."""
        print("🔐 Testing Clerk Authentication...")
        
        if not self.clerk_token:
            print("❌ No Clerk token provided")
            print("💡 To get a Clerk token:")
            print("   1. Log into your frontend application")
            print("   2. Open browser dev tools")
            print("   3. Run: await window.clerk.session.getToken()")
            print("   4. Copy the returned JWT token")
            return False
        
        try:
            response = self.session.get(f"{API_URL}/auth/test-auth")
            if response.status_code == 200:
                auth_data = response.json()
                if auth_data.get("success"):
                    print("✅ Authentication successful!")
                    print(f"   User ID: {auth_data.get('user_id')}")
                    print(f"   Email: {auth_data.get('email')}")
                    print(f"   Auth Provider: {auth_data.get('auth_provider')}")
                    return True
                else:
                    print(f"❌ Authentication failed: {auth_data.get('error')}")
                    return False
            else:
                print(f"❌ Auth test failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Auth test error: {e}")
            return False
    
    def check_ai_health(self):
        """Check AI assistant service health."""
        print("\n🔍 Checking AI Assistant Health...")
        
        try:
            response = self.session.get(f"{API_URL}/ai/health")
            if response.status_code == 200:
                health_data = response.json()
                print("✅ AI Assistant Health Check:")
                print(f"   Status: {health_data.get('status')}")
                print(f"   Redis Connected: {health_data.get('redis_connected')}")
                print(f"   OpenAI Available: {health_data.get('openai_available')}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False
    
    def get_cache_stats(self):
        """Get current cache statistics."""
        print("\n📊 Getting Cache Statistics...")
        
        try:
            response = self.session.get(f"{API_URL}/ai/cache/stats")
            if response.status_code == 200:
                stats = response.json()
                print("✅ Cache Statistics:")
                print(f"   Total Requests: {stats.get('total_requests', 0)}")
                print(f"   Cache Hits: {stats.get('cache_hits', 0)}")
                print(f"   Cache Misses: {stats.get('cache_misses', 0)}")
                print(f"   Hit Rate: {stats.get('hit_rate', 0):.1f}%")
                print(f"   Avg Response Time: {stats.get('avg_response_time_ms', 0):.1f}ms")
                print(f"   Cost Savings: ${stats.get('cost_savings_usd', 0):.6f}")
                return stats
            else:
                print(f"❌ Failed to get cache stats: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Cache stats error: {e}")
            return None
    
    def demo_briefing_generation(self):
        """Demonstrate briefing generation with caching."""
        print("\n💼 Demonstrating Briefing Generation...")
        
        briefing_request = {
            "contact_name": "Dr. Emily Rodriguez",
            "contact_context": "Chief AI Officer at InnovateTech, PhD in Machine Learning from MIT, 12+ years in AI research, published 40+ papers on deep learning and computer vision",
            "meeting_context": "Strategic discussion about AI consulting partnership and potential joint research opportunities in autonomous systems",
            "force_refresh": False
        }
        
        print("📝 Generating briefing (first request)...")
        print(f"   Contact: {briefing_request['contact_name']}")
        print(f"   Meeting: {briefing_request['meeting_context'][:60]}...")
        
        start_time = time.time()
        
        try:
            response = self.session.post(
                f"{API_URL}/ai/briefing",
                json=briefing_request
            )
            
            response_time = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                briefing_data = response.json()
                print("✅ Briefing Generated Successfully!")
                print(f"   Model: {briefing_data['model']}")
                print(f"   Cached: {briefing_data['cached']}")
                print(f"   Response Time: {response_time}ms")
                
                if briefing_data['usage']:
                    usage = briefing_data['usage']
                    print(f"   Tokens: {usage.get('total_tokens', 0)}")
                    print(f"   Cost: ${usage.get('cost_usd', 0):.6f}")
                
                # Show first part of content
                content = briefing_data['content']
                print(f"\n📋 Briefing Content Preview:")
                print("   " + "="*60)
                print("   " + content[:400] + "...")
                print("   " + "="*60)
                
                # Test caching with identical request
                print("\n🔄 Testing cache with identical request...")
                start_time2 = time.time()
                
                response2 = self.session.post(
                    f"{API_URL}/ai/briefing",
                    json=briefing_request
                )
                
                response_time2 = int((time.time() - start_time2) * 1000)
                
                if response2.status_code == 200:
                    briefing_data2 = response2.json()
                    print(f"✅ Second Request - Cached: {briefing_data2['cached']}")
                    print(f"   Response Time: {response_time2}ms")
                    
                    if briefing_data2['cached']:
                        speed_improvement = ((response_time - response_time2) / response_time * 100)
                        print(f"   🚀 Speed Improvement: {speed_improvement:.1f}%")
                        print("   🎯 Cache working perfectly!")
                
                return True
            else:
                print(f"❌ Briefing generation failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Briefing generation error: {e}")
            return False
    
    def demo_message_generation(self):
        """Demonstrate message generation with different parameters."""
        print("\n✉️ Demonstrating Message Generation...")
        
        # Professional follow-up message
        message_request1 = {
            "message_type": "follow_up",
            "recipient_context": "Michael Thompson, VP of Product at CloudScale Solutions, former colleague from DataTech Inc",
            "message_context": "Following up on our discussion about integrating AI capabilities into their cloud platform",
            "tone": "professional",
            "force_refresh": False
        }
        
        print("📧 Generating professional follow-up message...")
        
        try:
            response = self.session.post(
                f"{API_URL}/ai/message",
                json=message_request1
            )
            
            if response.status_code == 200:
                message_data = response.json()
                print("✅ Message Generated:")
                print(f"   Type: {message_request1['message_type']}")
                print(f"   Tone: {message_request1['tone']}")
                print(f"   Cached: {message_data['cached']}")
                
                content = message_data['content']
                print(f"\n📬 Message Content:")
                print("   " + "="*60)
                print("   " + content[:300] + "...")
                print("   " + "="*60)
                
                # Test with different tone
                print("\n🎨 Generating same message with friendly tone...")
                message_request2 = message_request1.copy()
                message_request2["tone"] = "friendly"
                
                response2 = self.session.post(
                    f"{API_URL}/ai/message",
                    json=message_request2
                )
                
                if response2.status_code == 200:
                    message_data2 = response2.json()
                    print(f"✅ Friendly Version - Cached: {message_data2['cached']}")
                    print("   ✨ Different parameters = Different cache key (as expected)")
                
                return True
            else:
                print(f"❌ Message generation failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Message generation error: {e}")
            return False
    
    def demo_cache_management(self):
        """Demonstrate cache management operations."""
        print("\n🧹 Demonstrating Cache Management...")
        
        try:
            response = self.session.delete(f"{API_URL}/ai/cache")
            if response.status_code == 200:
                clear_data = response.json()
                print("✅ Cache Management:")
                print(f"   {clear_data.get('message', 'Cache operation completed')}")
                print(f"   Entries Deleted: {clear_data.get('deleted', 0)}")
                return True
            else:
                print(f"❌ Cache management failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Cache management error: {e}")
            return False
    
    def run_full_demo(self):
        """Run the complete demonstration."""
        print("🤖 AI Assistant API Demo with Clerk Authentication")
        print("=" * 60)
        print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌐 API URL: {API_URL}")
        
        if not self.clerk_token:
            print("\n❌ No Clerk token provided!")
            print("\n📝 To get a Clerk token for testing:")
            print("1. Open your frontend application in a browser")
            print("2. Log in with your account")
            print("3. Open browser developer tools (F12)")
            print("4. Go to Console tab")
            print("5. Run: await window.clerk.session.getToken()")
            print("6. Copy the returned JWT token")
            print("7. Run this script with: python3 clerk_ai_demo.py YOUR_TOKEN_HERE")
            return
        
        # Run all tests
        success_count = 0
        total_tests = 6
        
        if self.test_auth():
            success_count += 1
        
        if self.check_ai_health():
            success_count += 1
        
        if self.get_cache_stats():
            success_count += 1
        
        if self.demo_briefing_generation():
            success_count += 1
        
        if self.demo_message_generation():
            success_count += 1
        
        if self.demo_cache_management():
            success_count += 1
        
        # Summary
        print("\n🎉 Demo Summary")
        print("=" * 30)
        print(f"✅ Successful operations: {success_count}/{total_tests}")
        print(f"📊 Success rate: {(success_count/total_tests)*100:.1f}%")
        
        if success_count == total_tests:
            print("🚀 All AI Assistant features working perfectly with Clerk auth!")
        elif success_count > 0:
            print("⚠️  Some features working, check configuration for failed tests")
        else:
            print("❌ All tests failed, check authentication and service configuration")
        
        print(f"🕐 Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    def show_example_curl_commands(self):
        """Show example curl commands for API testing."""
        print("\n📚 Example Curl Commands")
        print("=" * 40)
        
        if self.clerk_token:
            token_preview = self.clerk_token[:20] + "..."
        else:
            token_preview = "YOUR_CLERK_JWT_TOKEN"
        
        print(f"""
# Health Check
curl -H "Authorization: Bearer {token_preview}" \\
     http://localhost:8000/api/v1/ai/health

# Cache Stats
curl -H "Authorization: Bearer {token_preview}" \\
     http://localhost:8000/api/v1/ai/cache/stats

# Generate Briefing
curl -X POST \\
     -H "Authorization: Bearer {token_preview}" \\
     -H "Content-Type: application/json" \\
     -d '{{"contact_name": "John Doe", "contact_context": "CEO at TechCorp", "meeting_context": "Partnership discussion"}}' \\
     http://localhost:8000/api/v1/ai/briefing

# Generate Message
curl -X POST \\
     -H "Authorization: Bearer {token_preview}" \\
     -H "Content-Type: application/json" \\
     -d '{{"message_type": "follow_up", "recipient_context": "Jane Smith", "message_context": "Project update", "tone": "professional"}}' \\
     http://localhost:8000/api/v1/ai/message

# Clear Cache
curl -X DELETE \\
     -H "Authorization: Bearer {token_preview}" \\
     http://localhost:8000/api/v1/ai/cache
""")


def main():
    """Main function to run the demo."""
    clerk_token = None
    
    # Check for token in command line arguments
    if len(sys.argv) > 1:
        clerk_token = sys.argv[1]
    
    demo = ClerkAIDemo(clerk_token)
    
    if clerk_token:
        # Run full demo
        demo.run_full_demo()
    else:
        # Show instructions and examples
        print("🤖 AI Assistant API Demo with Clerk Authentication")
        print("=" * 60)
        print("\n💡 Usage: python3 clerk_ai_demo.py [CLERK_JWT_TOKEN]")
        
        demo.show_example_curl_commands()
        
        print("\n📝 Getting Your Clerk Token:")
        print("1. Open your AIR frontend application")
        print("2. Log in with your account")
        print("3. Open browser developer tools (F12)")
        print("4. Go to Console tab")
        print("5. Run: await window.clerk.session.getToken()")
        print("6. Copy the JWT token and run this script again")


if __name__ == "__main__":
    main() 