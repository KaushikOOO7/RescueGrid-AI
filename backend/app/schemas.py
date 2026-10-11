from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DisasterType = Literal["flood", "earthquake", "landslide", "fire", "storm", "other", "unknown"]
LocationPrecision = Literal["unknown", "unresolved", "approximate", "verified"]
ThreatLevel = Literal["unknown", "none", "possible", "serious", "immediate"]
IncidentStatus = Literal["unverified", "verified", "needs_info", "monitoring", "resolved", "rejected", "merged"]


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_text: str = Field(min_length=5, max_length=5000)
    title: str | None = Field(default=None, max_length=200)
    disaster_type: DisasterType = "unknown"
    location_name: str | None = Field(default=None, max_length=240)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_precision: LocationPrecision = "unknown"
    needs: list[str] = Field(default_factory=list, max_length=20)
    people_affected: int | None = Field(default=None, ge=0, le=10_000_000)
    threat_level: ThreatLevel = "unknown"
    time_criticality: int | None = Field(default=None, ge=0, le=4)
    vulnerability_level: int | None = Field(default=None, ge=0, le=4)
    hazard_escalation: int | None = Field(default=None, ge=0, le=4)
    access_difficulty: int | None = Field(default=None, ge=0, le=4)
    status: Literal["unverified", "needs_info", "monitoring"] = "unverified"
    reported_at: datetime | None = None
    source_type: str = Field(default="manual", min_length=1, max_length=40)
    source_name: str | None = Field(default=None, max_length=160)
    is_firsthand: bool = False
    independence_confirmed: bool = False

    @field_validator("needs")
    @classmethod
    def clean_needs(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip()[:80] for item in value if item and item.strip()))

    @model_validator(mode="after")
    def validate_coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        if self.latitude is not None and self.location_precision not in {"approximate", "verified"}:
            raise ValueError("coordinates require location_precision='approximate' or 'verified'")
        return self


class IncidentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)
    disaster_type: DisasterType | None = None
    location_name: str | None = Field(default=None, max_length=240)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_precision: LocationPrecision | None = None
    needs: list[str] | None = Field(default=None, max_length=20)
    people_affected: int | None = Field(default=None, ge=0, le=10_000_000)
    threat_level: ThreatLevel | None = None
    time_criticality: int | None = Field(default=None, ge=0, le=4)
    vulnerability_level: int | None = Field(default=None, ge=0, le=4)
    hazard_escalation: int | None = Field(default=None, ge=0, le=4)
    access_difficulty: int | None = Field(default=None, ge=0, le=4)

    @model_validator(mode="after")
    def validate_coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            # Explicitly clearing coordinates is allowed only when both are provided as null.
            if self.latitude is None and self.longitude is not None or self.longitude is None and self.latitude is not None:
                raise ValueError("latitude and longitude must be updated together")
        if self.latitude is not None and self.location_precision not in {"approximate", "verified"}:
            raise ValueError("coordinates require location_precision='approximate' or 'verified'")
        return self


class ReportPreviewRequest(BaseModel):
    text: str = Field(min_length=5, max_length=5000)
    source_type: str = Field(default="manual", max_length=40)
    source_name: str | None = Field(default=None, max_length=160)


class VerifyRequest(BaseModel):
    action: Literal["verified", "rejected", "needs_info"]
    coordinator: str = Field(default="Coordinator", min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=2000)


class ResolveRequest(BaseModel):
    coordinator: str = Field(default="Coordinator", min_length=1, max_length=120)
    reason: str = Field(min_length=3, max_length=2000)


class PriorityRequest(BaseModel):
    priority: int = Field(ge=0, le=100)
    reason: str = Field(min_length=5, max_length=2000)
    coordinator: str = Field(default="Coordinator", min_length=1, max_length=120)


class NoteCreate(BaseModel):
    note: str = Field(min_length=2, max_length=4000)
    coordinator: str = Field(default="Coordinator", min_length=1, max_length=120)


class ConfirmDuplicateRequest(BaseModel):
    target_incident_id: int = Field(gt=0)
    coordinator: str = Field(default="Coordinator", min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=1000)


class MarkSeparateRequest(BaseModel):
    target_incident_id: int = Field(gt=0)
    coordinator: str = Field(default="Coordinator", min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=1000)


class ReportImportRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = Field(min_length=5, max_length=5000)
    source_type: str = Field(default="csv", max_length=40)
    source_name: str | None = Field(default=None, max_length=160)
    reported_at: datetime | None = None
    location_name: str | None = Field(default=None, max_length=240)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_precision: LocationPrecision = "unknown"
    disaster_type: DisasterType | None = None
    needs: list[str] | None = None
    people_affected: int | None = Field(default=None, ge=0, le=10_000_000)
    threat_level: ThreatLevel | None = None
    time_criticality: int | None = Field(default=None, ge=0, le=4)
    vulnerability_level: int | None = Field(default=None, ge=0, le=4)
    hazard_escalation: int | None = Field(default=None, ge=0, le=4)
    access_difficulty: int | None = Field(default=None, ge=0, le=4)
    is_firsthand: bool = False
    independence_confirmed: bool = False

    @model_validator(mode="after")
    def validate_coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        if self.latitude is not None and self.location_precision not in {"approximate", "verified"}:
            raise ValueError("coordinates require location_precision='approximate' or 'verified'")
        return self


class IncidentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    disaster_type: str
    location_name: str | None
    latitude: float | None
    longitude: float | None
    location_precision: str
    location_resolved: bool
    needs: list[str]
    people_affected: int | None
    status: str
    urgency_score: int
    urgency_level: str
    urgency_summary: str
    urgency_reasons: list[str]
    priority_score: int
    priority_level: str
    human_priority_override: int | None
    priority_override_reason: str | None
    confidence_score: int
    confidence_explanation: str
    report_count: int
    last_reported_at: datetime | None
    created_at: datetime
    updated_at: datetime
    merged_into_id: int | None


class IncidentListResponse(BaseModel):
    items: list[IncidentSummary]
    total: int
    limit: int
    offset: int


class DistributionItem(BaseModel):
    label: str
    count: int


class CoverageGapItem(BaseModel):
    area_name: str
    latitude: float | None
    longitude: float | None
    hazard_exposure: str
    last_known_info_at: datetime | None
    last_confirmed_at: datetime | None
    connectivity_limited: bool
    access_limited: bool
    synthetic: bool
    reasons: list[str]
    nearby_incident_count: int


class DashboardResponse(BaseModel):
    simulation_data: bool
    active_incidents: int
    high_urgency_incidents: int
    awaiting_verification: int
    reporting_gaps: int
    priority_distribution: list[DistributionItem]
    priority_queue: list[IncidentSummary]
    map_incidents: list[IncidentSummary]
    recent_updates: list[IncidentSummary]
    gap_preview: list[CoverageGapItem]


class IncidentDetailResponse(IncidentSummary):
    threat_level: str
    time_criticality: int | None
    vulnerability_level: int | None
    hazard_escalation: int | None
    access_difficulty: int | None
    original_reports: list[dict[str, Any]]
    verification_history: list[dict[str, Any]]
    history: list[dict[str, Any]]
    notes: list[dict[str, Any]]
    possible_duplicates: list[dict[str, Any]]
    resource_recommendations: list[dict[str, Any]]
    allocations: list[dict[str, Any]] = Field(default_factory=list)
    recommended_action: str
    human_decision: dict[str, Any]
    simulation_data: bool
    new_duplicate_candidates: list[dict[str, Any]] | None = None


class ReportPreviewResponse(BaseModel):
    original_text: str
    source_type: str
    source_name: str | None
    extracted: dict[str, Any]
    urgency: dict[str, Any]
    evidence_note: str
    simulation_data: bool


class ReportImportResponse(BaseModel):
    imported: int
    items: list[IncidentSummary]
    possible_duplicates: list[dict[str, Any]]
    note: str
    simulation_data: bool


class CoverageGapsResponse(BaseModel):
    simulation_data: bool
    note: str
    review_window_hours: int
    flagged_count: int
    areas: list[CoverageGapItem]


class AnalyticsResponse(BaseModel):
    active_incidents: int
    urgency_distribution: list[DistributionItem]
    disaster_type_distribution: list[DistributionItem]
    simulation_data: bool


class AuditLogItem(BaseModel):
    id: int
    incident_id: int | None
    entity_type: str
    entity_id: str
    action: str
    actor: str
    details: dict[str, Any]
    created_at: datetime


class AuditLogResponse(BaseModel):
    items: list[AuditLogItem]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: str
    mode: str
    database: str
    simulation_data: bool


class ResourceItem(BaseModel):
    id: int
    area_name: str | None
    resource_type: str
    quantity: int | None
    allocated_quantity: int
    available_quantity: int | None
    availability_status: str
    updated_by: str | None
    updated_at: datetime
    demo_key: str | None = None


class ResourceCreate(BaseModel):
    area_name: str | None = Field(default=None, max_length=160)
    resource_type: str = Field(min_length=2, max_length=80)
    quantity: int | None = Field(default=None, ge=0, le=100000)
    availability_status: Literal["available", "limited", "exhausted", "in_transit", "unknown"] = "available"
    updated_by: str | None = Field(default="Coordinator", max_length=120)


class ResourceUpdate(BaseModel):
    area_name: str | None = Field(default=None, max_length=160)
    quantity: int | None = Field(default=None, ge=0, le=100000)
    availability_status: Literal["available", "limited", "exhausted", "in_transit", "unknown"] | None = None
    updated_by: str | None = Field(default="Coordinator", max_length=120)


class AllocationCreate(BaseModel):
    incident_id: int
    resource_id: int
    allocated_quantity: int = Field(ge=1, le=10000)
    coordinator: str = Field(default="Coordinator", min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=1000)


class AllocationItem(BaseModel):
    id: int
    incident_id: int
    incident_title: str | None = None
    resource_id: int
    resource_type: str
    area_name: str | None = None
    allocated_quantity: int
    coordinator: str
    note: str | None
    status: str
    created_at: datetime
