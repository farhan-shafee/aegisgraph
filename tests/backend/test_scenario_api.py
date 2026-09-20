"""Scenario browsing exposes bounded descriptions, never evaluation answer keys."""

import hashlib
import importlib
import json

import pytest
from aegisgraph import config, main
from aegisgraph.db import Base, get_db, make_engine
from aegisgraph.services import seed_database
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

SCENARIO_IDS = {
    "atlas-compromise",
    "auth-pressure",
    "service-access",
    "sensitive-enumeration",
    "approved-admin",
    "bulk-automation",
    "isolated-anomaly",
    "mixed-context",
}
PUBLIC_FIELDS = {
    "id",
    "version",
    "title",
    "classification",
    "purpose",
    "theme",
    "event_count",
    "canonical_incident_id",
}
ORIGIN = "https://frontend.example"


@pytest.fixture(scope="module")
def scenario_database(tmp_path_factory):
    path = tmp_path_factory.mktemp("scenario-api") / "test.db"
    engine = make_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_database(db)
    yield engine
    engine.dispose()


@pytest.fixture(params=["local", "public_demo"])
def scenario_client(request, scenario_database, monkeypatch):
    # Public configuration remains PostgreSQL-only. A dependency override gives
    # these API tests isolated storage without permitting public SQLite settings.
    settings = config.Settings(
        app_mode=request.param,
        database_url="postgresql://demo:fixture-password@database.example/demo",
        allowed_origins=(ORIGIN,),
        allowed_hosts=("api.example",),
    )
    original_app, original_settings = main.app, main.settings
    monkeypatch.setattr(config, "settings", settings)
    importlib.reload(main)

    def override():
        with Session(scenario_database) as db:
            yield db

    main.app.dependency_overrides[get_db] = override
    try:
        with TestClient(main.app, base_url="https://api.example") as client:
            yield client, request.param
    finally:
        main.app.dependency_overrides.clear()
        main.app, main.settings = original_app, original_settings


def database_snapshot(engine):
    with Session(engine) as db:
        rows = {
            table.name: sorted(
                json.dumps(dict(row), sort_keys=True, default=str)
                for row in db.execute(select(table)).mappings()
            )
            for table in Base.metadata.sorted_tables
        }
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def assert_public_metadata(item):
    # An exact projection prevents additions such as expected rule matches,
    # evidence answer keys, supported claims, or raw ground truth leaking out.
    assert set(item) == PUBLIC_FIELDS
    assert item["id"] in SCENARIO_IDS
    assert isinstance(item["version"], str) and item["version"]
    for field in ("title", "classification", "purpose", "theme"):
        assert isinstance(item[field], str) and 0 < len(item[field]) <= 2000
    assert type(item["event_count"]) is int
    assert 0 < item["event_count"] <= 5000
    if item["id"] == "atlas-compromise":
        assert item["canonical_incident_id"] == "INC-fe8fa4b9508c"
        assert item["event_count"] == 4026
    else:
        assert item["canonical_incident_id"] is None


def test_scenario_catalog_is_stable_bounded_and_has_no_evaluation_answer_keys(
    scenario_client, scenario_database
):
    client, _ = scenario_client
    before = database_snapshot(scenario_database)
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"items"}
    assert len(payload["items"]) == len(SCENARIO_IDS)
    assert {item["id"] for item in payload["items"]} == SCENARIO_IDS
    for item in payload["items"]:
        assert_public_metadata(item)
    assert client.get("/api/scenarios").json() == payload
    assert len(response.content) < 32768
    assert database_snapshot(scenario_database) == before


def test_scenario_details_match_catalog_without_mutating_canonical_data(
    scenario_client, scenario_database
):
    client, _ = scenario_client
    before = database_snapshot(scenario_database)
    catalog = client.get("/api/scenarios")
    assert catalog.status_code == 200
    for item in catalog.json()["items"]:
        response = client.get(f"/api/scenarios/{item['id']}")
        assert response.status_code == 200
        assert response.json() == item
        assert_public_metadata(response.json())
    assert database_snapshot(scenario_database) == before


def test_unknown_scenario_has_no_fallback_or_private_error_detail(scenario_client):
    client, _ = scenario_client
    response = client.get("/api/scenarios/unknown-scenario")
    assert response.status_code == 404
    assert set(response.json()) == {"detail"}
    assert "unknown-scenario" not in response.text


def test_scenario_api_has_no_mutation_or_uploaded_telemetry_path(
    scenario_client, scenario_database
):
    client, mode = scenario_client
    before = database_snapshot(scenario_database)
    for method, path in (
        ("POST", "/api/scenarios"),
        ("PATCH", "/api/scenarios/atlas-compromise"),
        ("DELETE", "/api/scenarios/atlas-compromise"),
        ("POST", "/api/scenarios/atlas-compromise/events"),
        ("POST", "/api/scenarios/import"),
    ):
        response = client.request(
            method,
            path,
            headers={"Origin": ORIGIN},
            json={"events": [], "title": "Untrusted submitted scenario"},
        )
        if mode == "public_demo":
            assert response.status_code == 403, (method, path)
        else:
            assert response.status_code in {404, 405}, (method, path)
    assert database_snapshot(scenario_database) == before
