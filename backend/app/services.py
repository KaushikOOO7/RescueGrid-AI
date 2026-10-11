from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    AuditLog, CoordinatorNote, DuplicateLink, Incident, IncidentHistory, Report,
    ReportSource, ResourceAllocation, ResourceInventory,
)
from .scoring import assess_confidence, score_urgency, urgency_label


def parse_json(value: str | None, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _report_sources(report: Report) -> dict[str, Any]:
    source = report.source
    return {
        "id": report.id,
        "original_text": report.original_text,
        "source_type": source.source_type if source else "unknown",
        "source_name": source.source_name if source else None,
        "reported_at": report.reported_at,
        "is_firsthand": report.is_firsthand,
        "independence_confirmed": report.independence_confirmed,
        "extracted": parse_json(report.extracted_json, {}),
    }


def effective_priority(incident: Incident) -> int:
    return incident.human_priority_override if incident.human_priority_override is not None else incident.urgency_score


def _priority_label(score: int) -> str:
    return urgency_label(score)


def urgency_explanation(incident: Incident) -> str:
    factors = []
    if incident.threat_level == "immediate":
        factors.append("the report indicates an immediate threat to life")
    elif incident.threat_level == "serious":
        factors.append("serious threat indicators are recorded")
    elif incident.threat_level == "possible":
        factors.append("possible threat indicators are recorded")
    if incident.time_criticality is not None and incident.time_criticality >= 3:
        factors.append("time criticality is marked high")
    if incident.people_affected is not None and incident.people_affected > 0:
        factors.append(f"{incident.people_affected} people are recorded as affected")
    if incident.vulnerability_level is not None and incident.vulnerability_level >= 3:
        factors.append("vulnerability indicators are recorded")
    if incident.hazard_escalation is not None and incident.hazard_escalation >= 3:
        factors.append("conditions may be escalating")
    if incident.access_difficulty is not None and incident.access_difficulty >= 3:
        factors.append("rescue access may be difficult")
    if not factors:
        return "No strong urgency inputs were available; missing information is not evidence that conditions are safe."
    if len(factors) == 1:
        explanation = factors[0]
    elif len(factors) == 2:
        explanation = f"{factors[0]} and {factors[1]}"
    else:
        explanation = ", ".join(factors[:-1]) + f", and {factors[-1]}"
    return f"{incident.urgency_level.title()} urgency because {explanation}."


def incident_summary(incident: Incident) -> dict[str, Any]:
    return {
        "id": incident.id,
        "title": incident.title,
        "disaster_type": incident.disaster_type,
        "location_name": incident.location_name,
        "latitude": incident.latitude,
        "longitude": incident.longitude,
        "location_precision": incident.location_precision,
        "needs": parse_json(incident.needs_json, []),
        "people_affected": incident.people_affected,
        "status": incident.status,
        "urgency_score": incident.urgency_score,
        "urgency_level": incident.urgency_level,
        "priority_score": effective_priority(incident),
        "priority_level": _priority_label(effective_priority(incident)),
        "human_priority_override": incident.human_priority_override,
        "priority_override_reason": incident.priority_override_reason,
        "confidence_score": incident.confidence_score,
        "confidence_explanation": incident.confidence_explanation,
        "urgency_reasons": parse_json(incident.urgency_reasons_json, []),
        "urgency_summary": urgency_explanation(incident),
        "report_count": len(incident.reports),
        "last_reported_at": incident.last_reported_at,
        "created_at": incident.created_at,
        "updated_at": incident.updated_at,
        "location_resolved": incident.latitude is not None and incident.longitude is not None,
        "merged_into_id": incident.merged_into_id,
    }


def resource_recommendations(db: Session, incident: Incident) -> list[dict[str, Any]]:
    needs = parse_json(incident.needs_json, [])
    mapping = {
        "medical assistance": "medical team",
        "medical": "medical team",
        "rescue support": "search and rescue team",
        "rescue boat": "rescue boat",
        "evacuation support": "evacuation support",
        "drinking water": "drinking water",
        "food": "food supplies",
        "shelter": "temporary shelter",
        "communications": "communications support",
    }
    recommendations = []
    known_items = db.scalars(select(ResourceInventory)).all()
    for need in needs:
        resource_type = mapping.get(need.lower(), need)
        matching = [
            item for item in known_items
            if item.resource_type.lower() == resource_type.lower()
            and (item.area_name is None or (incident.location_name and item.area_name.strip().lower() == incident.location_name.strip().lower()))
        ]
        availability = "Unknown — no inventory has been entered"
        quantity = None
        available_quantity = None
        resource_id = None
        if matching:
            selected = matching[0]
            resource_id = selected.id
            availability = selected.availability_status
            quantity = selected.quantity
            available_quantity = max(0, (selected.quantity or 0) - selected.allocated_quantity) if selected.quantity is not None else None
        recommendations.append({
            "resource_id": resource_id,
            "need": need,
            "resource_type_to_consider": resource_type,
            "availability": availability,
            "quantity": quantity,
            "available_quantity": available_quantity,
            "approval_required": True,
            "note": "Recommendation only. Capacity, route safety, and deployment feasibility are not assessed.",
        })
    return recommendations


def incident_detail(db: Session, incident: Incident) -> dict[str, Any]:
    data = incident_summary(incident)
    reports = sorted(incident.reports, key=lambda report: report.reported_at or datetime.min, reverse=True)
    allocations = db.scalars(
        select(ResourceAllocation)
        .where(ResourceAllocation.incident_id == incident.id)
        .order_by(ResourceAllocation.created_at.desc())
    ).all()
    data.update({
        "threat_level": incident.threat_level,
        "time_criticality": incident.time_criticality,
        "vulnerability_level": incident.vulnerability_level,
        "hazard_escalation": incident.hazard_escalation,
        "access_difficulty": incident.access_difficulty,
        "original_reports": [_report_sources(report) for report in reports],
        "verification_history": [
            {"id": item.id, "action": item.action, "coordinator": item.coordinator, "note": item.note, "created_at": item.created_at}
            for item in sorted(incident.verifications, key=lambda item: item.created_at, reverse=True)
        ],
        "history": [
            {"id": item.id, "kind": item.kind, "old_value": item.old_value, "new_value": item.new_value, "reason": item.reason, "coordinator": item.coordinator, "created_at": item.created_at}
            for item in sorted(incident.histories, key=lambda item: item.created_at, reverse=True)
        ],
        "notes": [
            {"id": item.id, "note": item.note, "coordinator": item.coordinator, "created_at": item.created_at}
            for item in sorted(incident.notes, key=lambda item: item.created_at, reverse=True)
        ],
        "possible_duplicates": duplicate_summaries(db, incident),
        "resource_recommendations": resource_recommendations(db, incident),
        "allocations": [
            {
                "id": alloc.id,
                "resource_id": alloc.resource_id,
                "resource_type": alloc.resource.resource_type if alloc.resource else "unknown",
                "area_name": alloc.resource.area_name if alloc.resource else None,
                "allocated_quantity": alloc.allocated_quantity,
                "coordinator": alloc.coordinator,
                "note": alloc.note,
                "status": alloc.status,
                "created_at": alloc.created_at,
            }
            for alloc in allocations
        ],
        "recommended_action": _recommended_action(incident),
        "human_decision": {
            "priority_override": incident.human_priority_override,
            "priority_override_reason": incident.priority_override_reason,
            "status": incident.status,
        },
        "simulation_data": bool(incident.demo_key),
    })
    return data


def _recommended_action(incident: Incident) -> str:
    if incident.status == "resolved":
        return "Resolved by a coordinator. Continue normal monitoring only if assigned."
    if incident.urgency_score >= 60 and incident.status != "verified":
        return "Urgent human verification is recommended; consider the listed resource types only after coordinator review."
    if incident.status in {"unverified", "needs_info"}:
        return "Request verification or missing details from an authorized source."
    if incident.urgency_score >= 60:
        return "Review the listed needs with an authorized coordinator; no dispatch is authorized by this system."
    return "Continue coordinator review and update when new information is available."


def duplicate_summaries(db: Session, incident: Incident) -> list[dict[str, Any]]:
    links = db.scalars(select(DuplicateLink).where(
        (DuplicateLink.incident_a_id == incident.id) | (DuplicateLink.incident_b_id == incident.id)
    ).order_by(DuplicateLink.created_at.desc())).all()
    result = []
    for link in links:
        other_id = link.incident_b_id if link.incident_a_id == incident.id else link.incident_a_id
        other = db.get(Incident, other_id)
        if not other:
            continue
        candidate_report = next(iter(other.reports), None)
        result.append({
            "relationship_id": link.id,
            "other_incident_id": other.id,
            "other_title": other.title,
            "other_status": other.status,
            "candidate_report_id": candidate_report.id if candidate_report else None,
            "similarity": link.similarity,
            "reason": link.reason,
            "status": link.status,
            "coordinator_note": link.coordinator_note,
        })
    return result


def recalculate_incident(db: Session, incident: Incident) -> None:
    reports = db.scalars(select(Report).where(Report.incident_id == incident.id)).all()
    incident.reports = reports
    if reports:
        incident.last_reported_at = max(report.reported_at for report in reports if report.reported_at)
    urgency = score_urgency({
        "threat_level": incident.threat_level,
        "time_criticality": incident.time_criticality,
        "people_affected": incident.people_affected,
        "vulnerability_level": incident.vulnerability_level,
        "hazard_escalation": incident.hazard_escalation,
        "access_difficulty": incident.access_difficulty,
    })
    incident.urgency_score = urgency["score"]
    incident.urgency_level = urgency["level"]
    incident.urgency_reasons_json = json.dumps(urgency["reasons"])

    for report in reports:
        extracted = parse_json(report.extracted_json, {})
        report.extracted_disaster_type = extracted.get("disaster_type")
        report.extracted_location = extracted.get("location_name")
    assessment = assess_confidence(
        {
            "location_precision": incident.location_precision,
        },
        reports,
        status=incident.status,
        latest_reported_at=incident.last_reported_at,
    )
    incident.confidence_score = assessment["score"]
    incident.confidence_explanation = assessment["explanation"]
    incident.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)


def make_audit(
    db: Session,
    *,
    incident_id: int | None,
    entity_type: str,
    entity_id: str | int,
    action: str,
    actor: str = "Coordinator",
    details: dict[str, Any] | None = None,
) -> AuditLog:
    row = AuditLog(
        incident_id=incident_id,
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        actor=actor,
        details_json=json.dumps(details or {}, default=str),
    )
    db.add(row)
    return row
