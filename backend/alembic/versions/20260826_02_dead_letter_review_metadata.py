"""Add admin review metadata to durable outbox events.

Revision ID: 20260826_02
Revises: 20260826_01
Create Date: 2026-08-26
"""

from alembic import op
import sqlalchemy as sa

revision = "20260826_02"
down_revision = "20260826_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workflow_outbox_events", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workflow_outbox_events", sa.Column("review_note", sa.Text(), nullable=True))
    op.add_column("workflow_outbox_events", sa.Column("reviewer_actor_id", sa.Integer(), nullable=True))
    op.create_index("ix_workflow_outbox_events_reviewer_actor_id", "workflow_outbox_events", ["reviewer_actor_id"])


def downgrade() -> None:
    op.drop_index("ix_workflow_outbox_events_reviewer_actor_id", table_name="workflow_outbox_events")
    op.drop_column("workflow_outbox_events", "reviewer_actor_id")
    op.drop_column("workflow_outbox_events", "review_note")
    op.drop_column("workflow_outbox_events", "reviewed_at")
