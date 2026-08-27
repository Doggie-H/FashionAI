"""Add reviewer-approved 2D garment structural profile.

Revision ID: 20260827_06
Revises: 20260827_05
Create Date: 2026-08-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260827_06"
down_revision = "20260827_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("garment_asset_revisions", sa.Column("structural_profile", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("garment_asset_revisions", "structural_profile")
