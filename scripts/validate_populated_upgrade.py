"""Verify additive PostgreSQL upgrades from a populated V1 schema.

Use a new empty database whose name ends in _upgrade_validation. The script never
resets or drops a database. It retains the synthetic result for inspection.
"""

import hashlib
import json

from aegisgraph import models as m
from aegisgraph import services
from aegisgraph.config import ROOT, settings
from aegisgraph.db import engine
from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, inspect, select, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session


def snapshot(metadata: MetaData) -> str:
    with engine.connect() as connection:
        rows = {
            table.name: sorted(
                json.dumps(dict(row), sort_keys=True, default=str)
                for row in connection.execute(select(table)).mappings()
            )
            for table in metadata.sorted_tables
            if table.name != "alembic_version"
        }
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def main():
    assert not settings.public_demo, "Run the upgrade fixture in local deterministic mode."
    assert engine.dialect.name == "postgresql", "This check requires PostgreSQL."
    assert (engine.url.database or "").endswith("_upgrade_validation"), (
        "Use a dedicated database ending in _upgrade_validation."
    )
    assert not inspect(engine).get_table_names(), "Refusing a nonempty database."
    configuration = Config(str(ROOT / "alembic.ini"))
    command.upgrade(configuration, "003_immutable_events")
    legacy = MetaData()
    legacy.reflect(engine)
    with Session(engine) as db:
        services.seed_database(db)
        result = services.execute_evaluations(db)
        assert result["failed"] == 0
        services.create_note(db, "INC-fe8fa4b9508c", "Synthetic pre-upgrade analyst note.")
        # A populated report, note, audit and evaluation history must survive too.
        # Build a V1 report fixture directly: current report generation correctly
        # requires the new ledger schema, which does not exist before this upgrade.
        db.add(
            m.Report(
                id="RPT-UPGRADE-FIXTURE",
                incident_id="INC-fe8fa4b9508c",
                title="Synthetic pre-upgrade report",
                content="Preserved V1 report snapshot.",
                status="approved",
                approved_by="upgrade.fixture",
                approved_at=m.utcnow(),
            )
        )
        services.audit(
            db,
            "INC-fe8fa4b9508c",
            "report_approved",
            "RPT-UPGRADE-FIXTURE",
            after={"status": "approved"},
        )
        db.commit()
    before = snapshot(legacy)
    command.upgrade(configuration, "head")
    assert snapshot(legacy) == before, "Upgrade changed V1 data."
    current = MetaData()
    current.reflect(engine)
    added_tables = set(current.tables) - set(legacy.tables)
    with engine.connect() as connection:
        for name in added_tables:
            assert connection.execute(select(current.tables[name]).limit(1)).first() is None
    current_before = snapshot(current)
    command.upgrade(configuration, "head")
    assert snapshot(current) == current_before, "Repeated upgrade changed stored data."
    from aegisgraph.rule_workflow import (
        ProposalRequest,
        ReviewRequest,
        get_workbench,
        propose_revision,
        review_revision,
        run_regression,
    )

    with Session(engine) as db:
        baseline = get_workbench(db, "APP-002", public_demo=False)
        revision = propose_revision(
            db,
            "APP-002",
            ProposalRequest(
                parameters={"threshold": 1500},
                base_ruleset_digest=baseline["ruleset_digest"],
                base_generation=baseline["generation"],
                base_version=baseline["version"],
                reason="Validate the upgraded local workflow.",
            ),
            actor_label="upgrade.fixture",
            public_demo=False,
        )
        assert db.get(m.RuleVersion, revision["id"]) is not None
        run = run_regression(db, revision["id"], actor_label="upgrade.fixture", public_demo=False)
        review_revision(
            db,
            revision["id"],
            ReviewRequest(
                decision="reject",
                regression_id=run["id"],
                reason="Synthetic migration check; keep the shipped rules active.",
            ),
            actor_label="upgrade.fixture",
            public_demo=False,
        )
    # Database enforcement is tested through SQL, independently of ORM listeners.
    from aegisgraph.hypothesis_workflow import (
        ReviewHypothesisRequest,
        get_ledger,
        review_hypothesis,
    )

    with Session(engine) as db:
        ledger = get_ledger(db, "INC-fe8fa4b9508c", public_demo=False)
        review_hypothesis(
            db,
            "INC-fe8fa4b9508c",
            "account_compromise",
            ReviewHypothesisRequest(
                expected_version=0,
                context_digest=ledger["context_digest"],
                review_status="accepted",
                related_finding_ids=[],
                reason="Verify scoped human review after the additive migration.",
            ),
            actor_label="upgrade.fixture",
            public_demo=False,
        )
    for table in (
        "events",
        "audit_log",
        "rule_versions",
        "detection_regression_runs",
        "rule_reviews",
        "hypothesis_revisions",
    ):
        for operation in (f"UPDATE {table} SET id = id", f"DELETE FROM {table}"):
            with engine.connect() as connection:
                transaction = connection.begin()
                try:
                    connection.execute(text(operation))
                except DatabaseError:
                    pass
                else:
                    raise AssertionError(f"Append-only control absent for {table}")
                finally:
                    transaction.rollback()
    print(
        "Populated PostgreSQL upgrade passed: V1 canonical data, notes, reports, "
        "audit and evaluation history preserved; additive empty tables; idempotent "
        "upgrade; usable local rule and hypothesis workflows; SQL append-only controls retained."
    )


if __name__ == "__main__":
    main()
