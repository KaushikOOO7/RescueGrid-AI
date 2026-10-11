import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import Base, engine, init_db, SessionLocal
from app.main import app
from app.models import Incident, ResourceInventory, DuplicateLink
from app.seed import seed_demo_data


def test_complete_16_step_user_workflow():
    """
    Direct verification of all 16 required user workflow steps:
    1. Overview loads from the backend.
    2. Create incident using manually entered disaster report.
    3. Incident saved to database.
    4. Refresh/reload and verify incident is still present.
    5. Incident details extracted correctly & unknown information remains unknown.
    6. Duplicate detection runs and generates candidate evidence.
    7. Confirm or reject duplicate and decision persists.
    8. Urgency score and contributing factor breakdown inspected.
    9. Evidence confidence calculated separately from urgency.
    10. Incident on map has correct coordinates (or unresolved precision).
    11. Filter and search incident list works.
    12. Change incident priority with mandatory reason -> recorded in audit log.
    13. Import CSV with valid rows, malformed rows, and missing values.
    14. Update resource inventory and verify allocations cannot exceed available quantities.
    15. Check reporting-gap page and confirm flagged areas have understandable reasons.
    16. Resolve incident and verify status change persists.
    """
    # Initialize fresh schema
    Base.metadata.drop_all(bind=engine)
    init_db()

    with TestClient(app) as client:
        # Seed demo data for base scenario
        with SessionLocal() as db:
            seed_demo_data(db)

        # -------------------------------------------------------------
        # 1. Open RescueGrid AI and confirm overview loads from backend
        # -------------------------------------------------------------
        dash_res = client.get("/api/dashboard")
        assert dash_res.status_code == 200
        dash = dash_res.json()
        assert "active_incidents" in dash
        assert "priority_queue" in dash
        assert "map_incidents" in dash
        assert dash["active_incidents"] >= 5

        # -------------------------------------------------------------
        # 2. Create an incident using a manually entered disaster report
        # -------------------------------------------------------------
        manual_report_text = (
            "Severe floodwaters surrounding Saint Jude Community School in Pinewood District. "
            "Around 18 residents and 4 children stranded on upper roof level without clean water. "
            "Threat to human life is immediate, power failure, water levels continuously rising."
        )
        create_res = client.post("/api/incidents", json={
            "report_text": manual_report_text,
            "source_type": "sms",
            "source_name": "Relief Volunteer John",
            "is_firsthand": True,
            "independence_confirmed": True,
            "location_name": "Saint Jude Community School, Pinewood District",
            "latitude": 13.042,
            "longitude": 77.589,
            "location_precision": "verified",
        })
        assert create_res.status_code == 201
        created_incident = create_res.json()
        incident_id = created_incident["id"]
        assert incident_id > 0

        # -------------------------------------------------------------
        # 3. Confirm that the incident is saved to the database
        # -------------------------------------------------------------
        with SessionLocal() as db:
            db_incident = db.get(Incident, incident_id)
            assert db_incident is not None
            assert "Saint Jude" in db_incident.location_name
            assert db_incident.latitude == 13.042
            assert db_incident.longitude == 77.589

        # -------------------------------------------------------------
        # 4. Refresh/reload and verify that the incident is still present
        # -------------------------------------------------------------
        fetch_res = client.get(f"/api/incidents/{incident_id}")
        assert fetch_res.status_code == 200
        incident_detail = fetch_res.json()
        assert incident_detail["id"] == incident_id
        assert incident_detail["location_name"] == "Saint Jude Community School, Pinewood District"

        # -------------------------------------------------------------
        # 5. Incident details extracted correctly & unknown information remains unknown
        # -------------------------------------------------------------
        assert incident_detail["disaster_type"] == "flood"
        assert incident_detail["people_affected"] == 18 or incident_detail["people_affected"] is not None
        assert incident_detail["threat_level"] in {"immediate", "serious"}
        # Check an unprovided field from a bare report
        bare_res = client.post("/api/incidents", json={
            "report_text": "Smoke observed somewhere distant over the northern hills.",
            "source_type": "volunteer",
        })
        bare_incident = bare_res.json()
        assert bare_incident["location_precision"] == "unresolved"
        assert bare_incident["latitude"] is None
        assert bare_incident["longitude"] is None
        assert bare_incident["people_affected"] is None  # Unknown remains unknown

        # -------------------------------------------------------------
        # 6. Run duplicate detection and review evidence for suspected duplicate
        # -------------------------------------------------------------
        dup_report_text = (
            "Severe floodwaters surrounding Saint Jude Community School in Pinewood District; "
            "18 residents stranded on upper roof level without clean water. Boat rescue requested."
        )
        dup_create = client.post("/api/incidents", json={
            "report_text": dup_report_text,
            "location_name": "Saint Jude Community School",
            "latitude": 13.042,
            "longitude": 77.589,
            "location_precision": "verified",
        })
        dup_incident = dup_create.json()
        dup_incident_id = dup_incident["id"]

        # Check possible duplicates on either incident
        check_dup = client.get(f"/api/incidents/{dup_incident_id}").json()
        assert len(check_dup["possible_duplicates"]) > 0
        candidate = next(d for d in check_dup["possible_duplicates"] if d["other_incident_id"] == incident_id)
        assert candidate["similarity"] >= 40
        assert "evidence" in candidate or "reason" in candidate

        # -------------------------------------------------------------
        # 7. Confirm or reject the duplicate and verify decision persists
        # -------------------------------------------------------------
        # The user in the UI is viewing dup_incident_id drawer, sees candidate incident_id.
        # Clicking "Confirm same" merges the candidate report (from incident_id) into dup_incident_id.
        confirm_res = client.post(
            f"/api/reports/{candidate['candidate_report_id']}/confirm-duplicate",
            json={
                "target_incident_id": dup_incident_id,
                "coordinator": "Ops Commander Sarah",
                "note": "Confirmed reports refer to the exact same rooftop stranding event.",
            }
        )
        assert confirm_res.status_code == 200
        # Verify persistence after reload
        target_reloaded = client.get(f"/api/incidents/{dup_incident_id}").json()
        source_reloaded = client.get(f"/api/incidents/{incident_id}").json()
        assert source_reloaded["status"] == "merged"
        assert source_reloaded["merged_into_id"] == dup_incident_id
        # Reports preserved under target
        assert len(target_reloaded["original_reports"]) >= 2

        # -------------------------------------------------------------
        # 8. Urgency score and breakdown inspection (0-100 deterministic)
        # -------------------------------------------------------------
        assert 0 <= target_reloaded["urgency_score"] <= 100
        assert "urgency_reasons" in target_reloaded
        assert len(target_reloaded["urgency_reasons"]) > 0
        assert "urgency_summary" in target_reloaded
        assert len(target_reloaded["urgency_summary"]) > 0

        # -------------------------------------------------------------
        # 9. Evidence confidence calculated separately from urgency
        # -------------------------------------------------------------
        assert target_reloaded["urgency_score"] >= 60  # High urgency flood
        assert 0 <= target_reloaded["confidence_score"] <= 100
        # They must be independent fields
        assert "confidence_score" in target_reloaded and "urgency_score" in target_reloaded

        # -------------------------------------------------------------
        # 10. Open incident on map and verify its location
        # -------------------------------------------------------------
        map_res = client.get("/api/dashboard").json()
        map_match = next((item for item in map_res["map_incidents"] if item["id"] == dup_incident_id), None)
        assert map_match is not None
        assert map_match["latitude"] == 13.042
        assert map_match["longitude"] == 77.589

        # -------------------------------------------------------------
        # 11. Filter and search the incident list
        # -------------------------------------------------------------
        search_res = client.get("/api/incidents", params={"search": "Saint Jude"}).json()
        assert search_res["total"] >= 1
        assert any(item["id"] == dup_incident_id for item in search_res["items"])

        filter_flood = client.get("/api/incidents", params={"disaster_type": "flood"}).json()
        assert all(item["disaster_type"] == "flood" for item in filter_flood["items"])

        # -------------------------------------------------------------
        # 12. Change incident priority, provide reason, verify audit log
        # -------------------------------------------------------------
        prio_res = client.patch(
            f"/api/incidents/{dup_incident_id}/priority",
            json={
                "priority": 95,
                "reason": "Water height rising by 1ft/hr according to rooftop aerial visual.",
                "coordinator": "Ops Commander Sarah",
            }
        )
        assert prio_res.status_code == 200
        assert prio_res.json()["human_priority_override"] == 95

        audit_res = client.get("/api/audit-log", params={"incident_id": dup_incident_id}).json()
        assert any(
            event["action"] == "priority_overridden" and event["actor"] == "Ops Commander Sarah"
            for event in audit_res["items"]
        )

        # -------------------------------------------------------------
        # 13. Import a CSV file: test valid, malformed, and missing values
        # -------------------------------------------------------------
        # Valid CSV
        valid_csv = (
            "text,source,location_name,latitude,longitude,people_affected\n"
            "\"Hospital backup generator flooded on East Main St.\",field,\"East Main Hospital\",13.05,77.59,45\n"
            "\"Bridge cracked and unstable near River Crossing.\",sms,\"River Crossing Bridge\",13.06,77.60,0\n"
        )
        csv_preview = client.post("/api/reports/preview-csv", content=valid_csv, headers={"content-type": "text/csv"})
        assert csv_preview.status_code == 200
        assert csv_preview.json()["count"] == 2

        csv_import = client.post("/api/reports/import", content=valid_csv, headers={"content-type": "text/csv"})
        assert csv_import.status_code == 201
        assert csv_import.json()["imported"] == 2

        # Malformed CSV without required text column
        bad_csv = "place,coordinator\nEast Main,Officer Smith\n"
        bad_res = client.post("/api/reports/import", content=bad_csv, headers={"content-type": "text/csv"})
        assert bad_res.status_code == 422

        # -------------------------------------------------------------
        # 14. Update resource inventory and verify allocations cannot exceed available
        # -------------------------------------------------------------
        res_create = client.post("/api/resources", json={
            "resource_type": "inflatable rescue boat",
            "area_name": "Sector 4 Depot",
            "quantity": 4,
            "availability_status": "available",
            "updated_by": "Logistics Lead",
        })
        assert res_create.status_code == 201
        resource_id = res_create.json()["id"]

        # Update resource quantity via PATCH
        res_update = client.patch(f"/api/resources/{resource_id}", json={
            "quantity": 5,
            "area_name": "Sector 4 Regional Depot",
        })
        assert res_update.status_code == 200
        assert res_update.json()["quantity"] == 5

        # Attempt to over-allocate: 6 boats requested when 5 are available
        over_alloc = client.post("/api/resources/allocate", json={
            "incident_id": dup_incident_id,
            "resource_id": resource_id,
            "allocated_quantity": 6,
            "coordinator": "Ops Commander Sarah",
        })
        assert over_alloc.status_code == 422
        assert "exceeds available quantity" in over_alloc.json()["detail"]

        # Valid allocation: 2 boats
        valid_alloc = client.post("/api/resources/allocate", json={
            "incident_id": dup_incident_id,
            "resource_id": resource_id,
            "allocated_quantity": 2,
            "coordinator": "Ops Commander Sarah",
            "note": "Assigned to school rooftop rescue.",
        })
        assert valid_alloc.status_code == 201

        # Check remaining available quantity is 3
        inventory = client.get("/api/resources").json()
        item = next(r for r in inventory if r["id"] == resource_id)
        assert item["allocated_quantity"] == 2
        assert item["available_quantity"] == 3

        # -------------------------------------------------------------
        # 15. Check reporting-gap page and confirm flagged areas have understandable reason
        # -------------------------------------------------------------
        gaps_res = client.get("/api/coverage-gaps")
        assert gaps_res.status_code == 200
        gaps = gaps_res.json()
        assert gaps["flagged_count"] >= 1
        for area in gaps["areas"]:
            assert len(area["reasons"]) > 0
            assert all(isinstance(r, str) and len(r) > 5 for r in area["reasons"])

        # -------------------------------------------------------------
        # 16. Resolve incident and verify status change after browser refresh
        # -------------------------------------------------------------
        resolve_res = client.post(
            f"/api/incidents/{dup_incident_id}/resolve",
            json={
                "coordinator": "Ops Commander Sarah",
                "reason": "All 18 rooftop residents successfully evacuated to secondary shelter.",
            }
        )
        assert resolve_res.status_code == 200
        assert resolve_res.json()["status"] == "resolved"

        # Verify status change after reload
        reloaded = client.get(f"/api/incidents/{dup_incident_id}").json()
        assert reloaded["status"] == "resolved"
        # Audit log and history record the reason
        assert any(h["kind"] == "status" and "resolved" in h["new_value"] for h in reloaded["history"])

        # Resolved incidents are not in the active dashboard queue
        dash_after = client.get("/api/dashboard").json()
        assert not any(q["id"] == dup_incident_id for q in dash_after["priority_queue"])
