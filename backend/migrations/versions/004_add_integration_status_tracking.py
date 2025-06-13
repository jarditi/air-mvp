"""Add integration status tracking tables

Revision ID: 004
Revises: 003
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    """Add integration status tracking tables."""
    
    # Create integration_status_events table
    op.create_table(
        'integration_status_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        
        # Foreign key to integration
        sa.Column('integration_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('integrations.id', ondelete='CASCADE'), nullable=False, index=True),
        
        # Event details
        sa.Column('event_type', sa.String(50), nullable=False, index=True),
        sa.Column('severity', sa.String(20), nullable=False, index=True),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('details', postgresql.JSONB, default={}),
        
        # Status tracking
        sa.Column('previous_status', sa.String(20)),
        sa.Column('new_status', sa.String(20)),
        
        # Context information
        sa.Column('user_agent', sa.String(255)),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('source', sa.String(50), default='system'),
        
        # Metrics
        sa.Column('duration_ms', sa.Integer),
        sa.Column('items_affected', sa.Integer),
        
        # Resolution tracking
        sa.Column('resolved', sa.Boolean, default=False),
        sa.Column('resolved_at', sa.DateTime),
        sa.Column('resolution_message', sa.Text),
    )
    
    # Create integration_health_checks table
    op.create_table(
        'integration_health_checks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        
        # Foreign key to integration
        sa.Column('integration_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('integrations.id', ondelete='CASCADE'), nullable=False, index=True),
        
        # Health check details
        sa.Column('check_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        
        # Results
        sa.Column('response_time_ms', sa.Integer),
        sa.Column('success', sa.Boolean, nullable=False),
        sa.Column('error_message', sa.Text),
        sa.Column('details', postgresql.JSONB, default={}),
        
        # Metrics
        sa.Column('check_duration_ms', sa.Integer),
    )
    
    # Create integration_alerts table
    op.create_table(
        'integration_alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        
        # Foreign key to integration
        sa.Column('integration_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('integrations.id', ondelete='CASCADE'), nullable=False, index=True),
        
        # Alert details
        sa.Column('alert_type', sa.String(50), nullable=False, index=True),
        sa.Column('severity', sa.String(20), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('details', postgresql.JSONB, default={}),
        
        # Alert state
        sa.Column('status', sa.String(20), default='active', index=True),
        sa.Column('acknowledged', sa.Boolean, default=False),
        sa.Column('acknowledged_at', sa.DateTime),
        sa.Column('acknowledged_by', sa.String(255)),
        
        # Resolution
        sa.Column('resolved', sa.Boolean, default=False),
        sa.Column('resolved_at', sa.DateTime),
        sa.Column('resolution_message', sa.Text),
        sa.Column('auto_resolved', sa.Boolean, default=False),
        
        # Notification tracking
        sa.Column('notification_sent', sa.Boolean, default=False),
        sa.Column('notification_sent_at', sa.DateTime),
        sa.Column('notification_channels', postgresql.JSONB, default=[]),
        
        # Suppression
        sa.Column('suppressed_until', sa.DateTime),
        sa.Column('suppression_reason', sa.Text),
    )
    
    # Create indexes for better query performance
    op.create_index('idx_integration_status_events_integration_type', 'integration_status_events', ['integration_id', 'event_type'])
    op.create_index('idx_integration_status_events_severity_created', 'integration_status_events', ['severity', 'created_at'])
    op.create_index('idx_integration_status_events_created_at', 'integration_status_events', ['created_at'])
    
    op.create_index('idx_integration_health_checks_integration_type', 'integration_health_checks', ['integration_id', 'check_type'])
    op.create_index('idx_integration_health_checks_status_created', 'integration_health_checks', ['status', 'created_at'])
    op.create_index('idx_integration_health_checks_created_at', 'integration_health_checks', ['created_at'])
    
    op.create_index('idx_integration_alerts_integration_type', 'integration_alerts', ['integration_id', 'alert_type'])
    op.create_index('idx_integration_alerts_status_severity', 'integration_alerts', ['status', 'severity'])
    op.create_index('idx_integration_alerts_created_at', 'integration_alerts', ['created_at'])
    op.create_index('idx_integration_alerts_active', 'integration_alerts', ['status'], postgresql_where=sa.text("status IN ('active', 'acknowledged')"))


def downgrade():
    """Remove integration status tracking tables."""
    
    # Drop indexes
    op.drop_index('idx_integration_alerts_active')
    op.drop_index('idx_integration_alerts_created_at')
    op.drop_index('idx_integration_alerts_status_severity')
    op.drop_index('idx_integration_alerts_integration_type')
    
    op.drop_index('idx_integration_health_checks_created_at')
    op.drop_index('idx_integration_health_checks_status_created')
    op.drop_index('idx_integration_health_checks_integration_type')
    
    op.drop_index('idx_integration_status_events_created_at')
    op.drop_index('idx_integration_status_events_severity_created')
    op.drop_index('idx_integration_status_events_integration_type')
    
    # Drop tables
    op.drop_table('integration_alerts')
    op.drop_table('integration_health_checks')
    op.drop_table('integration_status_events') 