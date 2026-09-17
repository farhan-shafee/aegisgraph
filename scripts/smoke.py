"""Exercise the configured, migrated and seeded API against its actual database.

No reset or writes are performed. AI/evaluation writes are covered by isolated
tests and the interactive demo. Use DATABASE_URL to select the database.
"""

from aegisgraph.main import app
from fastapi.testclient import TestClient


def main() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        health.raise_for_status()
        overview = client.get("/api/overview")
        overview.raise_for_status()
        counts = overview.json()["counts"]
        assert counts["events"] >= 4000, counts
        assert counts["incidents"] >= 1, counts
        events = client.get("/api/events", params={"limit": 10, "offset": 0})
        events.raise_for_status()
        assert len(events.json()["items"]) == 10
        assert events.json()["total"] == counts["events"]
        rules = client.get("/api/detections")
        rules.raise_for_status()
        assert len(rules.json()["items"]) == 10
        queue = client.get("/api/incidents")
        queue.raise_for_status()
        incident_id = queue.json()["items"][0]["id"]
        detail = client.get(f"/api/incidents/{incident_id}")
        detail.raise_for_status()
        case = detail.json()
        assert case["evidence"] and case["alerts"] and case["entities"]
        evidence_ids = {item["id"] for item in case["evidence"]}
        for relationship in case["relationships"]:
            assert set(relationship["evidence_ids"]).issubset(evidence_ids)
        assert client.get("/api/incidents/does-not-exist").status_code == 404
        assert client.get("/api/events", params={"limit": -1}).status_code == 422
        print(f"API/database smoke passed: {counts}; {len(evidence_ids)} case evidence items")


if __name__ == "__main__":
    main()
