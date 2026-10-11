from __future__ import annotations

import argparse
import json
from datetime import timedelta
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .database import SessionLocal, init_db
from .models import (
    AuditLog, CoordinatorNote, CoverageRecord, DuplicateLink, Incident, IncidentHistory,
    Report, ReportSource, ResourceInventory, VerificationRecord, utcnow,
)
from .services import recalculate_incident


def _source(db: Session, kind: str, name: str, *, demo: bool = True) -> ReportSource:
    source = ReportSource(source_type=kind, source_name=name, is_demo=demo)
    db.add(source)
    db.flush()
    return source


def _incident(
    db: Session,
    *,
    demo_key: str,
    title: str,
    disaster_type: str,
    location_name: str | None,
    latitude: float | None,
    longitude: float | None,
    location_precision: str,
    needs: list[str],
    people_affected: int | None,
    threat_level: str,
    time_criticality: int | None,
    vulnerability_level: int | None,
    hazard_escalation: int | None,
    access_difficulty: int | None,
    status: str = "unverified",
    report: dict | None = None,
) -> Incident:
    incident = Incident(
        demo_key=demo_key,
        title=title,
        disaster_type=disaster_type,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
        location_precision=location_precision,
        needs_json=json.dumps(needs),
        people_affected=people_affected,
        threat_level=threat_level,
        time_criticality=time_criticality,
        vulnerability_level=vulnerability_level,
        hazard_escalation=hazard_escalation,
        access_difficulty=access_difficulty,
        status=status,
    )
    db.add(incident)
    db.flush()
    if report:
        src = _source(db, report.get("source_type", "sms"), report.get("source_name", "Simulated source"))
        db.add(Report(
            incident_id=incident.id,
            source_id=src.id,
            original_text=report["text"],
            reported_at=report["reported_at"],
            extracted_json=json.dumps(report.get("extracted", {})),
            is_firsthand=report.get("is_firsthand", False),
            independence_confirmed=report.get("independence_confirmed", False),
            demo_key=report.get("demo_key"),
        ))
        db.flush()
    return incident


def clear_demo_data(db: Session) -> None:
    """Delete only rows explicitly tagged as demo; unrelated user records are retained."""
    demo_incidents = db.scalars(select(Incident).where(Incident.demo_key.is_not(None))).all()
    demo_ids = [item.id for item in demo_incidents]
    if demo_ids:
        db.execute(delete(DuplicateLink).where(
            (DuplicateLink.incident_a_id.in_(demo_ids)) | (DuplicateLink.incident_b_id.in_(demo_ids))
        ))
        db.execute(delete(IncidentHistory).where(IncidentHistory.incident_id.in_(demo_ids)))
        db.execute(delete(VerificationRecord).where(VerificationRecord.incident_id.in_(demo_ids)))
        db.execute(delete(CoordinatorNote).where(CoordinatorNote.incident_id.in_(demo_ids)))
        db.execute(delete(AuditLog).where(AuditLog.incident_id.in_(demo_ids)))
        db.execute(delete(Report).where(Report.incident_id.in_(demo_ids)))
        db.execute(delete(Incident).where(Incident.id.in_(demo_ids)))
    db.execute(delete(CoverageRecord).where(CoverageRecord.demo_key.is_not(None)))
    demo_source_ids = db.scalars(select(ReportSource.id).where(ReportSource.is_demo.is_(True))).all()
    if demo_source_ids:
        # Any remaining report reference is user data; keep its source record.
        referenced = set(db.scalars(select(Report.source_id).where(Report.source_id.in_(demo_source_ids))).all())
        removable = [sid for sid in demo_source_ids if sid not in referenced]
        if removable:
            db.execute(delete(ReportSource).where(ReportSource.id.in_(removable)))
    db.execute(delete(ResourceInventory).where(ResourceInventory.demo_key.is_not(None)))
    db.commit()


def seed_demo_data(db: Session, *, reset_demo: bool = False) -> int:
    if reset_demo:
        clear_demo_data(db)
    already_seeded = db.scalar(select(func.count()).select_from(Incident).where(Incident.demo_key.is_not(None)))
    if already_seeded:
        return 0

    now = utcnow()
    flood_text = "SMS: Six residents are trapped above the ground floor near Kestrel Footbridge. Floodwater is rising rapidly; boat rescue and medical help needed now."
    flood = _incident(
        db, demo_key="demo-flood-kestrel", title="Residents reported trapped as floodwater rises",
        disaster_type="flood", location_name="Kestrel Footbridge", latitude=13.105, longitude=77.612,
        location_precision="approximate", needs=["rescue boat", "medical assistance"], people_affected=6,
        threat_level="immediate", time_criticality=4, vulnerability_level=2, hazard_escalation=4,
        access_difficulty=3, report={"demo_key": "demo-report-flood-kestrel", "text": flood_text,
            "source_type": "sms", "source_name": "Simulated resident SMS", "reported_at": now - timedelta(minutes=18),
            "is_firsthand": False, "independence_confirmed": False,
            "extracted": {"disaster_type": "flood", "location_name": "Kestrel Footbridge"}},
    )

    copy_text = "Volunteer message: At Kestrel Footbridge, six people remain trapped while flood water keeps rising; request boat rescue and medical support."
    flood_copy = _incident(
        db, demo_key="demo-flood-kestrel-copy", title="Possible repeat report: Kestrel Footbridge flood",
        disaster_type="flood", location_name="Kestrel Footbridge", latitude=13.106, longitude=77.613,
        location_precision="approximate", needs=["rescue boat", "medical assistance"], people_affected=6,
        threat_level="immediate", time_criticality=4, vulnerability_level=2, hazard_escalation=4,
        access_difficulty=3, report={"demo_key": "demo-report-flood-kestrel-copy", "text": copy_text,
            "source_type": "volunteer", "source_name": "Simulated volunteer channel", "reported_at": now - timedelta(minutes=11),
            "is_firsthand": False, "independence_confirmed": False,
            "extracted": {"disaster_type": "flood", "location_name": "Kestrel Footbridge"}},
    )
    a, b = sorted([flood.id, flood_copy.id])
    db.add(DuplicateLink(incident_a_id=a, incident_b_id=b, similarity=86.0,
                         reason="Text similarity is 86%. Both mention trapped residents, rising floodwater and Kestrel Footbridge within minutes.", status="possible"))

    quake_text_1 = "Field note: Earthquake shaking damaged the east wall at Pineglass School; 18 people are sheltering in the yard and two report minor injuries. Medical check and temporary shelter requested."
    quake = _incident(
        db, demo_key="demo-quake-pineglass", title="Earthquake damage reported at Pineglass School",
        disaster_type="earthquake", location_name="Pineglass School", latitude=12.962, longitude=77.584,
        location_precision="approximate", needs=["medical assistance", "shelter"], people_affected=18,
        threat_level="serious", time_criticality=3, vulnerability_level=2, hazard_escalation=2,
        access_difficulty=1, status="verified",
        report={"demo_key": "demo-report-quake-field", "text": quake_text_1,
            "source_type": "field", "source_name": "Simulated field team Alpha", "reported_at": now - timedelta(hours=1),
            "is_firsthand": True, "independence_confirmed": True,
            "extracted": {"disaster_type": "earthquake", "location_name": "Pineglass School"}},
    )
    src = _source(db, "authorized", "Simulated clinic liaison")
    db.add(Report(incident_id=quake.id, source_id=src.id,
        original_text="Clinic liaison independently confirms minor injuries and requests a medical check at Pineglass School.",
        reported_at=now - timedelta(minutes=42),
        extracted_json=json.dumps({"disaster_type": "earthquake", "location_name": "Pineglass School"}),
        is_firsthand=True, independence_confirmed=True, demo_key="demo-report-quake-clinic"))
    from .models import VerificationRecord
    db.add(VerificationRecord(incident_id=quake.id, action="verified", coordinator="Demo coordinator",
                              note="Synthetic demonstration verification record.", created_at=now - timedelta(minutes=38)))

    unknown = _incident(
        db, demo_key="demo-quake-unresolved", title="Earthquake report — location not resolved",
        disaster_type="earthquake", location_name=None, latitude=None, longitude=None,
        location_precision="unresolved", needs=["shelter"], people_affected=None,
        threat_level="possible", time_criticality=2, vulnerability_level=None, hazard_escalation=2,
        access_difficulty=None, status="needs_info",
        report={"demo_key": "demo-report-quake-unresolved", "text": "Social post: Strong shaking, a wall has fallen somewhere near the hills. We need shelter but I cannot share a safe location right now.",
            "source_type": "social", "source_name": "Simulated public post", "reported_at": now - timedelta(hours=2),
            "is_firsthand": False, "independence_confirmed": False,
            "extracted": {"disaster_type": "earthquake", "location_name": None}},
    )

    stale = _incident(
        db, demo_key="demo-flood-stale", title="Older flood report needs re-verification",
        disaster_type="flood", location_name="Morrow Weir", latitude=13.215, longitude=77.482,
        location_precision="approximate", needs=["drinking water"], people_affected=12,
        threat_level="possible", time_criticality=1, vulnerability_level=1, hazard_escalation=1,
        access_difficulty=2, status="unverified",
        report={"demo_key": "demo-report-flood-stale", "text": "Yesterday's simulated report: floodwater entered homes near Morrow Weir. Twelve residents asked for drinking water; current conditions are unknown.",
            "source_type": "sms", "source_name": "Simulated resident SMS", "reported_at": now - timedelta(hours=31),
            "is_firsthand": False, "independence_confirmed": False,
            "extracted": {"disaster_type": "flood", "location_name": "Morrow Weir"}},
    )

    db.add(CoverageRecord(
        area_name="Northglass Plateau (synthetic cell)", latitude=13.31, longitude=77.75,
        hazard_exposure="high", last_confirmed_at=now - timedelta(hours=36),
        connectivity_limited=True, access_limited=True,
        note="Synthetic demo observation: intermittent connectivity and limited access were reported.",
        synthetic=True, demo_key="demo-coverage-northglass",
    ))
    db.add(CoverageRecord(
        area_name="East Ember Cell (synthetic cell)", latitude=13.02, longitude=77.83,
        hazard_exposure="medium", last_confirmed_at=now - timedelta(hours=3),
        connectivity_limited=False, access_limited=False,
        note="Synthetic monitored cell; last simulation check-in was recent.",
        synthetic=True, demo_key="demo-coverage-east-ember",
    ))
    db.add(CoverageRecord(
        area_name="South Fern Cell (synthetic cell)", latitude=12.81, longitude=77.56,
        hazard_exposure="high", last_confirmed_at=None,
        connectivity_limited=False, access_limited=True,
        note="Synthetic high-exposure cell without a field timestamp.",
        synthetic=True, demo_key="demo-coverage-south-fern",
    ))
    db.add(ResourceInventory(
        resource_type="rescue boat", area_name="Kestrel Footbridge", quantity=3, allocated_quantity=0,
        availability_status="available", updated_by="Demo logistics lead", demo_key="demo-res-boat-kestrel",
    ))
    db.add(ResourceInventory(
        resource_type="medical team", area_name="Pineglass School", quantity=4, allocated_quantity=1,
        availability_status="available", updated_by="Demo medical lead", demo_key="demo-res-med-pineglass",
    ))
    db.add(ResourceInventory(
        resource_type="drinking water", area_name="Morrow Weir", quantity=500, allocated_quantity=0,
        availability_status="available", updated_by="Demo supplies coordinator", demo_key="demo-res-water-morrow",
    ))
    db.add(ResourceInventory(
        resource_type="search and rescue team", area_name=None, quantity=2, allocated_quantity=0,
        availability_status="available", updated_by="Central emergency base", demo_key="demo-res-sar-central",
    ))
    db.add(ResourceInventory(
        resource_type="evacuation support", area_name=None, quantity=6, allocated_quantity=0,
        availability_status="available", updated_by="Regional fleet", demo_key="demo-res-evac-fleet",
    ))
    db.add(ResourceInventory(
        resource_type="temporary shelter", area_name=None, quantity=50, allocated_quantity=0,
        availability_status="available", updated_by="Shelter logistics", demo_key="demo-res-shelter-main",
    ))
    db.flush()
    for incident in (flood, flood_copy, quake, unknown, stale):
        recalculate_incident(db, incident)
        db.add(AuditLog(incident_id=incident.id, entity_type="incident", entity_id=str(incident.id),
                        action="demo_seeded", actor="RescueGrid demo", details_json="{\"simulation\":true}"))
    db.commit()
    return 5


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed or safely reset RescueGrid's synthetic demo records.")
    parser.add_argument("--reset-demo", action="store_true", help="remove only rows tagged as demo, then reseed; user records are retained")
    args = parser.parse_args()
    init_db()
    with SessionLocal() as db:
        added = seed_demo_data(db, reset_demo=args.reset_demo)
    print(f"Synthetic demo incidents added: {added}")
    print("Only explicitly tagged demo rows are affected by --reset-demo.")


if __name__ == "__main__":
    main()
