"""Add empty local rule workflow tables; preserve all canonical data."""

import sqlalchemy as sa
from alembic import op

revision = "004_rule_workflow"
down_revision = "003_immutable_events"
branch_labels = None
depends_on = None
IMMUTABLE_TABLES = ("rule_versions", "detection_regression_runs", "rule_reviews")


def upgrade():
    op.create_table(
        "rule_versions",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("rule_id", sa.String(40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("parent_version", sa.Integer(), nullable=False),
        sa.Column("base_generation", sa.Integer(), nullable=False),
        sa.Column("base_ruleset_digest", sa.String(64), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("actor_label", sa.String(100), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("rule_id", "version", name="uq_rule_version_number"),
        sa.CheckConstraint(
            "version >= 2 AND parent_version >= 1 AND base_generation >= 0",
            name="ck_rule_version_numbers",
        ),
    )
    op.create_index("ix_rule_versions_rule_id", "rule_versions", ["rule_id"])
    op.create_table(
        "detection_regression_runs",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("revision_id", sa.String(80), sa.ForeignKey("rule_versions.id"), nullable=False),
        sa.Column("base_ruleset_digest", sa.String(64), nullable=False),
        sa.Column("proposed_ruleset_digest", sa.String(64), nullable=False),
        sa.Column("corpus_digest", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("actor_label", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_detection_regression_runs_revision_id", "detection_regression_runs", ["revision_id"]
    )
    op.create_table(
        "rule_reviews",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column(
            "revision_id",
            sa.String(80),
            sa.ForeignKey("rule_versions.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column(
            "regression_id",
            sa.String(80),
            sa.ForeignKey("detection_regression_runs.id"),
            nullable=True,
        ),
        sa.Column("actor_label", sa.String(100), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("decision IN ('approve', 'reject')", name="ck_rule_review_decision"),
    )
    op.create_table(
        "ruleset_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("active_versions", sa.JSON(), nullable=False),
        sa.CheckConstraint("id = 1 AND generation >= 0", name="ck_ruleset_singleton"),
    )
    # No baseline/singleton rows: public initialization must still recognize an empty DB.
    dialect = op.get_bind().dialect.name
    for table in IMMUTABLE_TABLES:
        if dialect == "postgresql":
            op.execute(
                f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION aegisgraph_reject_mutation()"
            )
        elif dialect == "sqlite":
            for action in ("UPDATE", "DELETE"):
                op.execute(
                    f"CREATE TRIGGER {table}_immutable_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'AegisGraph append-only record cannot be updated or deleted'); END"
                )


def downgrade():
    # Dropping these tables drops only their triggers; preserve the V1 shared PG function.
    op.drop_table("ruleset_state")
    for table in reversed(IMMUTABLE_TABLES):
        op.drop_table(table)
