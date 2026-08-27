"""Create legacy and Workflow Foundation baseline schema.

Revision ID: 20260826_00
Revises:
Create Date: 2026-08-26
"""

from alembic import op
import sqlalchemy as sa

revision = "20260826_00"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(), nullable=True, unique=True),
        sa.Column("email", sa.String(), nullable=True, unique=True),
        sa.Column("height_cm", sa.Float(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "wardrobe_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("color", sa.String(), nullable=True),
        sa.Column("image_url", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_wardrobe_items_id", "wardrobe_items", ["id"])
    op.create_index("ix_wardrobe_items_name", "wardrobe_items", ["name"])
    op.create_index("ix_wardrobe_items_category", "wardrobe_items", ["category"])

    op.create_table(
        "body_profile_revisions",
        sa.Column("profile_id", sa.String(length=32), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("measurements", sa.JSON(), nullable=False),
        sa.Column("body_contract", sa.JSON(), nullable=False),
        sa.Column("calibration_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supersedes_profile_id", sa.String(length=32), nullable=True),
    )
    op.create_index("ix_body_profile_revisions_owner_id", "body_profile_revisions", ["owner_id"])
    op.create_index("ix_body_profile_revisions_status", "body_profile_revisions", ["status"])

    op.create_table(
        "workflow_wardrobe_assets",
        sa.Column("asset_id", sa.String(length=32), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("active_revision_id", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workflow_wardrobe_assets_owner_id", "workflow_wardrobe_assets", ["owner_id"])
    op.create_index("ix_workflow_wardrobe_assets_category", "workflow_wardrobe_assets", ["category"])
    op.create_index("ix_workflow_wardrobe_assets_status", "workflow_wardrobe_assets", ["status"])

    op.create_table(
        "garment_asset_revisions",
        sa.Column("revision_id", sa.String(length=40), primary_key=True),
        sa.Column("asset_id", sa.String(length=32), sa.ForeignKey("workflow_wardrobe_assets.asset_id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("import_id", sa.String(length=32), nullable=True),
        sa.Column("canonical_garment_id", sa.String(length=128), nullable=True),
        sa.Column("manifest_snapshot", sa.JSON(), nullable=True),
        sa.Column("quality_summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_note", sa.Text(), nullable=True),
        sa.UniqueConstraint("asset_id", "revision", name="uq_garment_asset_revision"),
    )
    op.create_index("ix_garment_asset_revisions_asset_id", "garment_asset_revisions", ["asset_id"])
    op.create_index("ix_garment_asset_revisions_status", "garment_asset_revisions", ["status"])
    op.create_index("ix_garment_asset_revisions_import_id", "garment_asset_revisions", ["import_id"])

    op.create_table(
        "styling_sessions",
        sa.Column("session_id", sa.String(length=32), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body_profile_id", sa.String(length=32), sa.ForeignKey("body_profile_revisions.profile_id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("body_contract_snapshot", sa.JSON(), nullable=False),
        sa.Column("wardrobe_snapshot", sa.JSON(), nullable=False),
        sa.Column("selected_outfit_id", sa.String(length=128), nullable=True),
        sa.Column("active_decision_run_id", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_styling_sessions_owner_id", "styling_sessions", ["owner_id"])
    op.create_index("ix_styling_sessions_body_profile_id", "styling_sessions", ["body_profile_id"])
    op.create_index("ix_styling_sessions_status", "styling_sessions", ["status"])

    op.create_table(
        "outfit_decision_runs",
        sa.Column("decision_run_id", sa.String(length=40), primary_key=True),
        sa.Column("session_id", sa.String(length=32), sa.ForeignKey("styling_sessions.session_id"), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("catalog_version", sa.String(length=64), nullable=False),
        sa.Column("rule_version", sa.String(length=64), nullable=False),
        sa.Column("decision_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_outfit_decision_runs_session_id", "outfit_decision_runs", ["session_id"])
    op.create_index("ix_outfit_decision_runs_status", "outfit_decision_runs", ["status"])

    op.create_table(
        "try_on_runs",
        sa.Column("try_on_run_id", sa.String(length=40), primary_key=True),
        sa.Column("session_id", sa.String(length=32), sa.ForeignKey("styling_sessions.session_id"), nullable=False),
        sa.Column("decision_run_id", sa.String(length=40), sa.ForeignKey("outfit_decision_runs.decision_run_id"), nullable=False),
        sa.Column("selected_outfit_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("render_mode", sa.String(length=40), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_try_on_runs_session_id", "try_on_runs", ["session_id"])
    op.create_index("ix_try_on_runs_decision_run_id", "try_on_runs", ["decision_run_id"])
    op.create_index("ix_try_on_runs_status", "try_on_runs", ["status"])

    op.create_table(
        "workflow_audit_events",
        sa.Column("event_id", sa.String(length=40), primary_key=True),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=96), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("aggregate_type", "aggregate_id", "event_type", "actor_id", "correlation_id"):
        op.create_index(f"ix_workflow_audit_events_{column}", "workflow_audit_events", [column])

    op.create_table(
        "processed_workflow_commands",
        sa.Column("command_id", sa.String(length=40), primary_key=True),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("command_type", sa.String(length=96), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("actor_id", "command_type", "idempotency_key", name="uq_workflow_command_idempotency"),
    )
    op.create_index("ix_processed_workflow_commands_actor_id", "processed_workflow_commands", ["actor_id"])
    op.create_index("ix_processed_workflow_commands_correlation_id", "processed_workflow_commands", ["correlation_id"])


def downgrade() -> None:
    for table in (
        "processed_workflow_commands", "workflow_audit_events", "try_on_runs", "outfit_decision_runs",
        "styling_sessions", "garment_asset_revisions", "workflow_wardrobe_assets", "body_profile_revisions",
        "wardrobe_items", "users",
    ):
        op.drop_table(table)
