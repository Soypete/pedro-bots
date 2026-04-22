"""create socialwatch schema and tables

Revision ID: 071441bbc59f
Revises: 
Create Date: 2026-04-21 15:05:39.451757

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '071441bbc59f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS socialwatch")
    
    op.create_table('feeds',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('feed_type', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('channel_id', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        schema='socialwatch',
    )
    
    op.create_table('content_items',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source_feed_id', sa.UUID(), sa.ForeignKey('socialwatch.feeds.id'), nullable=True),
        sa.Column('source_type', sa.Text(), nullable=False),
        sa.Column('added_by', sa.Text(), nullable=True),
        sa.Column('posted', sa.Boolean(), server_default='false'),
        sa.Column('posted_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        schema='socialwatch',
    )
    
    op.create_table('posted_content',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('content_item_id', sa.UUID(), sa.ForeignKey('socialwatch.content_items.id'), nullable=False),
        sa.Column('platform', sa.Text(), nullable=False),
        sa.Column('post_id', sa.Text(), nullable=True),
        sa.Column('post_url', sa.Text(), nullable=True),
        sa.Column('post_text', sa.Text(), nullable=True),
        sa.Column('posted_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        schema='socialwatch',
    )
    
    op.create_table('relevance_scores',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('content_item_id', sa.UUID(), sa.ForeignKey('socialwatch.content_items.id'), nullable=False),
        sa.Column('relevance_score', sa.Float(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('evaluated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        schema='socialwatch',
    )
    
    op.create_index('idx_sw_feeds_active', 'feeds', ['active'], schema='socialwatch')
    op.create_index('idx_sw_content_posted', 'content_items', ['posted'], schema='socialwatch')
    op.create_index('idx_sw_content_created', 'content_items', ['created_at'], schema='socialwatch', postgresql_using='btree')
    op.create_index('idx_sw_relevance_item', 'relevance_scores', ['content_item_id'], schema='socialwatch')
    op.create_index('idx_sw_posted_item', 'posted_content', ['content_item_id'], schema='socialwatch')


def downgrade() -> None:
    op.drop_index('idx_sw_posted_item', schema='socialwatch')
    op.drop_index('idx_sw_relevance_item', schema='socialwatch')
    op.drop_index('idx_sw_content_created', schema='socialwatch')
    op.drop_index('idx_sw_content_posted', schema='socialwatch')
    op.drop_index('idx_sw_feeds_active', schema='socialwatch')
    
    op.drop_table('relevance_scores', schema='socialwatch')
    op.drop_table('posted_content', schema='socialwatch')
    op.drop_table('content_items', schema='socialwatch')
    op.drop_table('feeds', schema='socialwatch')
    
    op.execute("DROP SCHEMA IF EXISTS socialwatch")