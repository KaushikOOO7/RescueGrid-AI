from __future__ import annotations

import csv
import io
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from .config import AUTO_SEED, CORS_ORIGINS, DATABASE_URL, DUPLICATE_SIMILARITY_THRESHOLD
from .database import SessionLocal, get_db, init_db
from .duplicates import find_possible_duplicate_candidates
from .extraction import extract_report
from .gaps import identify_reporting_gaps
from .models import (
    AuditLog, CoordinatorNote, CoverageRecord, DuplicateLink, Incident,
    IncidentHistory, Report, ReportSource, ResourceAllocation, ResourceInventory,
    VerificationRecord, utcnow,
)
from .schemas import (
    AllocationCreate, AllocationItem, AnalyticsResponse, AuditLogResponse,
    ConfirmDuplicateRequest, CoverageGapsResponse, DashboardResponse, HealthResponse,
    IncidentCreate, IncidentDetailResponse, IncidentListResponse, IncidentPatch,
    MarkSeparateRequest, NoteCreate, PriorityRequest, ReportImportResponse,
    ReportImportRow, ReportPreviewRequest, ReportPreviewResponse, ResolveRequest,
    ResourceCreate, ResourceItem, ResourceUpdate, VerifyRequest,
)
from .services import (
    effective_priority, incident_detail, incident_summary, make_audit,
    parse_json, recalculate_incident,
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if AUTO_SEED:
        with SessionLocal() as db:
            existing = db.scalar(select(func.count()).select_from(Incident)) or 0
            # Never seed a non-empty user database during normal startup.
            if existing == 0:
                from .seed import seed_demo_data
                seed_demo_data(db)
    yield


app = FastAPI(
    title="RescueGrid AI API",
    version="1.0.0",
    description=(
        "Synthetic-data-first disaster-response decision support prototype. "
        "Urgency and evidence confidence are separate heuristics; human approval is required."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _not_found_incident(db: Session, incident_id: int) -> Incident:
    incident = db.scalar(
        select(Incident).options(
            selectinload(Incident.reports).selectinload(Report.source),
            selectinload(Incident.verifications),
            selectinload(Incident.histories),
            selectinload(Incident.notes),
        ).where(Incident.id == incident_id)
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


def _merge_extracted(text: str, model: IncidentCreate | ReportImportRow) -> dict[str, Any]:
    """Fill what can be extracted, then apply only explicitly supplied structured inputs."""
    extracted = extract_report(text)
    supplied = model.model_dump()
    explicitly_set = model.model_fields_set
    allowed = {
        "title", "disaster_type", "location_name", "latitude", "longitude", "location_precision",
        "needs", "people_affected", "threat_level", "time_criticality", "vulnerability_level",
        "hazard_escalation", "access_difficulty",
    }
    for key in allowed & explicitly_set:
        extracted[key] = supplied[key]
    if not extracted.get("title"):
        extracted["title"] = "Unclassified emergency report"
    if extracted.get("location_name") is None and extracted.get("latitude") is None:
        if extracted.get("location_precision") == "approximate":
            extracted["location_precision"] = "unresolved"
    return extracted


def _values_for_duplicate(incident: Incident) -> dict[str, Any]:
    report = max(incident.reports, key=lambda item: item.reported_at or datetime.min, default=None)
    return {
        "incident_id": incident.id,
        "text": report.original_text if report else incident.title,
        "disaster_type": incident.disaster_type,
        "reported_at": incident.last_reported_at,
        "last_reported_at": incident.last_reported_at,
        "latitude": incident.latitude,
        "longitude": incident.longitude,
        "status": incident.status,
    }


def _add_duplicate_candidates(db: Session, incident: Incident, report_text: str, reported_at: datetime) -> list[dict[str, Any]]:
    db.flush()
    existing = db.scalars(
        select(Incident).options(selectinload(Incident.reports)).where(Incident.id != incident.id)
    ).all()
    candidates = find_possible_duplicate_candidates(
        {
            "text": report_text,
            "disaster_type": incident.disaster_type,
            "reported_at": reported_at,
            "latitude": incident.latitude,
            "longitude": incident.longitude,
        },
        [_values_for_duplicate(item) for item in existing],
        threshold=DUPLICATE_SIMILARITY_THRESHOLD,
    )
    created = []
    for candidate in candidates:
        other_id = int(candidate["incident_id"])
        first, second = sorted([incident.id, other_id])
        existing_link = db.scalar(select(DuplicateLink).where(
            DuplicateLink.incident_a_id == first,
            DuplicateLink.incident_b_id == second,
        ))
        if existing_link:
            continue
        link = DuplicateLink(
            incident_a_id=first,
            incident_b_id=second,
            similarity=candidate["similarity"],
            reason=candidate["reason"],
            status="possible",
        )
        db.add(link)
        created.append({
            "new_incident_id": incident.id,
            "candidate_incident_id": other_id,
            "similarity": candidate["similarity"],
            "reason": candidate["reason"],
            "status": "possible",
        })
    return created


def _create_incident(db: Session, model: IncidentCreate | ReportImportRow, *, demo: bool = False) -> tuple[Incident, list[dict[str, Any]]]:
    text = model.report_text if isinstance(model, IncidentCreate) else model.text
    values = _merge_extracted(text, model)
    reported_at = model.reported_at or utcnow()
    source_type = getattr(model, "source_type", "csv")
    source_name = getattr(model, "source_name", None)
    incident = Incident(
        title=values.get("title") or "Unclassified emergency report",
        disaster_type=values.get("disaster_type") or "unknown",
        location_name=values.get("location_name"),
        latitude=values.get("latitude"),
        longitude=values.get("longitude"),
        location_precision=values.get("location_precision") or "unknown",
        needs_json=json.dumps(values.get("needs") or []),
        people_affected=values.get("people_affected"),
        threat_level=values.get("threat_level") or "unknown",
        time_criticality=values.get("time_criticality"),
        vulnerability_level=values.get("vulnerability_level"),
        hazard_escalation=values.get("hazard_escalation"),
        access_difficulty=values.get("access_difficulty"),
        status=getattr(model, "status", "unverified"),
    )
    db.add(incident)
    db.flush()
    source = ReportSource(source_type=source_type, source_name=source_name)
    db.add(source)
    db.flush()
    report = Report(
        incident_id=incident.id,
        source_id=source.id,
        original_text=text,
        reported_at=reported_at,
        extracted_json=json.dumps(values),
        is_firsthand=bool(getattr(model, "is_firsthand", False)),
        independence_confirmed=bool(getattr(model, "independence_confirmed", False)),
    )
    db.add(report)
    db.flush()
    recalculate_incident(db, incident)
    candidates = _add_duplicate_candidates(db, incident, text, reported_at)
    make_audit(
        db,
        incident_id=incident.id,
        entity_type="incident",
        entity_id=incident.id,
        action="report_ingested",
        actor="RescueGrid intake",
        details={"source_type": source_type, "report_id": report.id, "simulation": demo},
    )
    return incident, candidates


def _csv_rows(raw: str) -> list[ReportImportRow]:
    if len(raw.encode("utf-8")) > 2_000_000:
        raise HTTPException(status_code=413, detail="CSV exceeds the 2 MB prototype import limit")
    try:
        reader = csv.DictReader(io.StringIO(raw.lstrip("\ufeff")))
    except csv.Error as exc:
        raise HTTPException(status_code=422, detail=f"CSV could not be parsed: {exc}") from exc
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="CSV needs a header row")
    headers = {str(header or "").strip().lower().replace(" ", "_") for header in reader.fieldnames}
    text_column = next((name for name in ("text", "report", "message", "description", "body", "original_text") if name in headers), None)
    if not text_column:
        raise HTTPException(status_code=422, detail="CSV needs a text, report, message, description, body, or original_text column")

    rows: list[ReportImportRow] = []
    for line_number, raw_row in enumerate(reader, start=2):
        normalized = {str(key or "").strip().lower().replace(" ", "_"): (value.strip() if isinstance(value, str) else value)
                      for key, value in raw_row.items()}
        text = normalized.get(text_column)
        if not text:
            # Ignore fully blank trailing lines, reject partially populated rows.
            if not any(value not in (None, "") for value in normalized.values()):
                continue
            raise HTTPException(status_code=422, detail=f"CSV row {line_number}: report text is required")
        payload: dict[str, Any] = {"text": text}
        aliases = {
            "source_type": ("source_type", "source"),
            "source_name": ("source_name", "reporter", "channel"),
            "reported_at": ("reported_at", "timestamp", "time"),
            "location_name": ("location_name", "location", "place"),
            "latitude": ("latitude", "lat"),
            "longitude": ("longitude", "lon", "lng"),
            "location_precision": ("location_precision",),
            "disaster_type": ("disaster_type", "type"),
            "needs": ("needs", "resource_needs"),
            "people_affected": ("people_affected", "people", "affected_count"),
            "threat_level": ("threat_level",),
            "time_criticality": ("time_criticality",),
            "vulnerability_level": ("vulnerability_level",),
            "hazard_escalation": ("hazard_escalation",),
            "access_difficulty": ("access_difficulty",),
            "is_firsthand": ("is_firsthand", "firsthand"),
            "independence_confirmed": ("independence_confirmed",),
        }
        for output_key, names in aliases.items():
            value = next((normalized.get(name) for name in names if normalized.get(name) not in (None, "")), None)
            if value is None:
                continue
            if output_key == "needs":
                payload[output_key] = [part.strip() for part in value.replace(";", "|").replace(",", "|").split("|") if part.strip()]
            elif output_key in {"is_firsthand", "independence_confirmed"}:
                payload[output_key] = value.lower() in {"1", "true", "yes", "y"}
            else:
                payload[output_key] = value
        if payload.get("latitude") is not None and payload.get("location_precision") in (None, "unknown", "unresolved"):
            payload["location_precision"] = "approximate"
        try:
            rows.append(ReportImportRow.model_validate(payload))
        except ValidationError as exc:
            detail = "; ".join(error.get("msg", "invalid value") for error in exc.errors())
            raise HTTPException(status_code=422, detail=f"CSV row {line_number}: {detail}") from exc
        if len(rows) > 500:
            raise HTTPException(status_code=413, detail="CSV contains more than 500 reports")
    if not rows:
        raise HTTPException(status_code=422, detail="CSV contains no report rows")
    return rows


async def _import_rows_from_request(request: Request) -> list[ReportImportRow]:
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON request body") from exc
        items = body.get("reports") if isinstance(body, dict) else body
        if not isinstance(items, list) or not items:
            raise HTTPException(status_code=422, detail="JSON import body must contain a non-empty reports array")
        if len(items) > 500:
            raise HTTPException(status_code=413, detail="A maximum of 500 reports can be imported at once")
        rows = []
        for index, item in enumerate(items, start=1):
            try:
                rows.append(ReportImportRow.model_validate(item))
            except ValidationError as exc:
                detail = "; ".join(error.get("msg", "invalid value") for error in exc.errors())
                raise HTTPException(status_code=422, detail=f"Report {index}: {detail}") from exc
        return rows
    try:
        raw = (await request.body()).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="CSV must be UTF-8 encoded") from exc
    if not raw.strip():
        raise HTTPException(status_code=422, detail="CSV is empty")
    return _csv_rows(raw)


def _preview_row(row: ReportImportRow, index: int | None = None) -> dict[str, Any]:
    values = _merge_extracted(row.text, row)
    if index is not None:
        values["row"] = index
    from .scoring import score_urgency
    return {
        "row": index,
        "original_text": row.text,
        "source_type": row.source_type,
        "source_name": row.source_name,
        "is_firsthand": row.is_firsthand,
        "independence_confirmed": row.independence_confirmed,
        "extracted": values,
        "urgency": score_urgency(values),
        "warnings": values.get("warnings", []),
    }


def _active_incidents(db: Session) -> list[Incident]:
    return db.scalars(
        select(Incident).options(selectinload(Incident.reports).selectinload(Report.source))
        .where(Incident.status.not_in(["merged", "resolved", "rejected"]))
    ).all()


def _coverage_gaps(db: Session) -> list[dict[str, Any]]:
    areas = db.scalars(select(CoverageRecord)).all()
    incidents = db.scalars(select(Incident).where(Incident.status != "merged")).all()
    return identify_reporting_gaps(areas, incidents)


@app.get("/api/health", response_model=HealthResponse)
def health():
    return {"status": "ok", "mode": "local decision-support prototype", "database": "sqlite" if DATABASE_URL.startswith("sqlite") else "configured", "simulation_data": True}


@app.get("/api/dashboard", response_model=DashboardResponse)
def dashboard(db: Session = Depends(get_db)):
    incidents = _active_incidents(db)
    queue = sorted(incidents, key=lambda item: (effective_priority(item), item.updated_at), reverse=True)
    gaps = _coverage_gaps(db)
    distribution = {label: 0 for label in ("critical", "high", "elevated", "routine")}
    for incident in incidents:
        score = effective_priority(incident)
        label = "critical" if score >= 80 else "high" if score >= 60 else "elevated" if score >= 35 else "routine"
        distribution[label] += 1
    recent = sorted(
        db.scalars(select(Incident).where(Incident.status != "merged")).all(),
        key=lambda item: item.updated_at,
        reverse=True,
    )[:6]
    return {
        "simulation_data": True,
        "active_incidents": len(incidents),
        "high_urgency_incidents": sum(1 for item in incidents if item.urgency_score >= 60),
        "awaiting_verification": sum(1 for item in incidents if item.status in {"unverified", "needs_info"}),
        "reporting_gaps": len(gaps),
        "priority_distribution": [{"label": label.title(), "count": count} for label, count in distribution.items()],
        "priority_queue": [incident_summary(item) for item in queue[:6]],
        "map_incidents": [incident_summary(item) for item in incidents],
        "recent_updates": [incident_summary(item) for item in recent],
        "gap_preview": gaps[:4],
    }


@app.get("/api/incidents", response_model=IncidentListResponse)
def list_incidents(
    search: str | None = Query(default=None, max_length=200),
    disaster_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    urgency: str | None = None,
    since_hours: int | None = Query(default=None, ge=1, le=24 * 365),
    sort_by: str = Query(default="updated_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(Incident).options(selectinload(Incident.reports).selectinload(Report.source))
    if disaster_type:
        query = query.where(Incident.disaster_type == disaster_type.lower())
    if status_filter:
        query = query.where(Incident.status == status_filter.lower())
    if search:
        like = f"%{search.strip()}%"
        query = query.outerjoin(Report).where(or_(Incident.title.ilike(like), Incident.location_name.ilike(like), Report.original_text.ilike(like))).distinct()
    items = db.scalars(query).all()
    if since_hours:
        cutoff = utcnow() - timedelta(hours=since_hours)
        items = [item for item in items if (item.last_reported_at or item.updated_at) >= cutoff]
    if urgency:
        threshold_map = {"critical": (80, 101), "high": (60, 80), "elevated": (35, 60), "routine": (0, 35)}
        thresholds = threshold_map.get(urgency.lower())
        if not thresholds:
            raise HTTPException(status_code=422, detail="urgency must be critical, high, elevated, or routine")
        low, high = thresholds
        items = [item for item in items if low <= item.urgency_score < high]
    sort_fields = {
        "updated_at": lambda item: item.updated_at or datetime.min,
        "last_reported_at": lambda item: item.last_reported_at or datetime.min,
        "urgency_score": lambda item: item.urgency_score,
        "priority_score": lambda item: effective_priority(item),
        "confidence_score": lambda item: item.confidence_score,
        "disaster_type": lambda item: item.disaster_type,
        "status": lambda item: item.status,
        "title": lambda item: item.title.lower(),
    }
    if sort_by not in sort_fields:
        raise HTTPException(status_code=422, detail=f"Unsupported sort_by value: {sort_by}")
    items.sort(key=sort_fields[sort_by], reverse=sort_order == "desc")
    total = len(items)
    page = items[offset:offset + limit]
    return {"items": [incident_summary(item) for item in page], "total": total, "limit": limit, "offset": offset}


@app.post("/api/incidents", status_code=status.HTTP_201_CREATED, response_model=IncidentDetailResponse)
def create_incident(payload: IncidentCreate, db: Session = Depends(get_db)):
    incident, candidates = _create_incident(db, payload)
    db.commit()
    db.refresh(incident)
    detail = incident_detail(db, incident)
    detail["new_duplicate_candidates"] = candidates
    return detail


@app.get("/api/incidents/{incident_id}", response_model=IncidentDetailResponse)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    return incident_detail(db, _not_found_incident(db, incident_id))


@app.patch("/api/incidents/{incident_id}", response_model=IncidentDetailResponse)
def patch_incident(incident_id: int, payload: IncidentPatch, db: Session = Depends(get_db)):
    incident = _not_found_incident(db, incident_id)
    if incident.status == "merged":
        raise HTTPException(status_code=409, detail="Merged incidents are read-only")
    coordinate_fields = {"latitude", "longitude"}
    if payload.model_fields_set & coordinate_fields and not coordinate_fields.issubset(payload.model_fields_set):
        raise HTTPException(status_code=422, detail="Update latitude and longitude together; do not leave half a coordinate pair")
    old_values = {}
    updated_values = {}
    for key in payload.model_fields_set:
        value = getattr(payload, key)
        if key == "needs":
            old = parse_json(incident.needs_json, [])
            old_values[key] = old
            incident.needs_json = json.dumps(value or [])
            updated_values[key] = value or []
        else:
            old_values[key] = getattr(incident, key)
            setattr(incident, key, value)
            updated_values[key] = value
    if payload.latitude is None and "latitude" in payload.model_fields_set and payload.longitude is None and "longitude" in payload.model_fields_set:
        incident.location_precision = payload.location_precision or "unresolved"
    if not payload.model_fields_set:
        raise HTTPException(status_code=422, detail="Provide at least one field to update")
    recalculate_incident(db, incident)
    db.add(IncidentHistory(incident_id=incident.id, kind="details", old_value=json.dumps(old_values, default=str),
                           new_value=json.dumps(updated_values, default=str), reason="Coordinator edited incident details."))
    make_audit(db, incident_id=incident.id, entity_type="incident", entity_id=incident.id,
               action="details_updated", details={"fields": sorted(payload.model_fields_set)})
    db.commit()
    return incident_detail(db, incident)


@app.post("/api/incidents/{incident_id}/verify", response_model=IncidentDetailResponse)
def verify_incident(incident_id: int, payload: VerifyRequest, db: Session = Depends(get_db)):
    incident = _not_found_incident(db, incident_id)
    if incident.status in {"merged", "resolved"}:
        raise HTTPException(status_code=409, detail=f"Cannot verify an incident in {incident.status} status")
    old_status = incident.status
    incident.status = payload.action
    db.add(VerificationRecord(incident_id=incident.id, action=payload.action, coordinator=payload.coordinator, note=payload.note))
    db.add(IncidentHistory(incident_id=incident.id, kind="status", old_value=old_status, new_value=payload.action,
                           reason=payload.note or "Coordinator review." , coordinator=payload.coordinator))
    recalculate_incident(db, incident)
    make_audit(db, incident_id=incident.id, entity_type="incident", entity_id=incident.id,
               action=f"verification_{payload.action}", actor=payload.coordinator, details={"note": payload.note})
    db.commit()
    return incident_detail(db, incident)


@app.post("/api/incidents/{incident_id}/resolve", response_model=IncidentDetailResponse)
def resolve_incident(incident_id: int, payload: ResolveRequest, db: Session = Depends(get_db)):
    incident = _not_found_incident(db, incident_id)
    if incident.status == "merged":
        raise HTTPException(status_code=409, detail="A merged incident cannot be resolved independently")
    old_status = incident.status
    incident.status = "resolved"
    db.add(IncidentHistory(incident_id=incident.id, kind="status", old_value=old_status, new_value="resolved",
                           reason=payload.reason, coordinator=payload.coordinator))
    recalculate_incident(db, incident)
    make_audit(db, incident_id=incident.id, entity_type="incident", entity_id=incident.id,
               action="incident_resolved", actor=payload.coordinator, details={"reason": payload.reason})
    db.commit()
    return incident_detail(db, incident)


@app.post("/api/incidents/{incident_id}/priority", response_model=IncidentDetailResponse)
@app.patch("/api/incidents/{incident_id}/priority", response_model=IncidentDetailResponse)
def override_priority(incident_id: int, payload: PriorityRequest, db: Session = Depends(get_db)):
    incident = _not_found_incident(db, incident_id)
    if incident.status == "merged":
        raise HTTPException(status_code=409, detail="Merged incidents are read-only")
    old = effective_priority(incident)
    incident.human_priority_override = payload.priority
    incident.priority_override_reason = payload.reason
    incident.updated_at = utcnow()
    db.add(IncidentHistory(incident_id=incident.id, kind="priority", old_value=str(old), new_value=str(payload.priority),
                           reason=payload.reason, coordinator=payload.coordinator))
    make_audit(db, incident_id=incident.id, entity_type="incident", entity_id=incident.id,
               action="priority_overridden", actor=payload.coordinator,
               details={"previous_priority": old, "priority": payload.priority, "reason": payload.reason})
    db.commit()
    return incident_detail(db, incident)


@app.post("/api/incidents/{incident_id}/notes", status_code=status.HTTP_201_CREATED)
def add_note(incident_id: int, payload: NoteCreate, db: Session = Depends(get_db)):
    incident = _not_found_incident(db, incident_id)
    note = CoordinatorNote(incident_id=incident.id, coordinator=payload.coordinator, note=payload.note)
    db.add(note)
    db.flush()
    make_audit(db, incident_id=incident.id, entity_type="incident", entity_id=incident.id,
               action="coordinator_note_added", actor=payload.coordinator, details={"note_id": note.id})
    db.commit()
    return {"id": note.id, "incident_id": incident.id, "coordinator": note.coordinator, "note": note.note, "created_at": note.created_at}


@app.post("/api/reports/preview", response_model=ReportPreviewResponse)
def preview_report(payload: ReportPreviewRequest):
    extracted = extract_report(payload.text)
    from .scoring import score_urgency
    urgency = score_urgency(extracted)
    return {
        "original_text": payload.text,
        "source_type": payload.source_type,
        "source_name": payload.source_name,
        "extracted": extracted,
        "urgency": urgency,
        "evidence_note": "Evidence confidence is assessed separately after saving; this preview is not a probability or verification.",
        "simulation_data": False,
    }


@app.post("/api/reports/preview-csv")
async def preview_csv(request: Request):
    try:
        raw = (await request.body()).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="CSV must be UTF-8 encoded") from exc
    rows = _csv_rows(raw)
    return {"count": len(rows), "items": [_preview_row(row, index + 2) for index, row in enumerate(rows)], "simulation_data": False}


@app.post("/api/reports/import", status_code=status.HTTP_201_CREATED, response_model=ReportImportResponse)
async def import_reports(request: Request, db: Session = Depends(get_db)):
    rows = await _import_rows_from_request(request)
    created: list[Incident] = []
    candidates: list[dict[str, Any]] = []
    for row in rows:
        incident, found = _create_incident(db, row)
        created.append(incident)
        candidates.extend(found)
    db.commit()
    for incident in created:
        db.refresh(incident)
    return {
        "imported": len(created),
        "items": [incident_summary(item) for item in created],
        "possible_duplicates": candidates,
        "note": "Reports were preserved as original records. Similarity candidates were not merged.",
        "simulation_data": False,
    }


@app.post("/api/reports/{report_id}/confirm-duplicate")
def confirm_duplicate(report_id: int, payload: ConfirmDuplicateRequest, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Original report not found")
    source_incident = db.get(Incident, report.incident_id)
    target = db.get(Incident, payload.target_incident_id)
    if not source_incident or not target:
        raise HTTPException(status_code=404, detail="Incident not found")
    if source_incident.id == target.id:
        raise HTTPException(status_code=422, detail="A report cannot be merged into its own incident")
    first, second = sorted([source_incident.id, target.id])
    link = db.scalar(select(DuplicateLink).where(DuplicateLink.incident_a_id == first, DuplicateLink.incident_b_id == second))
    if not link:
        raise HTTPException(status_code=404, detail="No suspected duplicate relationship exists for these incidents")
    if link.status != "possible":
        raise HTTPException(status_code=409, detail=f"Duplicate candidate has already been reviewed as {link.status}")
    if target.status in {"merged", "resolved", "rejected"}:
        raise HTTPException(status_code=409, detail=f"Cannot merge into an incident in {target.status} status")
    if source_incident.status in {"merged", "resolved", "rejected"}:
        raise HTTPException(status_code=409, detail=f"Cannot merge a report from an incident in {source_incident.status} status")

    # Move source fields only when useful; do not sum counts for reports of the same event.
    before = source_incident.status
    if target.disaster_type == "unknown":
        target.disaster_type = source_incident.disaster_type
    if not target.location_name and source_incident.location_name:
        target.location_name = source_incident.location_name
    if target.latitude is None and source_incident.latitude is not None:
        target.latitude, target.longitude = source_incident.latitude, source_incident.longitude
        target.location_precision = source_incident.location_precision
    primary_needs = parse_json(target.needs_json, [])
    target.needs_json = json.dumps(list(dict.fromkeys(primary_needs + parse_json(source_incident.needs_json, []))))
    if target.people_affected is None:
        target.people_affected = source_incident.people_affected
    elif source_incident.people_affected is not None:
        target.people_affected = max(target.people_affected, source_incident.people_affected)
    threat_rank = {"unknown": 0, "none": 1, "possible": 2, "serious": 3, "immediate": 4}
    if threat_rank.get(source_incident.threat_level, 0) > threat_rank.get(target.threat_level, 0):
        target.threat_level = source_incident.threat_level
    for key in ("time_criticality", "vulnerability_level", "hazard_escalation", "access_difficulty"):
        source_value, target_value = getattr(source_incident, key), getattr(target, key)
        if source_value is not None:
            setattr(target, key, source_value if target_value is None else max(source_value, target_value))

    source_reports = db.scalars(select(Report).where(Report.incident_id == source_incident.id)).all()
    for source_report in source_reports:
        source_report.incident_id = target.id
    source_incident.status = "merged"
    source_incident.merged_into_id = target.id
    link.status = "confirmed"
    link.confirmed_by = payload.coordinator
    link.coordinator_note = payload.note
    db.add(IncidentHistory(incident_id=target.id, kind="duplicate_merge", old_value=None,
                           new_value=f"Merged incident {source_incident.id}", reason=payload.note or "Coordinator confirmed suspected duplicate.", coordinator=payload.coordinator))
    db.add(IncidentHistory(incident_id=source_incident.id, kind="duplicate_merge", old_value=before,
                           new_value="merged", reason=f"Merged into incident {target.id} after coordinator confirmation.", coordinator=payload.coordinator))
    # SessionLocal disables autoflush; persist FK moves before querying the target report set.
    db.flush()
    recalculate_incident(db, target)
    recalculate_incident(db, source_incident)
    make_audit(db, incident_id=target.id, entity_type="incident", entity_id=target.id,
               action="duplicate_confirmed_and_merged", actor=payload.coordinator,
               details={"merged_incident_id": source_incident.id, "report_id": report.id, "note": payload.note})
    db.commit()
    return {"merged": True, "primary": incident_detail(db, target), "archived_incident_id": source_incident.id,
            "preserved_report_count": len(target.reports)}


@app.post("/api/reports/{report_id}/mark-separate")
def mark_separate(report_id: int, payload: MarkSeparateRequest, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Original report not found")
    source_id = report.incident_id
    first, second = sorted([source_id, payload.target_incident_id])
    link = db.scalar(select(DuplicateLink).where(DuplicateLink.incident_a_id == first, DuplicateLink.incident_b_id == second))
    if not link:
        raise HTTPException(status_code=404, detail="No suspected duplicate relationship exists for these incidents")
    if link.status != "possible":
        raise HTTPException(status_code=409, detail=f"Duplicate candidate has already been reviewed as {link.status}")
    link.status = "separate"
    link.confirmed_by = payload.coordinator
    link.coordinator_note = payload.note
    make_audit(db, incident_id=source_id, entity_type="duplicate_relationship", entity_id=link.id,
               action="duplicate_marked_separate", actor=payload.coordinator,
               details={"other_incident_id": payload.target_incident_id, "note": payload.note})
    db.commit()
    return {"relationship_id": link.id, "status": link.status, "coordinator": link.confirmed_by}


@app.get("/api/coverage-gaps", response_model=CoverageGapsResponse)
def coverage_gaps(db: Session = Depends(get_db)):
    areas = db.scalars(select(CoverageRecord)).all()
    incidents = db.scalars(select(Incident).where(Incident.status != "merged")).all()
    gaps = identify_reporting_gaps(areas, incidents)
    return {
        "simulation_data": any(item["synthetic"] for item in gaps) or any(area.synthetic for area in areas),
        "note": "A flagged area indicates an information gap, not a confirmed incident or a safe/unsafe finding.",
        "review_window_hours": 12,
        "flagged_count": len(gaps),
        "areas": gaps,
    }


@app.get("/api/analytics", response_model=AnalyticsResponse)
def analytics(db: Session = Depends(get_db)):
    incidents = _active_incidents(db)
    urgency_distribution = {label: 0 for label in ("critical", "high", "elevated", "routine")}
    by_type: dict[str, int] = {}
    for incident in incidents:
        score = incident.urgency_score
        label = "critical" if score >= 80 else "high" if score >= 60 else "elevated" if score >= 35 else "routine"
        urgency_distribution[label] += 1
        by_type[incident.disaster_type] = by_type.get(incident.disaster_type, 0) + 1
    return {
        "active_incidents": len(incidents),
        "urgency_distribution": [{"label": key.title(), "count": value} for key, value in urgency_distribution.items()],
        "disaster_type_distribution": [{"label": key.title(), "count": value} for key, value in sorted(by_type.items())],
        "simulation_data": True,
    }


@app.get("/api/audit-log", response_model=AuditLogResponse)
def audit_log(
    incident_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(AuditLog)
    count_query = select(func.count()).select_from(AuditLog)
    if incident_id:
        query = query.where(AuditLog.incident_id == incident_id)
        count_query = count_query.where(AuditLog.incident_id == incident_id)
    total = db.scalar(count_query) or 0
    rows = db.scalars(query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)).all()
    return {
        "items": [{
            "id": row.id,
            "incident_id": row.incident_id,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "action": row.action,
            "actor": row.actor,
            "details": parse_json(row.details_json, {}),
            "created_at": row.created_at,
        } for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def _resource_item(r: ResourceInventory) -> dict[str, Any]:
    available = max(0, (r.quantity or 0) - r.allocated_quantity) if r.quantity is not None else None
    return {
        "id": r.id,
        "area_name": r.area_name,
        "resource_type": r.resource_type,
        "quantity": r.quantity,
        "allocated_quantity": r.allocated_quantity,
        "available_quantity": available,
        "availability_status": r.availability_status,
        "updated_by": r.updated_by,
        "updated_at": r.updated_at,
        "demo_key": r.demo_key,
    }


@app.get("/api/resources", response_model=list[ResourceItem])
def list_resources(db: Session = Depends(get_db)):
    resources = db.scalars(select(ResourceInventory).order_by(ResourceInventory.resource_type)).all()
    return [_resource_item(r) for r in resources]


@app.post("/api/resources", response_model=ResourceItem, status_code=status.HTTP_201_CREATED)
def create_resource(payload: ResourceCreate, db: Session = Depends(get_db)):
    r = ResourceInventory(
        area_name=payload.area_name,
        resource_type=payload.resource_type.strip(),
        quantity=payload.quantity,
        allocated_quantity=0,
        availability_status=payload.availability_status,
        updated_by=payload.updated_by or "Coordinator",
    )
    db.add(r)
    db.flush()
    make_audit(
        db,
        incident_id=None,
        entity_type="resource",
        entity_id=r.id,
        action="resource_created",
        actor=r.updated_by or "Coordinator",
        details={"resource_type": r.resource_type, "quantity": r.quantity, "area_name": r.area_name},
    )
    db.commit()
    db.refresh(r)
    return _resource_item(r)


@app.patch("/api/resources/{resource_id}", response_model=ResourceItem)
def update_resource(resource_id: int, payload: ResourceUpdate, db: Session = Depends(get_db)):
    r = db.get(ResourceInventory, resource_id)
    if not r:
        raise HTTPException(status_code=404, detail="Resource not found")
    if payload.area_name is not None:
        r.area_name = payload.area_name
    if payload.quantity is not None:
        if payload.quantity < r.allocated_quantity:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot reduce total quantity ({payload.quantity}) below current allocated quantity ({r.allocated_quantity})",
            )
        r.quantity = payload.quantity
    if payload.availability_status is not None:
        r.availability_status = payload.availability_status
    if payload.updated_by:
        r.updated_by = payload.updated_by
    r.updated_at = utcnow()
    make_audit(
        db,
        incident_id=None,
        entity_type="resource",
        entity_id=r.id,
        action="resource_updated",
        actor=payload.updated_by or "Coordinator",
        details={"fields": sorted(payload.model_fields_set)},
    )
    db.commit()
    db.refresh(r)
    return _resource_item(r)


@app.post("/api/resources/allocate", response_model=AllocationItem, status_code=status.HTTP_201_CREATED)
def allocate_resource(payload: AllocationCreate, db: Session = Depends(get_db)):
    incident = db.get(Incident, payload.incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.status in {"merged", "resolved", "rejected"}:
        raise HTTPException(status_code=409, detail=f"Cannot allocate resources to an incident in {incident.status} status")

    resource = db.get(ResourceInventory, payload.resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found in inventory")

    available = max(0, (resource.quantity or 0) - resource.allocated_quantity) if resource.quantity is not None else 0
    if resource.quantity is not None and payload.allocated_quantity > available:
        raise HTTPException(
            status_code=422,
            detail=f"Requested allocation ({payload.allocated_quantity}) exceeds available quantity ({available})",
        )

    allocation = ResourceAllocation(
        incident_id=incident.id,
        resource_id=resource.id,
        allocated_quantity=payload.allocated_quantity,
        coordinator=payload.coordinator,
        note=payload.note,
        status="approved",
    )
    db.add(allocation)
    resource.allocated_quantity += payload.allocated_quantity
    if resource.quantity is not None and resource.allocated_quantity >= resource.quantity:
        resource.availability_status = "exhausted"
    elif resource.availability_status == "exhausted":
        resource.availability_status = "limited"

    db.add(IncidentHistory(
        incident_id=incident.id,
        kind="resource_allocation",
        old_value=None,
        new_value=f"{payload.allocated_quantity} x {resource.resource_type}",
        reason=payload.note or "Coordinator approved resource allocation.",
        coordinator=payload.coordinator,
    ))

    make_audit(
        db,
        incident_id=incident.id,
        entity_type="resource_allocation",
        entity_id=resource.id,
        action="resource_allocated",
        actor=payload.coordinator,
        details={
            "resource_id": resource.id,
            "resource_type": resource.resource_type,
            "quantity": payload.allocated_quantity,
            "incident_id": incident.id,
            "note": payload.note,
        },
    )
    db.commit()
    db.refresh(allocation)
    return {
        "id": allocation.id,
        "incident_id": incident.id,
        "incident_title": incident.title,
        "resource_id": resource.id,
        "resource_type": resource.resource_type,
        "area_name": resource.area_name,
        "allocated_quantity": allocation.allocated_quantity,
        "coordinator": allocation.coordinator,
        "note": allocation.note,
        "status": allocation.status,
        "created_at": allocation.created_at,
    }


@app.delete("/api/resources/allocate/{allocation_id}", status_code=status.HTTP_200_OK)
def release_allocation(allocation_id: int, coordinator: str = Query(default="Coordinator"), db: Session = Depends(get_db)):
    allocation = db.get(ResourceAllocation, allocation_id)
    if not allocation:
        raise HTTPException(status_code=404, detail="Allocation record not found")
    resource = db.get(ResourceInventory, allocation.resource_id)
    if resource:
        resource.allocated_quantity = max(0, resource.allocated_quantity - allocation.allocated_quantity)
        if resource.quantity is not None and resource.allocated_quantity < resource.quantity and resource.availability_status == "exhausted":
            resource.availability_status = "available"

    incident_id = allocation.incident_id
    qty = allocation.allocated_quantity
    res_type = resource.resource_type if resource else "resource"

    db.add(IncidentHistory(
        incident_id=incident_id,
        kind="resource_allocation_released",
        old_value=f"{qty} x {res_type}",
        new_value="released",
        reason="Coordinator released allocated resources.",
        coordinator=coordinator,
    ))

    make_audit(
        db,
        incident_id=incident_id,
        entity_type="resource_allocation",
        entity_id=allocation.id,
        action="resource_allocation_released",
        actor=coordinator,
        details={"released_quantity": qty, "resource_id": allocation.resource_id},
    )
    db.delete(allocation)
    db.commit()
    return {"released": True, "allocation_id": allocation_id}


@app.post("/api/demo/reset", status_code=status.HTTP_200_OK)
def reset_demo(db: Session = Depends(get_db)):
    from .seed import seed_demo_data
    added = seed_demo_data(db, reset_demo=True)
    make_audit(
        db,
        incident_id=None,
        entity_type="system",
        entity_id="demo_data",
        action="demo_reset",
        actor="Coordinator",
        details={"reseeded_count": added},
    )
    db.commit()
    return {"reset": True, "reseeded_count": added, "note": "Demonstration records safely reset. User-created records were preserved."}
