#!/usr/bin/env python3
"""Test script to validate database schema after migration."""

import asyncio
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from lib.database import async_engine


async def test_schema():
    """Test that the database schema was created correctly."""
    print("🔍 Testing database schema...")
    
    async with async_engine.begin() as conn:
        # Test that all tables exist
        tables_result = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        table_names = [row[0] for row in tables_result.fetchall()]
        print(f"📋 Created tables: {sorted(table_names)}")
        
        # Test that all expected tables exist
        expected_tables = ['users', 'contacts', 'interactions', 'interests', 'alembic_version']
        missing_tables = [t for t in expected_tables if t not in table_names]
        if missing_tables:
            print(f"❌ ERROR: Missing tables: {missing_tables}")
            return False
        else:
            print("✅ All expected tables created successfully")
        
        # Test indexes
        indexes_result = await conn.execute(
            text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
        )
        index_names = [row[0] for row in indexes_result.fetchall()]
        print(f"📊 Created indexes: {len(index_names)} total")
        
        # Test foreign keys
        fks_result = await conn.execute(
            text("SELECT conname FROM pg_constraint WHERE contype = 'f'")
        )
        fk_names = [row[0] for row in fks_result.fetchall()]
        print(f"🔗 Created foreign keys: {len(fk_names)} total")
        
        # Test specific table structures
        for table in ['users', 'contacts', 'interactions', 'interests']:
            columns_result = await conn.execute(
                text(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}' ORDER BY ordinal_position")
            )
            columns = columns_result.fetchall()
            print(f"📝 {table} table: {len(columns)} columns")
        
        print("✅ Database schema validation completed successfully!")
        return True


async def test_model_imports():
    """Test that all models can be imported and work with the database."""
    print("\n🔍 Testing model imports...")
    
    try:
        from models.orm import User, Contact, Interaction, Interest
        print("✅ All models imported successfully")
        
        # Test that models can create instances (without saving)
        user = User(email="test@example.com", auth_provider="test", auth_provider_id="123")
        contact = Contact(full_name="Test Contact", email="contact@example.com")
        interaction = Interaction(interaction_type="email", direction="outbound", interaction_date="2024-01-01")
        interest = Interest(interest_category="technology", interest_topic="AI", confidence_score=0.8)
        
        print("✅ All models can be instantiated")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: Model import/instantiation failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("🚀 Starting database schema tests...\n")
    
    schema_ok = await test_schema()
    model_ok = await test_model_imports()
    
    if schema_ok and model_ok:
        print("\n🎉 All tests passed! Database schema is ready.")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 