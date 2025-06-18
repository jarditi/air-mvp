"""Add job results table for task monitoring

Revision ID: 005_add_job_results_table
Revises: 004_add_integration_status_tracking
Create Date: 2024-01-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_add_job_results_table'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    """Add job results table for comprehensive job monitoring and storage"""
    
    # Create job_results table
    op.create_table(
        'job_results',
        sa.Column('task_id', sa.String(255), primary_key=True),
        sa.Column('task_name', sa.String(255), nullable=False, index=True),
        sa.Column('status', sa.String(50), nullable=False, index=True),
        sa.Column('result_data', sa.LargeBinary, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('traceback', sa.Text, nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('execution_time', sa.Integer, nullable=True),  # Milliseconds
        sa.Column('retry_count', sa.Integer, default=0),
        sa.Column('worker_name', sa.String(255), nullable=True),
        sa.Column('args_data', sa.LargeBinary, nullable=True),
        sa.Column('kwargs_data', sa.LargeBinary, nullable=True),
        sa.Column('metadata_data', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), 
                 server_default=sa.text('CURRENT_TIMESTAMP'), index=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), 
                 server_default=sa.text('CURRENT_TIMESTAMP'),
                 onupdate=sa.text('CURRENT_TIMESTAMP'))
    )
    
    # Create indexes for better query performance
    op.create_index('idx_job_results_task_name_status', 'job_results', ['task_name', 'status'])
    op.create_index('idx_job_results_completed_at_status', 'job_results', ['completed_at', 'status'])
    op.create_index('idx_job_results_created_at', 'job_results', ['created_at'])


def downgrade():
    """Remove job results table"""
    
    # Drop indexes
    op.drop_index('idx_job_results_created_at', 'job_results')
    op.drop_index('idx_job_results_completed_at_status', 'job_results')
    op.drop_index('idx_job_results_task_name_status', 'job_results')
    
    # Drop table
    op.drop_table('job_results') 