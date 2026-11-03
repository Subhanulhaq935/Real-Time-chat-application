"""add_advanced_chat_fields

Revision ID: d1ef893a7c12
Revises: c9ad469e8e48
Create Date: 2026-11-03 17:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1ef893a7c12'
down_revision: Union[str, Sequence[str], None] = 'c9ad469e8e48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add last_seen_at to users
    op.add_column('users', sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True))

    # Add advanced fields to messages
    op.add_column('messages', sa.Column('message_type', sa.String(length=20), server_default='text', nullable=False))
    op.add_column('messages', sa.Column('media_url', sa.Text(), nullable=True))
    op.add_column('messages', sa.Column('media_duration', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('reactions', sa.JSON(), nullable=True))
    op.add_column('messages', sa.Column('is_deleted_everyone', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('messages', sa.Column('deleted_by_users', sa.JSON(), nullable=True))
    op.add_column('messages', sa.Column('is_edited', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('messages', sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('messages', 'edited_at')
    op.drop_column('messages', 'is_edited')
    op.drop_column('messages', 'deleted_by_users')
    op.drop_column('messages', 'is_deleted_everyone')
    op.drop_column('messages', 'reactions')
    op.drop_column('messages', 'media_duration')
    op.drop_column('messages', 'media_url')
    op.drop_column('messages', 'message_type')
    op.drop_column('users', 'last_seen_at')

