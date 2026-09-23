"""Add empty hypothesis review state and immutable revision history."""

import sqlalchemy as sa
from alembic import op

revision = "005_hypothesis_workflow"
down_revision = "004_rule_workflow"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hypothesis_states",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("incident_id", sa.String(80), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("kind", sa.String(60), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("incident_id", "kind", name="uq_hypothesis_scope_kind"),
        sa.CheckConstraint(
            "current_version >= 1 AND current_version <= 20", name="ck_hypothesis_state_version"
        ),
    )
    op.create_index("ix_hypothesis_states_incident_id", "hypothesis_states", ["incident_id"])
    op.create_table(
        "hypothesis_revisions",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("state_id", sa.String(80), sa.ForeignKey("hypothesis_states.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("context_digest", sa.String(64), nullable=False),
        sa.Column("review_status", sa.String(20), nullable=False),
        sa.Column("related_finding_ids", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("actor_label", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("state_id", "version", name="uq_hypothesis_revision_version"),
        sa.CheckConstraint("version >= 1 AND version <= 20", name="ck_hypothesis_revision_version"),
        sa.CheckConstraint(
            "review_status IN ('open', 'accepted', 'rejected')", name="ck_hypothesis_review_status"
        ),
    )
    op.create_index("ix_hypothesis_revisions_state_id", "hypothesis_revisions", ["state_id"])
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            "CREATE TRIGGER hypothesis_revisions_immutable BEFORE UPDATE OR DELETE ON hypothesis_revisions FOR EACH ROW EXECUTE FUNCTION aegisgraph_reject_mutation()"
        )
    elif dialect == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER hypothesis_revisions_immutable_{action.lower()} BEFORE {action} ON hypothesis_revisions BEGIN SELECT RAISE(ABORT, 'AegisGraph append-only record cannot be updated or deleted'); END"
            )


def downgrade():
    op.drop_table("hypothesis_revisions")
    op.drop_table("hypothesis_states")
