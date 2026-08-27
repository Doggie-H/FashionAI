"""Add transactional outbox and idempotent consumer delivery ledger.

Revision ID: 20260826_01
Revises: 20260826_00
Create Date: 2026-08-26
"""

from alembic import op
import sqlalchemy as sa

revision = "20260826_01"
down_revision = "20260826_00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_outbox_events",
        sa.Column("event_id", sa.String(length=40), primary_key=True),
        sa.Column("dedupe_key", sa.String(length=192), nullable=False, unique=True),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=96), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False, server_default="1.0"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("status IN ('pending', 'processing', 'published', 'retry', 'dead_letter')", name="ck_workflow_outbox_status"),
    )
    op.create_index("ix_workflow_outbox_events_aggregate_type", "workflow_outbox_events", ["aggregate_type"])
    op.create_index("ix_workflow_outbox_events_aggregate_id", "workflow_outbox_events", ["aggregate_id"])
    op.create_index("ix_workflow_outbox_events_event_type", "workflow_outbox_events", ["event_type"])
    op.create_index("ix_workflow_outbox_events_correlation_id", "workflow_outbox_events", ["correlation_id"])
    op.create_index("ix_workflow_outbox_events_status", "workflow_outbox_events", ["status"])
    op.create_index("ix_workflow_outbox_events_available_at", "workflow_outbox_events", ["available_at"])
    op.create_index("ix_workflow_outbox_claim", "workflow_outbox_events", ["status", "available_at", "created_at"])

    op.create_table(
        "processed_event_deliveries",
        sa.Column("delivery_id", sa.String(length=40), primary_key=True),
        sa.Column("consumer_name", sa.String(length=96), nullable=False),
        sa.Column("event_id", sa.String(length=40), sa.ForeignKey("workflow_outbox_events.event_id"), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="processing"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("consumer_name", "event_id", name="uq_processed_event_delivery"),
        sa.CheckConstraint("status IN ('processing', 'completed', 'failed')", name="ck_processed_event_delivery_status"),
    )
    op.create_index("ix_processed_event_deliveries_consumer_name", "processed_event_deliveries", ["consumer_name"])
    op.create_index("ix_processed_event_deliveries_event_id", "processed_event_deliveries", ["event_id"])
    op.create_index("ix_processed_event_delivery_status", "processed_event_deliveries", ["consumer_name", "status", "created_at"])


def downgrade() -> None:
    op.drop_table("processed_event_deliveries")
    op.drop_table("workflow_outbox_events")
