# AIR MVP Database Schema

## Overview

This document defines the database schema for the AIR (AI-native Relationship Management) MVP system. The schema is designed to support relationship tracking, AI-powered insights, and multi-platform integrations.

## Core Principles

- **Privacy-first**: All sensitive data is encrypted at rest
- **Graph-oriented**: Optimized for relationship queries and graph traversal
- **Integration-ready**: Supports multiple OAuth providers and data sources
- **AI-native**: Structured for LLM processing and vector embeddings
- **Audit-compliant**: Full audit trail for data access and modifications

## Database Tables

### 1. Users Table

Primary user accounts and authentication data.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    auth_provider VARCHAR(50) NOT NULL, -- 'auth0', 'clerk', 'google'
    auth_provider_id VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    avatar_url TEXT,
    timezone VARCHAR(50) DEFAULT 'UTC',
    subscription_tier VARCHAR(20) DEFAULT 'free', -- 'free', 'pro', 'enterprise'
    subscription_status VARCHAR(20) DEFAULT 'active', -- 'active', 'cancelled', 'past_due'
    onboarding_completed BOOLEAN DEFAULT FALSE,
    privacy_settings JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_auth_provider ON users(auth_provider, auth_provider_id);
```

### 2. Contacts Table

People in the user's relationship network.

```sql
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(255),
    full_name VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    company VARCHAR(255),
    job_title VARCHAR(255),
    linkedin_url TEXT,
    phone VARCHAR(50),
    avatar_url TEXT,
    location VARCHAR(255),
    bio TEXT,
    relationship_strength DECIMAL(3,2) DEFAULT 0.0, -- 0.0 to 1.0
    last_interaction_at TIMESTAMP WITH TIME ZONE,
    interaction_frequency VARCHAR(20), -- 'daily', 'weekly', 'monthly', 'quarterly', 'rarely'
    contact_source VARCHAR(50), -- 'gmail', 'calendar', 'linkedin', 'manual'
    is_archived BOOLEAN DEFAULT FALSE,
    tags TEXT[], -- Array of user-defined tags
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_contacts_user_id ON contacts(user_id);
CREATE INDEX idx_contacts_email ON contacts(email);
CREATE INDEX idx_contacts_company ON contacts(company);
CREATE INDEX idx_contacts_relationship_strength ON contacts(relationship_strength DESC);
CREATE INDEX idx_contacts_last_interaction ON contacts(last_interaction_at DESC);
```

### 3. Interactions Table

All communications and touchpoints with contacts.

```sql
CREATE TABLE interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contact_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    interaction_type VARCHAR(50) NOT NULL, -- 'email', 'meeting', 'call', 'linkedin_message', 'manual'
    direction VARCHAR(10) NOT NULL, -- 'inbound', 'outbound', 'mutual'
    subject VARCHAR(500),
    content TEXT,
    content_summary TEXT, -- AI-generated summary
    sentiment_score DECIMAL(3,2), -- -1.0 to 1.0
    interaction_date TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_minutes INTEGER, -- For meetings/calls
    meeting_attendees TEXT[], -- Array of attendee emails
    external_id VARCHAR(255), -- ID from source system (Gmail message ID, etc.)
    source_platform VARCHAR(50), -- 'gmail', 'calendar', 'linkedin', 'manual'
    metadata JSONB DEFAULT '{}', -- Platform-specific data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_interactions_user_id ON interactions(user_id);
CREATE INDEX idx_interactions_contact_id ON interactions(contact_id);
CREATE INDEX idx_interactions_date ON interactions(interaction_date DESC);
CREATE INDEX idx_interactions_type ON interactions(interaction_type);
CREATE INDEX idx_interactions_external_id ON interactions(external_id);
```

### 4. Interests Table

Detected interests and topics for contacts.

```sql
CREATE TABLE interests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contact_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    interest_category VARCHAR(100) NOT NULL, -- 'technology', 'sports', 'travel', etc.
    interest_topic VARCHAR(255) NOT NULL, -- Specific topic within category
    confidence_score DECIMAL(3,2) NOT NULL, -- 0.0 to 1.0
    evidence_count INTEGER DEFAULT 1, -- Number of supporting interactions
    first_detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_reinforced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    decay_factor DECIMAL(3,2) DEFAULT 1.0, -- For interest decay over time
    source_interactions UUID[], -- Array of interaction IDs that support this interest
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_interests_user_id ON interests(user_id);
CREATE INDEX idx_interests_contact_id ON interests(contact_id);
CREATE INDEX idx_interests_category ON interests(interest_category);
CREATE INDEX idx_interests_confidence ON interests(confidence_score DESC);
CREATE UNIQUE INDEX idx_interests_unique ON interests(contact_id, interest_category, interest_topic);
```

### 5. Integrations Table

OAuth tokens and integration status for external platforms.

```sql
CREATE TABLE integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL, -- 'gmail', 'calendar', 'linkedin'
    status VARCHAR(20) DEFAULT 'disconnected', -- 'connected', 'disconnected', 'error', 'expired'
    access_token TEXT, -- Encrypted
    refresh_token TEXT, -- Encrypted
    token_expires_at TIMESTAMP WITH TIME ZONE,
    scope TEXT[], -- Array of granted permissions
    last_sync_at TIMESTAMP WITH TIME ZONE,
    sync_frequency VARCHAR(20) DEFAULT 'hourly', -- 'realtime', 'hourly', 'daily'
    error_message TEXT,
    metadata JSONB DEFAULT '{}', -- Platform-specific settings
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_integrations_user_id ON integrations(user_id);
CREATE INDEX idx_integrations_platform ON integrations(platform);
CREATE INDEX idx_integrations_status ON integrations(status);
CREATE UNIQUE INDEX idx_integrations_user_platform ON integrations(user_id, platform);
```

### 6. Relationships Table

Graph connections and relationship metadata.

```sql
CREATE TABLE relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contact_a_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    contact_b_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50), -- 'colleague', 'friend', 'client', 'vendor', 'family'
    strength_score DECIMAL(3,2) DEFAULT 0.0, -- 0.0 to 1.0
    mutual_connections INTEGER DEFAULT 0,
    shared_interactions INTEGER DEFAULT 0,
    evidence_interactions UUID[], -- Array of interaction IDs that show connection
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_relationships_user_id ON relationships(user_id);
CREATE INDEX idx_relationships_contact_a ON relationships(contact_a_id);
CREATE INDEX idx_relationships_contact_b ON relationships(contact_b_id);
CREATE INDEX idx_relationships_strength ON relationships(strength_score DESC);
CREATE UNIQUE INDEX idx_relationships_unique ON relationships(user_id, contact_a_id, contact_b_id);
```

### 7. AI Memories Table

AI-generated summaries and insights about contacts and relationships.

```sql
CREATE TABLE ai_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contacts(id) ON DELETE CASCADE,
    memory_type VARCHAR(50) NOT NULL, -- 'summary', 'insight', 'briefing', 'talking_point'
    title VARCHAR(255),
    content TEXT NOT NULL,
    confidence_score DECIMAL(3,2), -- 0.0 to 1.0
    source_interactions UUID[], -- Array of interaction IDs used to generate memory
    embedding VECTOR(1536), -- OpenAI embedding for semantic search
    tags TEXT[],
    is_archived BOOLEAN DEFAULT FALSE,
    expires_at TIMESTAMP WITH TIME ZONE, -- For temporary memories
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_ai_memories_user_id ON ai_memories(user_id);
CREATE INDEX idx_ai_memories_contact_id ON ai_memories(contact_id);
CREATE INDEX idx_ai_memories_type ON ai_memories(memory_type);
CREATE INDEX idx_ai_memories_embedding ON ai_memories USING ivfflat (embedding vector_cosine_ops);
```

### 8. Notifications Table

Alerts, nudges, and system notifications.

```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
    notification_type VARCHAR(50) NOT NULL, -- 'going_cold', 'job_change', 'birthday', 'follow_up'
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    priority VARCHAR(10) DEFAULT 'medium', -- 'low', 'medium', 'high', 'urgent'
    status VARCHAR(20) DEFAULT 'unread', -- 'unread', 'read', 'dismissed', 'acted_upon'
    action_url TEXT, -- Deep link to relevant page
    metadata JSONB DEFAULT '{}',
    scheduled_for TIMESTAMP WITH TIME ZONE, -- For future notifications
    delivered_at TIMESTAMP WITH TIME ZONE,
    read_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_status ON notifications(status);
CREATE INDEX idx_notifications_type ON notifications(notification_type);
CREATE INDEX idx_notifications_scheduled ON notifications(scheduled_for);
```

### 9. Sync Jobs Table

Background job tracking for data synchronization.

```sql
CREATE TABLE sync_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    integration_id UUID NOT NULL REFERENCES integrations(id) ON DELETE CASCADE,
    job_type VARCHAR(50) NOT NULL, -- 'full_sync', 'incremental_sync', 'contact_enrichment'
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed', 'cancelled'
    progress_percentage INTEGER DEFAULT 0,
    items_processed INTEGER DEFAULT 0,
    items_total INTEGER,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sync_jobs_user_id ON sync_jobs(user_id);
CREATE INDEX idx_sync_jobs_integration_id ON sync_jobs(integration_id);
CREATE INDEX idx_sync_jobs_status ON sync_jobs(status);
CREATE INDEX idx_sync_jobs_created ON sync_jobs(created_at DESC);
```

### 10. Audit Log Table

Complete audit trail for compliance and debugging.

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL, -- 'create', 'update', 'delete', 'view', 'export'
    resource_type VARCHAR(50) NOT NULL, -- 'contact', 'interaction', 'integration', etc.
    resource_id UUID,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    api_endpoint VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at DESC);
```

## Relationships and Constraints

### Foreign Key Relationships

- `contacts.user_id` → `users.id`
- `interactions.user_id` → `users.id`
- `interactions.contact_id` → `contacts.id`
- `interests.user_id` → `users.id`
- `interests.contact_id` → `contacts.id`
- `integrations.user_id` → `users.id`
- `relationships.user_id` → `users.id`
- `relationships.contact_a_id` → `contacts.id`
- `relationships.contact_b_id` → `contacts.id`
- `ai_memories.user_id` → `users.id`
- `ai_memories.contact_id` → `contacts.id`
- `notifications.user_id` → `users.id`
- `notifications.contact_id` → `contacts.id`
- `sync_jobs.user_id` → `users.id`
- `sync_jobs.integration_id` → `integrations.id`

### Business Rules

1. **Data Isolation**: All user data is strictly isolated by `user_id`
2. **Soft Deletes**: Contacts can be archived instead of deleted
3. **Relationship Symmetry**: Relationships are bidirectional but stored once
4. **Interest Decay**: Interest confidence scores decay over time without reinforcement
5. **Token Security**: OAuth tokens are encrypted at rest
6. **Audit Compliance**: All data modifications are logged

## Vector Database Schema (Weaviate)

For semantic search and AI operations, we use Weaviate with the following schema:

### Contact Embeddings Class

```json
{
  "class": "ContactEmbedding",
  "properties": [
    {"name": "userId", "dataType": ["string"]},
    {"name": "contactId", "dataType": ["string"]},
    {"name": "fullName", "dataType": ["string"]},
    {"name": "company", "dataType": ["string"]},
    {"name": "jobTitle", "dataType": ["string"]},
    {"name": "bio", "dataType": ["text"]},
    {"name": "lastInteractionSummary", "dataType": ["text"]},
    {"name": "interests", "dataType": ["string[]"]},
    {"name": "relationshipStrength", "dataType": ["number"]},
    {"name": "updatedAt", "dataType": ["date"]}
  ],
  "vectorizer": "text2vec-openai"
}
```

### Interaction Embeddings Class

```json
{
  "class": "InteractionEmbedding",
  "properties": [
    {"name": "userId", "dataType": ["string"]},
    {"name": "contactId", "dataType": ["string"]},
    {"name": "interactionId", "dataType": ["string"]},
    {"name": "interactionType", "dataType": ["string"]},
    {"name": "subject", "dataType": ["string"]},
    {"name": "content", "dataType": ["text"]},
    {"name": "summary", "dataType": ["text"]},
    {"name": "sentimentScore", "dataType": ["number"]},
    {"name": "interactionDate", "dataType": ["date"]}
  ],
  "vectorizer": "text2vec-openai"
}
```

## Performance Considerations

### Indexing Strategy

- **Primary Keys**: All tables use UUID primary keys for distributed scaling
- **Foreign Keys**: Indexed for fast joins
- **Query Patterns**: Indexes optimized for common query patterns
- **Time-based**: Indexes on timestamp columns for chronological queries
- **Vector Search**: Specialized indexes for embedding similarity search

### Partitioning Strategy

For large datasets, consider partitioning by:
- `user_id` for data isolation
- Date ranges for time-series data (interactions, audit_logs)

### Caching Strategy

- **Redis**: Cache frequently accessed contact data and relationship graphs
- **Application**: Cache AI-generated summaries and embeddings
- **Database**: Use materialized views for complex aggregations

## Security Considerations

### Data Encryption

- **At Rest**: Sensitive fields (tokens, personal data) encrypted using AES-256
- **In Transit**: All connections use TLS 1.3
- **Application**: Field-level encryption for PII

### Access Control

- **Row-Level Security**: PostgreSQL RLS enforces user data isolation
- **API Authentication**: JWT tokens with short expiration
- **Audit Trail**: Complete logging of all data access

### Privacy Compliance

- **GDPR**: Right to be forgotten implemented via cascading deletes
- **Data Minimization**: Only necessary data is stored
- **Consent Management**: User privacy settings control data usage

## Migration Strategy

### Phase 1: Core Tables
1. Users, Contacts, Interactions
2. Basic indexes and constraints

### Phase 2: AI Features
1. Interests, AI Memories
2. Vector database setup

### Phase 3: Advanced Features
1. Relationships, Notifications
2. Sync Jobs, Audit Logs

### Phase 4: Optimization
1. Performance indexes
2. Partitioning
3. Materialized views

## Backup and Recovery

- **Daily Backups**: Automated PostgreSQL backups
- **Point-in-Time Recovery**: WAL archiving enabled
- **Cross-Region**: Backup replication for disaster recovery
- **Vector Data**: Weaviate backup strategy for embeddings

---

*This schema is designed to evolve with the product. All changes should be managed through Alembic migrations with proper testing and rollback procedures.* 