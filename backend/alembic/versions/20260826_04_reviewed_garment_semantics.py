"""Persist reviewer-approved semantic metadata for user-imported garments.

Revision ID: 20260826_04
Revises: 20260826_03
Create Date: 2026-08-26
"""

from alembic import op
import sqlalchemy as sa


revision = "20260826_04"
down_revision = "20260826_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("garment_asset_revisions", sa.Column("semantic_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("garment_asset_revisions", "semantic_metadata")
