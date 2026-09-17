"""Independent regression checks for detection, case boundaries, and reviewed reports."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from aegisgraph import models as m
from aegisgraph import services
from aegisgraph.correlation import correlate
from aegisgraph.db import Base, make_engine
from aegisgraph.detection import Signal, evaluate, load_rules
from aegisgraph.generator import generate_events
from aegisgraph.schema import CanonicalEvent, FindingCreate
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

START = datetime(2026, 9, 15, 13, tzinfo=UTC)
TEMPLATE = generate_events(normal_count=75)[0].model_dump(mode="json")


def event(
    number,
    minutes,
    *,
    user="USR-REVIEW",
    novel=False,
    action="login",
    kind="authentication",
    outcome="success",
    session=None,
    attributes=None,
):
    data = deepcopy(TEMPLATE)
    data.update(
        event_id=f"EVT-REVIEW-{number}",
        timestamp=START + timedelta(minutes=minutes),
        event_type=kind,
        action=action,
        outcome=outcome,
        attributes=attributes or {},
    )
    data["actor"]["user_id"] = user
    data["network"].update(
        source_ip="203.0.113.3" if novel else "192.0.2.2",
        location="region-b" if novel else "region-a",
    )
    data["device"]["device_id"] = "DEV-NEW" if novel else "DEV-KNOWN"
    data["session"]["session_id"] = session or ("SES-NEW" if novel else "SES-KNOWN")
    return CanonicalEvent.model_validate(data)


def rule(kind):
    return deepcopy(next(rule for rule in load_rules() if rule["kind"] == kind))


@pytest.mark.parametrize(
    "threshold,baseline_count,should_match", [(5, 3, False), (1, 1, True), (3, 3, True)]
)
def test_configured_novelty_baseline_controls_matching(threshold, baseline_count, should_match):
    configured = rule("unseen_auth")
    configured["threshold"] = threshold
    rows = [event(i, i) for i in range(baseline_count)] + [event(90, 10, novel=True)]
    assert bool(evaluate(rows, [configured])) is should_match


@pytest.mark.parametrize(
    "minutes,session,expected",
    [
        (15, "SES-NEW", True),
        (15.0001, "SES-NEW", False),
        (15, "SES-OTHER", False),
        (10, "SES-NEW", False),
    ],
)
def test_mfa_sequence_requires_same_session_and_exact_time_window(minutes, session, expected):
    rows = [event(i, i) for i in range(3)]
    rows += [
        event(10, 10, novel=True),
        event(11, minutes, novel=True, action="mfa_accept", kind="mfa", session=session),
    ]
    signals = evaluate(rows, [rule("unseen_auth"), rule("mfa_after_auth")])
    assert any(signal.rule_id == "MFA-001" for signal in signals) is expected


def test_novelty_threshold_controls_dependent_sequence():
    baseline = rule("unseen_auth")
    baseline["threshold"] = 5
    rows = [event(i, i) for i in range(3)] + [
        event(10, 10, novel=True),
        event(
            11,
            11,
            novel=True,
            action="role_assign",
            kind="privilege_change",
            attributes={"new_role": "platform_admin"},
        ),
    ]
    assert evaluate(rows, [baseline, rule("privilege_after_auth")]) == []


def test_failed_login_threshold_and_window():
    configured = rule("failed_logins")
    configured.update(threshold=3, window_minutes=5)
    assert (
        len(
            evaluate(
                [
                    event(1, 0, outcome="failure"),
                    event(2, 2, outcome="failure"),
                    event(3, 5, outcome="failure"),
                ],
                [configured],
            )
        )
        == 1
    )
    assert not evaluate(
        [
            event(1, 0, outcome="failure"),
            event(2, 2, outcome="failure"),
            event(3, 5.01, outcome="failure"),
        ],
        [configured],
    )


def signal(number, rule_id, minutes, user="USR-REVIEW", stamp=None):
    return Signal(
        f"ALT-REVIEW-{number}",
        rule_id,
        "Review signal",
        "medium",
        "Synthetic test",
        stamp or (START + timedelta(minutes=minutes)).isoformat(),
        user,
        (f"EVT-REVIEW-{number}",),
    )


def test_unrelated_principals_and_distant_clusters_do_not_merge():
    assert not correlate(
        [
            signal(1, "AUTH-002", 0),
            signal(2, "IAM-001", 10),
            signal(3, "APP-001", 20, user="USR-OTHER"),
        ],
        [],
    )
    assert not correlate(
        [signal(1, "AUTH-002", 0), signal(2, "IAM-001", 20), signal(3, "APP-001", 30.01)], []
    )


def test_correlation_window_is_inclusive_and_selects_only_same_principal_context():
    signals = [signal(1, "AUTH-002", 0), signal(2, "IAM-001", 20), signal(3, "APP-001", 30)]
    rows = [
        event(1, 0),
        event(2, 20),
        event(3, 30),
        event(4, 10, user="USR-OTHER"),
        event(5, -6),
        event(6, 31),
    ]
    cases = correlate(signals, rows)
    assert len(cases) == 1
    assert set(cases[0].event_ids) == {"EVT-REVIEW-1", "EVT-REVIEW-2", "EVT-REVIEW-3"}


def test_correlation_sorts_actual_instants_across_timezone_offsets():
    signals = [
        signal(1, "AUTH-002", 0, stamp="2026-09-15T12:00:00+02:00"),
        signal(2, "IAM-001", 20, stamp="2026-09-15T10:20:00+00:00"),
        signal(3, "APP-001", 31, stamp="2026-09-15T10:31:00+00:00"),
    ]
    assert not correlate(signals, [])


def test_generic_cluster_does_not_invent_privilege_or_resource_activity():
    cases = correlate(
        [signal(1, "AUTH-001", 0), signal(2, "AUTH-003", 5), signal(3, "API-001", 10)], []
    )
    assert len(cases) == 1
    assert "privileged access" not in cases[0].summary
    assert "account-resource activity" not in cases[0].summary
    assert "compromise" not in cases[0].title


@pytest.fixture
def db():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        for number in [1, 2]:
            row = event(number, number, user=f"USR-CASE-{number}")
            session.add(
                m.SecurityEvent(
                    id=row.event_id,
                    timestamp=row.timestamp,
                    source=row.source,
                    event_type=row.event_type,
                    user_id=row.actor.user_id,
                    session_id=row.session.session_id,
                    payload=row.model_dump(mode="json"),
                )
            )
            session.add(
                m.Incident(
                    id=f"INC-REVIEW-{number}",
                    title=f"Synthetic review case {number}",
                    summary=f"Case {number} isolated summary",
                    severity="medium",
                )
            )
        session.flush()
        for number in [1, 2]:
            session.add(
                m.Evidence(
                    id=f"EVD-REVIEW-{number}",
                    incident_id=f"INC-REVIEW-{number}",
                    event_id=f"EVT-REVIEW-{number}",
                )
            )
        session.commit()
        yield session
    engine.dispose()


def test_foreign_evidence_cannot_be_patched_or_cited(db):
    with pytest.raises(HTTPException) as denied:
        services.patch_evidence(db, "INC-REVIEW-1", "EVD-REVIEW-2", {"relevance": "benign"})
    assert denied.value.status_code == 404
    with pytest.raises(HTTPException) as denied:
        services.create_finding(
            db,
            "INC-REVIEW-1",
            FindingCreate(
                title="Review", narrative="Foreign citation", evidence_ids=["EVD-REVIEW-2"]
            ),
        )
    assert denied.value.status_code == 422
    assert db.get(m.Evidence, "EVD-REVIEW-2").relevance == "unreviewed"
    assert db.scalar(select(func.count()).select_from(m.Finding)) == 0


def test_foreign_finding_cannot_be_approved_or_enter_report(db):
    finding = services.create_finding(
        db,
        "INC-REVIEW-2",
        FindingCreate(
            title="FOREIGN-FINDING-CANARY",
            narrative="FOREIGN-NARRATIVE-CANARY",
            evidence_ids=["EVD-REVIEW-2"],
            approved=True,
        ),
    )
    with pytest.raises(HTTPException) as denied:
        services.approve_finding(db, "INC-REVIEW-1", finding["id"], True)
    assert denied.value.status_code == 404
    report = services.generate_report(db, "INC-REVIEW-1")
    assert "FOREIGN" not in report["content"]
    assert "EVD-REVIEW-2" not in report["content"]
    assert "USR-CASE-2" not in report["content"]


def test_unapproved_findings_are_not_reported_as_technical_findings(db):
    finding = services.create_finding(
        db,
        "INC-REVIEW-1",
        FindingCreate(
            title="UNREVIEWED-CANARY",
            narrative="Needs human review",
            evidence_ids=["EVD-REVIEW-1"],
            ai_assisted=True,
        ),
    )
    assert "UNREVIEWED-CANARY" not in services.generate_report(db, "INC-REVIEW-1")["content"]
    services.approve_finding(db, "INC-REVIEW-1", finding["id"], True)
    assert "UNREVIEWED-CANARY" in services.generate_report(db, "INC-REVIEW-1")["content"]


@pytest.mark.parametrize("mutation", ["evidence", "note", "status", "finding"])
def test_case_changes_invalidate_report_clear_approval_and_audit(db, mutation):
    services.generate_report(db, "INC-REVIEW-1")
    approved = services.approve_report(db, "INC-REVIEW-1")
    assert approved["approved_at"] and approved["approved_by"]
    if mutation == "evidence":
        services.patch_evidence(db, "INC-REVIEW-1", "EVD-REVIEW-1", {"relevance": "benign"})
    elif mutation == "note":
        services.create_note(db, "INC-REVIEW-1", "Additional investigation context")
    elif mutation == "status":
        services.patch_incident(db, "INC-REVIEW-1", {"status": "investigating"})
    else:
        services.create_finding(
            db,
            "INC-REVIEW-1",
            FindingCreate(title="Review", narrative="Current case", evidence_ids=["EVD-REVIEW-1"]),
        )
    report = services.report_json(services.get_report(db, "INC-REVIEW-1"))
    assert report["status"] == "stale"
    assert report["approved_at"] is None and report["approved_by"] is None
    with pytest.raises(HTTPException) as blocked:
        services.approve_report(db, "INC-REVIEW-1")
    assert blocked.value.status_code == 409
    audit = db.scalar(select(m.Audit).where(m.Audit.action == "report_invalidated"))
    assert audit.before == {"status": "approved"}
    assert audit.after == {"status": "stale"}
    fresh = services.generate_report(db, "INC-REVIEW-1")
    assert fresh["status"] == "draft" and fresh["review_required"]
    assert services.approve_report(db, "INC-REVIEW-1")["status"] == "approved"
