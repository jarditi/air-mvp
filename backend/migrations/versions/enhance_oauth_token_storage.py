"""enhance oauth token storage and add oauth state table

Revision ID: oauth_token_storage_v1
Revises: 7d327a558937
Create Date: 2024-01-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'oauth_token_storage_v1'
down_revision = '7d327a558937'
branch_labels = None
depends_on = None


def upgrade():
    """Upgrade database schema for enhanced OAuth token storage."""
    
    # Add new columns to integrations table
    op.add_column('integrations', sa.Column('provider_name', sa.String(length=50), nullable=True))
    op.add_column('integrations', sa.Column('access_token_encrypted', sa.Text(), nullable=True))
    op.add_column('integrations', sa.Column('refresh_token_encrypted', sa.Text(), nullable=True))
    op.add_column('integrations', sa.Column('token_type', sa.String(length=20), nullable=True, default='Bearer'))
    op.add_column('integrations', sa.Column('oauth_state', sa.String(length=255), nullable=True))
    op.add_column('integrations', sa.Column('oauth_code_verifier', sa.String(length=255), nullable=True))
    op.add_column('integrations', sa.Column('redirect_uri', sa.Text(), nullable=True))
    op.add_column('integrations', sa.Column('last_successful_sync_at', sa.DateTime(), nullable=True))
    op.add_column('integrations', sa.Column('auto_sync_enabled', sa.Boolean(), nullable=True, default=True))
    op.add_column('integrations', sa.Column('error_count', sa.Integer(), nullable=True, default=0))
    op.add_column('integrations', sa.Column('last_error_at', sa.DateTime(), nullable=True))
    op.add_column('integrations', sa.Column('retry_after', sa.DateTime(), nullable=True))
    op.add_column('integrations', sa.Column('total_syncs', sa.Integer(), nullable=True, default=0))
    op.add_column('integrations', sa.Column('total_items_synced', sa.Integer(), nullable=True, default=0))
    op.add_column('integrations', sa.Column('last_sync_duration_seconds', sa.Integer(), nullable=True))
    op.add_column('integrations', sa.Column('sync_settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True, default={}))
    op.add_column('integrations', sa.Column('features_enabled', postgresql.ARRAY(sa.Text()), nullable=True, default=[]))
    
    # Update existing columns
    op.alter_column('integrations', 'platform_metadata', 
                   existing_type=postgresql.JSONB(astext_type=sa.Text()),
                   nullable=True,
                   existing_nullable=True,
                   server_default='{}')
    
    # Update status column to include new statuses
    op.alter_column('integrations', 'status',
                   existing_type=sa.VARCHAR(length=20),
                   type_=sa.String(length=20),
                   existing_nullable=True,
                   existing_server_default=sa.text("'disconnected'::character varying"))
    
    # Rename old token columns (if they exist) and migrate data
    try:
        # Check if old columns exist and migrate data
        op.execute("""
            UPDATE integrations 
            SET access_token_encrypted = access_token,
                refresh_token_encrypted = refresh_token
            WHERE access_token IS NOT NULL OR refresh_token IS NOT NULL
        """)
        
        # Drop old columns
        op.drop_column('integrations', 'access_token')
        op.drop_column('integrations', 'refresh_token')
    except Exception:
        # Columns might not exist, continue
        pass
    
    # Set default values for new columns
    op.execute("""
        UPDATE integrations 
        SET provider_name = CASE 
            WHEN platform = 'google' THEN 'Google'
            WHEN platform = 'linkedin' THEN 'LinkedIn'
            WHEN platform = 'microsoft' THEN 'Microsoft'
            WHEN platform = 'github' THEN 'GitHub'
            ELSE INITCAP(platform)
        END,
        token_type = 'Bearer',
        auto_sync_enabled = true,
        error_count = 0,
        total_syncs = 0,
        total_items_synced = 0,
        sync_settings = '{}',
        features_enabled = '{}'
        WHERE provider_name IS NULL
    """)
    
    # Make provider_name non-nullable after setting defaults
    op.alter_column('integrations', 'provider_name', nullable=False)
    
    # Create oauth_states table
    op.create_table('oauth_states',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('state', sa.String(length=255), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('redirect_uri', sa.Text(), nullable=False),
        sa.Column('code_verifier', sa.String(length=255), nullable=True),
        sa.Column('scopes', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=True, default=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('state')
    )
    
    # Create indexes for oauth_states
    op.create_index('ix_oauth_states_state', 'oauth_states', ['state'])
    op.create_index('ix_oauth_states_user_id', 'oauth_states', ['user_id'])
    op.create_index('ix_oauth_states_platform', 'oauth_states', ['platform'])
    op.create_index('ix_oauth_states_expires_at', 'oauth_states', ['expires_at'])


def downgrade():
    """Downgrade database schema."""
    
    # Drop oauth_states table
    op.drop_index('ix_oauth_states_expires_at', table_name='oauth_states')
    op.drop_index('ix_oauth_states_platform', table_name='oauth_states')
    op.drop_index('ix_oauth_states_user_id', table_name='oauth_states')
    op.drop_index('ix_oauth_states_state', table_name='oauth_states')
    op.drop_table('oauth_states')
    
    # Add back old columns
    op.add_column('integrations', sa.Column('access_token', sa.Text(), nullable=True))
    op.add_column('integrations', sa.Column('refresh_token', sa.Text(), nullable=True))
    
    # Migrate data back
    op.execute("""
        UPDATE integrations 
        SET access_token = access_token_encrypted,
            refresh_token = refresh_token_encrypted
        WHERE access_token_encrypted IS NOT NULL OR refresh_token_encrypted IS NOT NULL
    """)
    
    # Drop new columns from integrations table
    op.drop_column('integrations', 'features_enabled')
    op.drop_column('integrations', 'sync_settings')
    op.drop_column('integrations', 'last_sync_duration_seconds')
    op.drop_column('integrations', 'total_items_synced')
    op.drop_column('integrations', 'total_syncs')
    op.drop_column('integrations', 'retry_after')
    op.drop_column('integrations', 'last_error_at')
    op.drop_column('integrations', 'error_count')
    op.drop_column('integrations', 'auto_sync_enabled')
    op.drop_column('integrations', 'last_successful_sync_at')
    op.drop_column('integrations', 'redirect_uri')
    op.drop_column('integrations', 'oauth_code_verifier')
    op.drop_column('integrations', 'oauth_state')
    op.drop_column('integrations', 'token_type')
    op.drop_column('integrations', 'refresh_token_encrypted')
    op.drop_column('integrations', 'access_token_encrypted')
    op.drop_column('integrations', 'provider_name') 