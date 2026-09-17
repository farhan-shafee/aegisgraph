"""Enforce event and audit immutability at the database boundary."""

from alembic import op

revision = "003_immutable_events"
down_revision = "cff4868e0db7"
branch_labels = None
depends_on = None


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("""CREATE FUNCTION aegisgraph_reject_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'AegisGraph append-only record cannot be updated or deleted'; END;
        $$ LANGUAGE plpgsql""")
        for table in ("events", "audit_log"):
            op.execute(
                f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION aegisgraph_reject_mutation()"
            )
    elif dialect == "sqlite":
        for table in ("events", "audit_log"):
            for action in ("UPDATE", "DELETE"):
                op.execute(
                    f"CREATE TRIGGER {table}_immutable_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'AegisGraph append-only record cannot be updated or deleted'); END"
                )


def downgrade():
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        for table in ("events", "audit_log"):
            op.execute(f"DROP TRIGGER {table}_immutable ON {table}")
        op.execute("DROP FUNCTION aegisgraph_reject_mutation()")
    elif dialect == "sqlite":
        for table in ("events", "audit_log"):
            for action in ("update", "delete"):
                op.execute(f"DROP TRIGGER {table}_immutable_{action}")
