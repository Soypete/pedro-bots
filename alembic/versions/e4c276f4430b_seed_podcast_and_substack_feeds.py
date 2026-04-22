"""seed podcast and substack feeds

Revision ID: e4c276f4430b
Revises: 071441bbc59f
Create Date: 2026-04-21 15:10:53.351870

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4c276f4430b'
down_revision: Union[str, Sequence[str], None] = '071441bbc59f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO socialwatch.feeds (url, feed_type, name, channel_id, active)
        VALUES 
            ('', 'youtube', 'Domesticating AI', 'UC9dlJM2TpRp68E7MIFVn5NA', true),
            ('https://soypetetech.substack.com/feed', 'substack', 'soyPete Tech', null, true),
            ('https://github.com/Soypete.atom', 'generic', 'Soypete GitHub', null, true)
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM socialwatch.feeds 
        WHERE name IN ('Domesticating AI', 'soyPete Tech')
    """)