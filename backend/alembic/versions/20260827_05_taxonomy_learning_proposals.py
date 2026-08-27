"""Add governed taxonomy learning proposals derived from approved reviews.

Revision ID: 20260827_05
Revises: 20260826_04
Create Date: 2026-08-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260827_05"
down_revision = "20260826_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "taxonomy_learning_proposals",
        sa.Column("proposal_id", sa.String(length=40), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=True),
        sa.Column("dimension", sa.String(length=64), nullable=False),
        sa.Column("subject_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="proposed"),
        sa.Column("support_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("average_confidence", sa.JSON(), nullable=False),
        sa.Column("proposal_payload", sa.JSON(), nullable=False),
        sa.Column("source_review_task_ids", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "dimension", "subject_key", name="uq_taxonomy_learning_proposal_key"),
    )
    op.create_index("ix_taxonomy_learning_proposals_tenant_id", "taxonomy_learning_proposals", ["tenant_id"])
    op.create_index("ix_taxonomy_learning_proposals_dimension", "taxonomy_learning_proposals", ["dimension"])
    op.create_index("ix_taxonomy_learning_proposals_subject_key", "taxonomy_learning_proposals", ["subject_key"])
    op.create_index("ix_taxonomy_learning_proposals_status", "taxonomy_learning_proposals", ["status"])


def downgrade() -> None:
    op.drop_index("ix_taxonomy_learning_proposals_status", table_name="taxonomy_learning_proposals")
    op.drop_index("ix_taxonomy_learning_proposals_subject_key", table_name="taxonomy_learning_proposals")
    op.drop_index("ix_taxonomy_learning_proposals_dimension", table_name="taxonomy_learning_proposals")
    op.drop_index("ix_taxonomy_learning_proposals_tenant_id", table_name="taxonomy_learning_proposals")
    op.drop_table("taxonomy_learning_proposals")
