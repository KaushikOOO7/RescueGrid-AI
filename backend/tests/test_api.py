from fastapi.testclient import TestClient
import pytest

from app.database import Base, engine, init_db
from app.main import app
from app.database import SessionLocal
from app.models import CoverageRecord, Incident, utcnow
from app.seed import seed_demo_data
from sqlalchemy import select
from datetime import timedelta


@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    init_db()
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


def test_health_and_incident_persistence(client):
    assert client.get("/api/health").status_code == 200
    response = client.post("/api/incidents", json={
        "report_text": "Floodwater is rising near Kestrel Bridge; four residents are trapped and need a rescue boat.",
        "source_type": "sms", "source_name": "Synthetic test",
    })
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["urgency_score"] > 0
    incident_id = created["id"]
    fetched = client.get(f"/api/incidents/{incident_id}")
    assert fetched.status_code == 200
    assert fetched.json()["original_reports"][0]["original_text"].startswith("Floodwater")
    assert client.get("/api/incidents").json()["total"] == 1


def test_dashboard_and_analytics_metrics_follow_saved_incident_data(client):
    client.post("/api/incidents", json={
        "report_text": "Floodwater rising; residents are trapped and need help.",
        "threat_level": "immediate", "time_criticality": 4, "people_affected": 7,
    })
    dashboard = client.get("/api/dashboard").json()
    analytics = client.get("/api/analytics").json()
    assert dashboard["active_incidents"] == 1
    assert dashboard["high_urgency_incidents"] == 1
    assert sum(item["count"] for item in analytics["urgency_distribution"]) == 1
    assert analytics["disaster_type_distribution"][0]["label"] == "Flood"


def test_input_validation_and_uncertain_location_are_safe(client):
    invalid_coords = client.post("/api/incidents", json={
        "report_text": "Earthquake damage report from a simulated test.",
        "latitude": 13.0, "longitude": 77.0, "location_precision": "unknown",
    })
    assert invalid_coords.status_code == 422
    created = client.post("/api/incidents", json={
        "report_text": "A wall collapsed somewhere after earthquake shaking; people need shelter.",
    })
    assert created.status_code == 201
    assert created.json()["latitude"] is None
    assert created.json()["longitude"] is None
    assert created.json()["location_precision"] == "unresolved"


def test_patch_rejects_half_coordinate_pair(client):
    incident = client.post("/api/incidents", json={"report_text": "An earthquake report from an unknown location."}).json()
    response = client.patch(f"/api/incidents/{incident['id']}", json={"latitude": 13.0})
    assert response.status_code == 422


def test_priority_override_requires_reason_and_is_audited(client):
    incident = client.post("/api/incidents", json={"report_text": "A storm damaged a roof and assistance is needed."}).json()
    bad = client.post(f"/api/incidents/{incident['id']}/priority", json={"priority": 80, "reason": "no"})
    assert bad.status_code == 422
    response = client.post(f"/api/incidents/{incident['id']}/priority", json={
        "priority": 82, "reason": "Coordinator elevated pending a field check.", "coordinator": "Test lead",
    })
    assert response.status_code == 200
    assert response.json()["priority_score"] == 82
    assert response.json()["urgency_score"] != 82 or response.json()["human_priority_override"] == 82
    audit = client.get("/api/audit-log", params={"incident_id": incident["id"]}).json()
    assert any(item["action"] == "priority_overridden" for item in audit["items"])
    detail = client.get(f"/api/incidents/{incident['id']}").json()
    assert any(item["kind"] == "priority" for item in detail["history"])


def test_resource_recommendation_does_not_invent_inventory(client):
    incident = client.post("/api/incidents", json={
        "report_text": "Flood report requests a rescue boat.",
        "needs": ["rescue boat"],
    }).json()
    detail = client.get(f"/api/incidents/{incident['id']}").json()
    recommendation = detail["resource_recommendations"][0]
    assert recommendation["resource_type_to_consider"] == "rescue boat"
    assert recommendation["availability"].startswith("Unknown")
    assert recommendation["approval_required"] is True


def test_verify_resolve_and_notes_create_history(client):
    incident = client.post("/api/incidents", json={"report_text": "Earthquake shaking reported; location unknown."}).json()
    iid = incident["id"]
    verified = client.post(f"/api/incidents/{iid}/verify", json={"action": "verified", "coordinator": "A. Reviewer", "note": "Checked simulated field channel."})
    assert verified.status_code == 200
    assert verified.json()["status"] == "verified"
    note = client.post(f"/api/incidents/{iid}/notes", json={"note": "Follow up with local liaison.", "coordinator": "A. Reviewer"})
    assert note.status_code == 201
    resolved = client.post(f"/api/incidents/{iid}/resolve", json={"reason": "Synthetic exercise closed by coordinator."})
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert len(resolved.json()["verification_history"]) == 1
    assert any(item["note"] == "Follow up with local liaison." for item in resolved.json()["notes"])


def test_csv_import_validation_and_duplicates_never_auto_merge(client):
    csv_one = "text,source_type,source_name\n\"Floodwater rising near Kestrel Bridge; four residents are trapped and need a rescue boat.\",sms,Channel A\n"
    first = client.post("/api/reports/import", content=csv_one, headers={"content-type": "text/csv"})
    assert first.status_code == 201, first.text
    first_id = first.json()["items"][0]["id"]
    csv_two = "text,source_type,source_name\n\"Four people trapped near Kestrel Bridge as floodwater continues rising; boat rescue requested.\",volunteer,Channel B\n"
    preview = client.post("/api/reports/preview-csv", content=csv_two, headers={"content-type": "text/csv"})
    assert preview.status_code == 200
    assert client.get("/api/incidents").json()["total"] == 1  # preview is non-persistent
    second = client.post("/api/reports/import", content=csv_two, headers={"content-type": "text/csv"})
    assert second.status_code == 201, second.text
    assert second.json()["possible_duplicates"]
    assert client.get("/api/incidents").json()["total"] == 2
    candidate_id = second.json()["items"][0]["id"]
    detail = client.get(f"/api/incidents/{candidate_id}").json()
    candidate_report_id = detail["original_reports"][0]["id"]
    merged = client.post(f"/api/reports/{candidate_report_id}/confirm-duplicate", json={
        "target_incident_id": first_id, "coordinator": "Test lead", "note": "Same simulated report event.",
    })
    assert merged.status_code == 200, merged.text
    assert merged.json()["merged"] is True
    assert merged.json()["preserved_report_count"] == 2
    assert client.get("/api/incidents").json()["total"] == 2
    archived = client.get(f"/api/incidents/{candidate_id}").json()
    assert archived["status"] == "merged"


def test_coordinator_can_mark_duplicate_candidates_separate(client):
    text = "Earthquake shaking damaged the west wall at Pineglass School; medical help requested."
    first = client.post("/api/incidents", json={"report_text": text, "source_name": "Test source A"}).json()
    second = client.post("/api/incidents", json={"report_text": text + " New message.", "source_name": "Test source B"}).json()
    assert second["new_duplicate_candidates"]
    report_id = second["original_reports"][0]["id"]
    result = client.post(f"/api/reports/{report_id}/mark-separate", json={
        "target_incident_id": first["id"], "coordinator": "Reviewer", "note": "Separate exercise reports.",
    })
    assert result.status_code == 200
    assert result.json()["status"] == "separate"
    assert client.get("/api/incidents").json()["total"] == 2


def test_csv_rejects_missing_text_column_and_invalid_row(client):
    no_text = client.post("/api/reports/import", content="source,location\nsms,Nowhere\n", headers={"content-type": "text/csv"})
    assert no_text.status_code == 422
    invalid = client.post("/api/reports/import", content="text,latitude,longitude\n\"Some emergency report text\",not-a-number,10\n", headers={"content-type": "text/csv"})
    assert invalid.status_code == 422


def test_coverage_gaps_endpoint_reports_info_limits(client):
    with SessionLocal() as db:
        db.add(CoverageRecord(area_name="Synthetic remote cell", latitude=13.4, longitude=77.7,
                              hazard_exposure="high", last_confirmed_at=utcnow() - timedelta(hours=24),
                              connectivity_limited=True, access_limited=True, synthetic=True))
        db.commit()
    result = client.get("/api/coverage-gaps")
    assert result.status_code == 200
    assert result.json()["flagged_count"] == 1
    assert result.json()["areas"][0]["synthetic"] is True
    assert "not a confirmed incident" in result.json()["note"]


def test_demo_reset_retains_untagged_user_records(client):
    with SessionLocal() as db:
        db.add(Incident(title="User-owned record", disaster_type="other", status="unverified"))
        db.commit()
        assert seed_demo_data(db) == 5
        assert seed_demo_data(db, reset_demo=True) == 5
        user_rows = db.scalars(select(Incident).where(Incident.demo_key.is_(None))).all()
        demo_rows = db.scalars(select(Incident).where(Incident.demo_key.is_not(None))).all()
        assert len(user_rows) == 1 and user_rows[0].title == "User-owned record"
        assert len(demo_rows) == 5


def test_not_found_and_invalid_sort_errors(client):
    assert client.get("/api/incidents/9999").status_code == 404
    assert client.get("/api/incidents", params={"sort_by": "made_up"}).status_code == 422


def test_resource_inventory_and_allocation_validation(client):
    # 1. Create a resource
    res_resp = client.post("/api/resources", json={
        "resource_type": "rescue boat",
        "area_name": "Riverside Zone",
        "quantity": 5,
        "availability_status": "available",
        "updated_by": "Logistics Lead",
    })
    assert res_resp.status_code == 201
    resource = res_resp.json()
    assert resource["quantity"] == 5
    assert resource["allocated_quantity"] == 0
    assert resource["available_quantity"] == 5

    # 2. Create an incident
    inc_resp = client.post("/api/incidents", json={
        "report_text": "Flooding near Riverside Zone; 10 people stranded needing boats.",
        "location_name": "Riverside Zone",
        "needs": ["rescue boat"],
    })
    incident_id = inc_resp.json()["id"]

    # 3. Over-allocation should fail with 422
    over_alloc = client.post("/api/resources/allocate", json={
        "incident_id": incident_id,
        "resource_id": resource["id"],
        "allocated_quantity": 10,
        "coordinator": "Lead Coordinator",
    })
    assert over_alloc.status_code == 422
    assert "exceeds available quantity" in over_alloc.json()["detail"]

    # 4. Valid allocation succeeds
    valid_alloc = client.post("/api/resources/allocate", json={
        "incident_id": incident_id,
        "resource_id": resource["id"],
        "allocated_quantity": 3,
        "coordinator": "Lead Coordinator",
        "note": "Dispatching 3 boats for rescue operation.",
    })
    assert valid_alloc.status_code == 201
    alloc_id = valid_alloc.json()["id"]

    # Verify inventory is updated
    updated_res = client.get("/api/resources").json()
    matched = next(r for r in updated_res if r["id"] == resource["id"])
    assert matched["allocated_quantity"] == 3
    assert matched["available_quantity"] == 2

    # Verify incident detail shows allocation
    inc_detail = client.get(f"/api/incidents/{incident_id}").json()
    assert len(inc_detail["allocations"]) == 1
    assert inc_detail["allocations"][0]["allocated_quantity"] == 3

    # 5. Cannot reduce total quantity below current allocated quantity
    reduce_fail = client.patch(f"/api/resources/{resource['id']}", json={"quantity": 2})
    assert reduce_fail.status_code == 422

    # 6. Release allocation restores inventory
    release_resp = client.delete(f"/api/resources/allocate/{alloc_id}?coordinator=Lead Coordinator")
    assert release_resp.status_code == 200

    refreshed_res = client.get("/api/resources").json()
    matched_after = next(r for r in refreshed_res if r["id"] == resource["id"])
    assert matched_after["allocated_quantity"] == 0
    assert matched_after["available_quantity"] == 5


def test_demo_reset_endpoint(client):
    reset_resp = client.post("/api/demo/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["reset"] is True
    # Audit log should record demo_reset
    audit = client.get("/api/audit-log").json()
    assert any(item["action"] == "demo_reset" for item in audit["items"])
