"""Clean PostgreSQL public-mode integration check; refuses an existing database schema.

Use a dedicated empty database with APP_MODE=public_demo. No external model calls.
The seeded database is retained for the public browser suite.
"""

import hashlib
import json

from aegisgraph import deployment
from aegisgraph.config import settings
from aegisgraph.db import Base, engine
from aegisgraph.main import app
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session


def snapshot() -> str:
    with Session(engine) as db:
        rows = {
            table.name: sorted(
                json.dumps(dict(row), sort_keys=True, default=str)
                for row in db.execute(select(table)).mappings()
            )
            for table in Base.metadata.sorted_tables
        }
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def main():
    deployment.require_public_mode()
    assert not inspect(engine).get_table_names(), "Use a new empty PostgreSQL validation database."
    assert deployment.initialize_public()["status"] == "empty"
    assert deployment.initialize_public(seed=True)["ready"]
    before = snapshot()
    assert deployment.initialize_public(seed=True)["action"] == "unchanged"
    assert deployment.initialize_public()["action"] == "unchanged"
    assert snapshot() == before, "Initialization changed an existing dataset."
    host = settings.allowed_hosts[0]
    incident = deployment.FLAGSHIP_ID
    with TestClient(app, base_url=f"https://{host}") as client:
        assert client.get("/ready").status_code == 200
        assert client.get("/api/runtime").json()["app_mode"] == "public_demo"
        for path in ("overview", "events", "detections", "alerts", "incidents", "evaluations"):
            assert client.get(f"/api/{path}").status_code == 200, path
        detail = client.get(f"/api/incidents/{incident}").json()
        assert len(detail["evidence"]) == 26
        for question in ("What most likely happened?", "What malware family was used?"):
            response = client.post(
                f"/api/incidents/{incident}/analysis",
                json={"question": question},
                headers={"Origin": settings.allowed_origins[0]},
            )
            assert response.status_code == 200, response.status_code
            assert response.json()["provider"] == "deterministic"
            if "malware" in question:
                assert response.json()["status"] == "insufficient_evidence"
        for method, path in (
            ("PATCH", f"/api/incidents/{incident}"),
            ("PATCH", f"/api/incidents/{incident}/evidence/{detail['evidence'][0]['id']}"),
            ("POST", f"/api/incidents/{incident}/findings"),
            ("POST", f"/api/incidents/{incident}/notes"),
            ("POST", f"/api/incidents/{incident}/report"),
            ("POST", f"/api/incidents/{incident}/report/approve"),
            ("POST", "/api/evaluations/run"),
            ("POST", "/api/demo-reset"),
            ("DELETE", "/api/detections"),
        ):
            assert client.request(method, path, json={}).status_code == 403, path
    assert snapshot() == before, "Public requests persisted a change."
    print(
        "Public PostgreSQL validation passed: clean migrations, explicit seed, unchanged reinitialization,"
    )
    print(
        "read routes, two deterministic questions, mutation denials, and identical database snapshot."
    )


if __name__ == "__main__":
    main()
