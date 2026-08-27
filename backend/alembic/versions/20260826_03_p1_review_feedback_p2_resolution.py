"""Add P1 feedback/review/evaluation and P2 try-on resolution persistence.

Revision ID: 20260826_03
Revises: 20260826_02
Create Date: 2026-08-26
"""

from alembic import op
import sqlalchemy as sa


revision = "20260826_03"
down_revision = "20260826_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("try_on_runs", sa.Column("resolution_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.alter_column("try_on_runs", "resolution_payload", server_default=None)

    op.create_table(
        "styling_session_feedback",
        sa.Column("feedback_id", sa.String(length=40), primary_key=True),
        sa.Column("session_id", sa.String(length=32), sa.ForeignKey("styling_sessions.session_id"), nullable=False),
        sa.Column("decision_run_id", sa.String(length=40), sa.ForeignKey("outfit_decision_runs.decision_run_id"), nullable=False),
        sa.Column("try_on_run_id", sa.String(length=40), sa.ForeignKey("try_on_runs.try_on_run_id"), nullable=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_outfit_id", sa.String(length=128), nullable=True),
        sa.Column("sentiment", sa.String(length=24), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("issue_type", sa.String(length=48), nullable=True),
        sa.Column("fit_concern", sa.String(length=48), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_styling_session_feedback_session_id", "styling_session_feedback", ["session_id"])
    op.create_index("ix_styling_session_feedback_decision_run_id", "styling_session_feedback", ["decision_run_id"])
    op.create_index("ix_styling_session_feedback_try_on_run_id", "styling_session_feedback", ["try_on_run_id"])
    op.create_index("ix_styling_session_feedback_owner_id", "styling_session_feedback", ["owner_id"])

    op.create_table(
        "workflow_review_tasks",
        sa.Column("task_id", sa.String(length=40), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=64), nullable=False),
        sa.Column("subject_revision_id", sa.String(length=64), nullable=True),
        sa.Column("review_type", sa.String(length=48), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("assignee_actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("checklist_version", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=True),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("tenant_id", "owner_id", "subject_type", "subject_id", "subject_revision_id", "review_type", "priority", "status", "assignee_actor_id", "due_at"):
        op.create_index(f"ix_workflow_review_tasks_{column}", "workflow_review_tasks", [column])

    op.create_table(
        "workflow_evaluation_labels",
        sa.Column("label_id", sa.String(length=40), primary_key=True),
        sa.Column("source_review_task_id", sa.String(length=40), sa.ForeignKey("workflow_review_tasks.task_id"), nullable=False, unique=True),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=64), nullable=False),
        sa.Column("label_type", sa.String(length=64), nullable=False),
        sa.Column("label_value", sa.JSON(), nullable=False),
        sa.Column("rubric_version", sa.String(length=64), nullable=False),
        sa.Column("reviewer_actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("subject_type", "subject_id", "label_type", "reviewer_actor_id"):
        op.create_index(f"ix_workflow_evaluation_labels_{column}", "workflow_evaluation_labels", [column])


def downgrade() -> None:
    for column in ("reviewer_actor_id", "label_type", "subject_id", "subject_type"):
        op.drop_index(f"ix_workflow_evaluation_labels_{column}", table_name="workflow_evaluation_labels")
    op.drop_table("workflow_evaluation_labels")

    for column in ("due_at", "assignee_actor_id", "status", "priority", "review_type", "subject_revision_id", "subject_id", "subject_type", "owner_id", "tenant_id"):
        op.drop_index(f"ix_workflow_review_tasks_{column}", table_name="workflow_review_tasks")
    op.drop_table("workflow_review_tasks")

    for column in ("owner_id", "try_on_run_id", "decision_run_id", "session_id"):
        op.drop_index(f"ix_styling_session_feedback_{column}", table_name="styling_session_feedback")
    op.drop_table("styling_session_feedback")
    op.drop_column("try_on_runs", "resolution_payload")
