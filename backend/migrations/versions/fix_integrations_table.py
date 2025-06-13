"""fix integrations table structure

Revision ID: fix_integrations_v1
Revises: oauth_token_storage_v1
Create Date: 2024-01-15 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'fix_integrations_v1'
down_revision = 'oauth_token_storage_v1'
branch_labels = None
depends_on = None


def upgrade():
    """Fix integrations table structure."""
    
    # Add new columns to integrations table
    op.add_column('integrations', sa.Column('provider_name', sa.String(length=50), nullable=True))
    op.add_column('integrations', sa.Column('access_token_encrypted', sa.Text(), nullable=True))
    op.add_column('integrations', sa.Column('refresh_token_encrypted', sa.Text(), nullable=True))
    op.add_column('integrations', sa.Column('token_type', sa.String(length=20), nullable=True, server_default='Bearer'))
    op.add_column('integrations', sa.Column('oauth_state', sa.String(length=255), nullable=True))
    op.add_column('integrations', sa.Column('oauth_code_verifier', sa.String(length=255), nullable=True))
    op.add_column('integrations', sa.Column('redirect_uri', sa.Text(), nullable=True))
    op.add_column('integrations', sa.Column('last_successful_sync_at', sa.DateTime(), nullable=True))
    op.add_column('integrations', sa.Column('auto_sync_enabled', sa.Boolean(), nullable=True, server_default='true'))
    op.add_column('integrations', sa.Column('error_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('integrations', sa.Column('last_error_at', sa.DateTime(), nullable=True))
    op.add_column('integrations', sa.Column('retry_after', sa.DateTime(), nullable=True))
    op.add_column('integrations', sa.Column('total_syncs', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('integrations', sa.Column('total_items_synced', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('integrations', sa.Column('last_sync_duration_seconds', sa.Integer(), nullable=True))
    op.add_column('integrations', sa.Column('sync_settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'))
    op.add_column('integrations', sa.Column('features_enabled', postgresql.ARRAY(sa.Text()), nullable=True, server_default='{}'))
    
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
    
    # Copy existing token data to encrypted columns (they will be encrypted at application level)
    op.execute("""
        UPDATE integrations 
        SET access_token_encrypted = access_token,
            refresh_token_encrypted = refresh_token
        WHERE access_token IS NOT NULL OR refresh_token IS NOT NULL
    """)
    
    # Make provider_name non-nullable after setting defaults
    op.alter_column('integrations', 'provider_name', nullable=False)
    
    # Drop old token columns
    op.drop_column('integrations', 'access_token')
    op.drop_column('integrations', 'refresh_token')


def downgrade():
    """Downgrade integrations table structure."""
    
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