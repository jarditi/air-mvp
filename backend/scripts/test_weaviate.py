#!/usr/bin/env python3
"""Test script for Weaviate client and embeddings functionality."""

import sys
import os
import asyncio
import json
from typing import Dict, Any, List
from uuid import uuid4

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.weaviate_client import get_weaviate_client, close_weaviate_client
from lib.embeddings import get_embedding_generator, get_embedding_cache, generate_cached_embedding


def test_weaviate_connection():
    """Test Weaviate connection and health check."""
    print("🔍 Testing Weaviate connection...")
    
    try:
        client = get_weaviate_client()
        health = client.health_check()
        
        print(f"✅ Weaviate Health Check:")
        print(f"   - Ready: {health['ready']}")
        print(f"   - Live: {health['live']}")
        print(f"   - Status: {health['status']}")
        print(f"   - URL: {health['url']}")
        
        if health.get('error'):
            print(f"   - Error: {health['error']}")
            return False
        
        return health['ready'] and health['live']
        
    except Exception as e:
        print(f"❌ Weaviate connection failed: {e}")
        return False


def test_embedding_generation():
    """Test embedding generation functionality."""
    print("\n🧠 Testing embedding generation...")
    
    try:
        generator = get_embedding_generator()
        
        # Test basic text embedding
        test_text = "This is a test sentence for embedding generation."
        embedding = generator.generate_text_embedding(test_text)
        
        print(f"✅ Generated text embedding:")
        print(f"   - Dimension: {len(embedding)}")
        print(f"   - First 5 values: {embedding[:5]}")
        print(f"   - Text length: {len(test_text)} chars")
        
        # Test contact embedding
        contact_data = {
            "first_name": "John",
            "last_name": "Doe",
            "company": "Tech Corp",
            "job_title": "Software Engineer",
            "email": "john.doe@techcorp.com",
            "notes": "Interested in AI and machine learning",
            "tags": ["tech", "ai", "engineering"]
        }
        
        contact_embedding = generator.generate_contact_embedding(contact_data)
        print(f"✅ Generated contact embedding:")
        print(f"   - Dimension: {len(contact_embedding)}")
        print(f"   - Contact: {contact_data['first_name']} {contact_data['last_name']}")
        
        # Test interaction embedding
        interaction_data = {
            "type": "email",
            "direction": "outbound",
            "subject": "Follow up on our AI discussion",
            "content": "Hi John, I wanted to follow up on our conversation about implementing AI in our workflow.",
            "context": "Business meeting follow-up"
        }
        
        interaction_embedding = generator.generate_interaction_embedding(interaction_data)
        print(f"✅ Generated interaction embedding:")
        print(f"   - Dimension: {len(interaction_embedding)}")
        print(f"   - Type: {interaction_data['type']}")
        
        # Test similarity calculation
        similarity = generator.calculate_similarity(embedding, contact_embedding)
        print(f"✅ Similarity calculation:")
        print(f"   - Text vs Contact: {similarity:.4f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Embedding generation failed: {e}")
        return False


def test_embedding_cache():
    """Test embedding caching functionality."""
    print("\n💾 Testing embedding cache...")
    
    try:
        cache = get_embedding_cache()
        generator = get_embedding_generator()
        
        # Test cache operations
        test_text = "This is a test for caching functionality."
        text_hash = generator.get_embedding_hash(test_text)
        
        # Should be empty initially
        cached_result = cache.get(text_hash)
        print(f"✅ Initial cache state: {cached_result is None}")
        
        # Generate and cache embedding
        embedding = generate_cached_embedding(test_text)
        print(f"✅ Generated cached embedding: {len(embedding)} dimensions")
        
        # Should now be in cache
        cached_result = cache.get(text_hash)
        print(f"✅ Cache hit: {cached_result is not None}")
        print(f"   - Cache size: {cache.size()}")
        
        # Test cache retrieval
        embedding2 = generate_cached_embedding(test_text)
        print(f"✅ Retrieved from cache: {len(embedding2)} dimensions")
        
        # Should be identical
        is_identical = embedding == embedding2
        print(f"✅ Cache consistency: {is_identical}")
        
        return True
        
    except Exception as e:
        print(f"❌ Embedding cache test failed: {e}")
        return False


def test_weaviate_operations():
    """Test Weaviate CRUD operations."""
    print("\n🗄️ Testing Weaviate operations...")
    
    try:
        client = get_weaviate_client()
        generator = get_embedding_generator()
        
        # Test user and contact IDs
        user_id = str(uuid4())
        contact_id = str(uuid4())
        
        # Test contact embedding storage
        contact_data = {
            "first_name": "Alice",
            "last_name": "Smith",
            "company": "AI Innovations",
            "job_title": "Data Scientist",
            "notes": "Expert in machine learning and data analysis",
            "tags": ["ai", "data-science", "python"],
            "relationshipStrength": 0.8
        }
        
        contact_embedding = generator.generate_contact_embedding(contact_data)
        
        contact_properties = {
            "fullName": f"{contact_data['first_name']} {contact_data['last_name']}",
            "company": contact_data["company"],
            "jobTitle": contact_data["job_title"],
            "notes": contact_data["notes"],
            "tags": contact_data["tags"],
            "relationshipStrength": contact_data["relationshipStrength"]
        }
        
        weaviate_contact_id = client.add_contact_embedding(
            contact_id=contact_id,
            user_id=user_id,
            embedding=contact_embedding,
            properties=contact_properties
        )
        
        print(f"✅ Added contact to Weaviate:")
        print(f"   - Contact ID: {contact_id}")
        print(f"   - Weaviate ID: {weaviate_contact_id}")
        print(f"   - Name: {contact_properties['fullName']}")
        
        # Test interaction embedding storage
        interaction_id = str(uuid4())
        interaction_data = {
            "type": "meeting",
            "subject": "AI Strategy Discussion",
            "content": "Discussed implementation of AI tools in data analysis workflow",
            "occurredAt": "2024-01-15T10:00:00Z",
            "sentimentScore": 0.7,
            "importanceScore": 0.9
        }
        
        interaction_embedding = generator.generate_interaction_embedding(interaction_data)
        
        weaviate_interaction_id = client.add_interaction_embedding(
            interaction_id=interaction_id,
            user_id=user_id,
            contact_id=contact_id,
            embedding=interaction_embedding,
            properties=interaction_data
        )
        
        print(f"✅ Added interaction to Weaviate:")
        print(f"   - Interaction ID: {interaction_id}")
        print(f"   - Weaviate ID: {weaviate_interaction_id}")
        print(f"   - Subject: {interaction_data['subject']}")
        
        # Test search functionality
        query_text = "data science and machine learning expert"
        query_embedding = generator.generate_query_embedding(query_text)
        
        similar_contacts = client.search_similar_contacts(
            user_id=user_id,
            query_vector=query_embedding,
            limit=5,
            min_certainty=0.5
        )
        
        print(f"✅ Search results for '{query_text}':")
        print(f"   - Found {len(similar_contacts)} similar contacts")
        
        for i, contact in enumerate(similar_contacts):
            certainty = contact.get("_additional", {}).get("certainty", 0)
            print(f"   - {i+1}. {contact.get('fullName', 'Unknown')} (certainty: {certainty:.3f})")
        
        # Test interaction search
        interaction_query = "AI strategy and implementation"
        interaction_query_embedding = generator.generate_query_embedding(interaction_query)
        
        similar_interactions = client.search_similar_interactions(
            user_id=user_id,
            query_vector=interaction_query_embedding,
            limit=5,
            min_certainty=0.5
        )
        
        print(f"✅ Interaction search results for '{interaction_query}':")
        print(f"   - Found {len(similar_interactions)} similar interactions")
        
        for i, interaction in enumerate(similar_interactions):
            certainty = interaction.get("_additional", {}).get("certainty", 0)
            print(f"   - {i+1}. {interaction.get('subject', 'Unknown')} (certainty: {certainty:.3f})")
        
        # Test statistics
        stats = client.get_stats()
        print(f"✅ Weaviate statistics:")
        for class_name, count in stats.items():
            if class_name != "cluster_status":
                print(f"   - {class_name}: {count} objects")
        
        # Cleanup test data
        client.delete_embedding(weaviate_contact_id, "Contact")
        client.delete_embedding(weaviate_interaction_id, "Interaction")
        print(f"✅ Cleaned up test data")
        
        return True
        
    except Exception as e:
        print(f"❌ Weaviate operations test failed: {e}")
        return False


def test_interest_and_memory_operations():
    """Test interest and memory embedding operations."""
    print("\n🎯 Testing interest and memory operations...")
    
    try:
        client = get_weaviate_client()
        generator = get_embedding_generator()
        
        user_id = str(uuid4())
        contact_id = str(uuid4())
        
        # Test interest embedding
        interest_id = str(uuid4())
        interest_data = {
            "category": "technology",
            "topic": "artificial intelligence",
            "context": "Mentioned interest in AI during conversation about automation",
            "source": "email_analysis",
            "confidenceScore": 0.85
        }
        
        interest_embedding = generator.generate_interest_embedding(interest_data)
        
        weaviate_interest_id = client.add_interest_embedding(
            interest_id=interest_id,
            user_id=user_id,
            contact_id=contact_id,
            embedding=interest_embedding,
            properties=interest_data
        )
        
        print(f"✅ Added interest to Weaviate:")
        print(f"   - Interest ID: {interest_id}")
        print(f"   - Topic: {interest_data['topic']}")
        print(f"   - Confidence: {interest_data['confidenceScore']}")
        
        # Test memory embedding
        memory_id = str(uuid4())
        memory_data = {
            "memoryType": "insight",
            "content": "Contact shows strong interest in AI automation tools for business processes",
            "context": "Derived from multiple email exchanges and meeting notes",
            "confidenceScore": 0.9,
            "tags": ["ai", "automation", "business-process"]
        }
        
        memory_embedding = generator.generate_memory_embedding(memory_data)
        
        weaviate_memory_id = client.add_memory_embedding(
            memory_id=memory_id,
            user_id=user_id,
            embedding=memory_embedding,
            properties={**memory_data, "contactId": contact_id}
        )
        
        print(f"✅ Added memory to Weaviate:")
        print(f"   - Memory ID: {memory_id}")
        print(f"   - Type: {memory_data['memoryType']}")
        print(f"   - Content preview: {memory_data['content'][:50]}...")
        
        # Test interest search
        interest_query = "machine learning and automation"
        interest_query_embedding = generator.generate_query_embedding(interest_query)
        
        similar_interests = client.search_similar_interests(
            user_id=user_id,
            query_vector=interest_query_embedding,
            limit=5,
            min_certainty=0.5
        )
        
        print(f"✅ Interest search results:")
        print(f"   - Found {len(similar_interests)} similar interests")
        
        # Test memory search
        memory_query = "business automation insights"
        memory_query_embedding = generator.generate_query_embedding(memory_query)
        
        similar_memories = client.search_memories(
            user_id=user_id,
            query_vector=memory_query_embedding,
            limit=5,
            min_certainty=0.5
        )
        
        print(f"✅ Memory search results:")
        print(f"   - Found {len(similar_memories)} similar memories")
        
        # Cleanup
        client.delete_embedding(weaviate_interest_id, "Interest")
        client.delete_embedding(weaviate_memory_id, "AIMemory")
        print(f"✅ Cleaned up test data")
        
        return True
        
    except Exception as e:
        print(f"❌ Interest and memory operations test failed: {e}")
        return False


def main():
    """Run all Weaviate tests."""
    print("🚀 Starting Weaviate Client Tests")
    print("=" * 50)
    
    tests = [
        ("Weaviate Connection", test_weaviate_connection),
        ("Embedding Generation", test_embedding_generation),
        ("Embedding Cache", test_embedding_cache),
        ("Weaviate Operations", test_weaviate_operations),
        ("Interest & Memory Operations", test_interest_and_memory_operations),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 All tests passed! Weaviate client is working correctly.")
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
    
    # Cleanup
    try:
        close_weaviate_client()
        print("🧹 Cleaned up Weaviate client")
    except Exception as e:
        print(f"⚠️ Error during cleanup: {e}")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 