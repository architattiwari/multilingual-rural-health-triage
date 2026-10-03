"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("triage_status", sa.String(30), nullable=False),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("triage_status IN ('information_gathering','emergency','complete')", name="ck_conv_status"),
    )
    op.create_index("ix_conversations_expires_at", "conversations", ["expires_at"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("language", sa.String(10)),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('patient','assistant')", name="ck_msg_role"),
        sa.CheckConstraint("source IN ('text','voice','system')", name="ck_msg_source"),
    )
    op.create_index("ix_messages_conversation", "conversation_messages", ["conversation_id", "id"])

    op.create_table(
        "clinical_observations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("concept", sa.String(60), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_observations_conversation", "clinical_observations", ["conversation_id", "id"])

    op.create_table(
        "triage_assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("rules_triggered", sa.JSON(), nullable=False),
        sa.Column("red_flags", sa.JSON(), nullable=False),
        sa.Column("information_used", sa.JSON(), nullable=False),
        sa.Column("engine_version", sa.String(20), nullable=False),
        sa.Column("rules_version", sa.String(20), nullable=False),
        sa.Column("is_final", sa.Boolean(), nullable=False),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("level IN ('emergency','urgent','non_urgent')", name="ck_assessment_level"),
    )
    op.create_index("ix_assessments_conversation", "triage_assessments", ["conversation_id", "created_at"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.String(36)),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("request_id", sa.String(32)),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_conversation_id", "audit_events", ["conversation_id"])
    op.create_index("ix_audit_type_created", "audit_events", ["event_type", "created_at"])


def downgrade() -> None:
    for table in ("audit_events", "triage_assessments", "clinical_observations", "conversation_messages", "conversations"):
        op.drop_table(table)
