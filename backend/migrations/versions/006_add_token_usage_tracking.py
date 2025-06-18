"""Add token usage tracking tables

Revision ID: 006_add_token_usage_tracking
Revises: 005_add_job_results_table
Create Date: 2024-01-15 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006_add_token_usage_tracking'
down_revision = '005_add_job_results_table'
branch_labels = None
depends_on = None


def upgrade():
    """Add token usage tracking tables for comprehensive LLM usage monitoring"""
    
    # Create llm_usage_logs table
    op.create_table(
        'llm_usage_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), index=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        
        # User and request tracking
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('request_id', sa.String(255), nullable=True, index=True),
        sa.Column('session_id', sa.String(255), nullable=True, index=True),
        
        # Model and usage details
        sa.Column('model', sa.String(50), nullable=False, index=True),
        sa.Column('usage_type', sa.String(50), nullable=False, index=True),
        sa.Column('prompt_tokens', sa.Integer, nullable=False),
        sa.Column('completion_tokens', sa.Integer, nullable=False),
        sa.Column('total_tokens', sa.Integer, nullable=False, index=True),
        
        # Cost and performance
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=False, index=True),
        sa.Column('response_time_ms', sa.Integer, nullable=False),
        
        # Request context
        sa.Column('endpoint', sa.String(255), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        
        # Content metadata (for analysis)
        sa.Column('prompt_length', sa.Integer, nullable=True),
        sa.Column('completion_length', sa.Integer, nullable=True),
        sa.Column('temperature', sa.Numeric(3, 2), nullable=True),
        sa.Column('max_tokens', sa.Integer, nullable=True),
        
        # Success/failure tracking
        sa.Column('success', sa.Boolean, nullable=False, default=True, index=True),
        sa.Column('error_type', sa.String(100), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        
        # Caching information
        sa.Column('cached_response', sa.Boolean, nullable=False, default=False, index=True),
        sa.Column('cache_key', sa.String(255), nullable=True),
        
        # Additional metadata
        sa.Column('request_metadata', postgresql.JSONB, default={}),
    )
    
    # Create llm_usage_summaries table for aggregated data
    op.create_table(
        'llm_usage_summaries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        
        # Aggregation period
        sa.Column('period_type', sa.String(20), nullable=False, index=True),  # 'hour', 'day', 'week', 'month'
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False, index=True),
        
        # Grouping dimensions
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('model', sa.String(50), nullable=True, index=True),
        sa.Column('usage_type', sa.String(50), nullable=True, index=True),
        
        # Aggregated metrics
        sa.Column('total_requests', sa.Integer, nullable=False, default=0),
        sa.Column('successful_requests', sa.Integer, nullable=False, default=0),
        sa.Column('failed_requests', sa.Integer, nullable=False, default=0),
        sa.Column('total_tokens', sa.BigInteger, nullable=False, default=0),
        sa.Column('total_prompt_tokens', sa.BigInteger, nullable=False, default=0),
        sa.Column('total_completion_tokens', sa.BigInteger, nullable=False, default=0),
        sa.Column('total_cost_usd', sa.Numeric(12, 6), nullable=False, default=0),
        
        # Performance metrics
        sa.Column('avg_response_time_ms', sa.Integer, nullable=True),
        sa.Column('min_response_time_ms', sa.Integer, nullable=True),
        sa.Column('max_response_time_ms', sa.Integer, nullable=True),
        sa.Column('p95_response_time_ms', sa.Integer, nullable=True),
        
        # Cache metrics
        sa.Column('cache_hit_rate', sa.Numeric(5, 4), nullable=True),  # 0.0000 to 1.0000
        sa.Column('cached_requests', sa.Integer, nullable=False, default=0),
        
        # Additional aggregated data
        sa.Column('unique_users', sa.Integer, nullable=True),
        sa.Column('unique_sessions', sa.Integer, nullable=True),
        sa.Column('summary_metadata', postgresql.JSONB, default={}),
    )
    
    # Create llm_cost_budgets table for cost management
    op.create_table(
        'llm_cost_budgets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        
        # Budget scope
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('budget_type', sa.String(20), nullable=False, index=True),  # 'user', 'global', 'usage_type'
        sa.Column('scope', sa.String(50), nullable=True),  # For usage_type budgets
        
        # Budget configuration
        sa.Column('budget_period', sa.String(20), nullable=False),  # 'daily', 'weekly', 'monthly'
        sa.Column('budget_amount_usd', sa.Numeric(10, 2), nullable=False),
        sa.Column('warning_threshold', sa.Numeric(3, 2), nullable=False, default=0.8),  # 80% warning
        sa.Column('hard_limit', sa.Boolean, nullable=False, default=False),
        
        # Current period tracking
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('current_period_spent', sa.Numeric(10, 6), nullable=False, default=0),
        sa.Column('current_period_requests', sa.Integer, nullable=False, default=0),
        
        # Status
        sa.Column('is_active', sa.Boolean, nullable=False, default=True, index=True),
        sa.Column('last_warning_sent', sa.DateTime(timezone=True), nullable=True),
        sa.Column('budget_exceeded', sa.Boolean, nullable=False, default=False, index=True),
        
        # Metadata
        sa.Column('budget_metadata', postgresql.JSONB, default={}),
    )
    
    # Create indexes for better query performance
    op.create_index('idx_llm_usage_logs_user_date', 'llm_usage_logs', ['user_id', 'created_at'])
    op.create_index('idx_llm_usage_logs_model_type', 'llm_usage_logs', ['model', 'usage_type'])
    op.create_index('idx_llm_usage_logs_cost_date', 'llm_usage_logs', ['cost_usd', 'created_at'])
    op.create_index('idx_llm_usage_logs_success_date', 'llm_usage_logs', ['success', 'created_at'])
    
    op.create_index('idx_llm_usage_summaries_period', 'llm_usage_summaries', ['period_type', 'period_start', 'period_end'])
    op.create_index('idx_llm_usage_summaries_user_period', 'llm_usage_summaries', ['user_id', 'period_start'])
    op.create_index('idx_llm_usage_summaries_model_period', 'llm_usage_summaries', ['model', 'period_start'])
    
    op.create_index('idx_llm_cost_budgets_user_active', 'llm_cost_budgets', ['user_id', 'is_active'])
    op.create_index('idx_llm_cost_budgets_period', 'llm_cost_budgets', ['current_period_start', 'current_period_end'])
    op.create_index('idx_llm_cost_budgets_exceeded', 'llm_cost_budgets', ['budget_exceeded', 'is_active'])
    
    # Create unique constraints
    op.create_index('idx_llm_usage_summaries_unique', 'llm_usage_summaries', 
                   ['period_type', 'period_start', 'user_id', 'model', 'usage_type'], unique=True)


def downgrade():
    """Remove token usage tracking tables"""
    op.drop_table('llm_cost_budgets')
    op.drop_table('llm_usage_summaries')
    op.drop_table('llm_usage_logs') 