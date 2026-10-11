from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    # Naive UTC is used consistently because SQLite does not preserve timezone data.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (Index("ix_incidents_status_urgency", "status", "urgency_score"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    disaster_type: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    location_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_precision: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    needs_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    people_affected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    threat_level: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    time_criticality: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vulnerability_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hazard_escalation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    access_difficulty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="unverified")
    urgency_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    urgency_level: Mapped[str] = mapped_column(String(24), nullable=False, default="routine")
    urgency_reasons_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_reported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    human_priority_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    merged_into_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    demo_key: Mapped[str | None] = mapped_column(String(80), nullable=True, unique=True)

    reports: Mapped[list["Report"]] = relationship(back_populates="incident", cascade="all, delete-orphan", passive_deletes=True)
    verifications: Mapped[list["VerificationRecord"]] = relationship(back_populates="incident", cascade="all, delete-orphan", passive_deletes=True)
    histories: Mapped[list["IncidentHistory"]] = relationship(back_populates="incident", cascade="all, delete-orphan", passive_deletes=True)
    notes: Mapped[list["CoordinatorNote"]] = relationship(back_populates="incident", cascade="all, delete-orphan", passive_deletes=True)


class ReportSource(Base):
    __tablename__ = "report_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    source_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    reports: Mapped[list["Report"]] = relationship(back_populates="source", passive_deletes=True)


class Report(Base):
    __tablename__ = "original_reports"
    __table_args__ = (Index("ix_reports_incident_reported", "incident_id", "reported_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("report_sources.id", ondelete="SET NULL"), nullable=True)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    extracted_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_firsthand: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    independence_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    demo_key: Mapped[str | None] = mapped_column(String(80), nullable=True, unique=True)

    incident: Mapped[Incident] = relationship(back_populates="reports")
    source: Mapped[ReportSource | None] = relationship(back_populates="reports")


class DuplicateLink(Base):
    __tablename__ = "possible_duplicate_relationships"
    __table_args__ = (UniqueConstraint("incident_a_id", "incident_b_id", name="uq_duplicate_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_a_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    incident_b_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    similarity: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="possible")
    confirmed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    coordinator_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class VerificationRecord(Base):
    __tablename__ = "incident_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    coordinator: Mapped[str] = mapped_column(String(120), nullable=False, default="Coordinator")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    incident: Mapped[Incident] = relationship(back_populates="verifications")


class IncidentHistory(Base):
    __tablename__ = "incident_status_priority_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    coordinator: Mapped[str] = mapped_column(String(120), nullable=False, default="Coordinator")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    incident: Mapped[Incident] = relationship(back_populates="histories")


class CoordinatorNote(Base):
    __tablename__ = "coordinator_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    coordinator: Mapped[str] = mapped_column(String(120), nullable=False, default="Coordinator")
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    incident: Mapped[Incident] = relationship(back_populates="notes")


class CoverageRecord(Base):
    __tablename__ = "reporting_coverage_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    area_name: Mapped[str] = mapped_column(String(160), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    hazard_exposure: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    connectivity_limited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    access_limited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    demo_key: Mapped[str | None] = mapped_column(String(80), nullable=True, unique=True)


class ResourceInventory(Base):
    __tablename__ = "resource_inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    area_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allocated_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    availability_status: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    updated_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    demo_key: Mapped[str | None] = mapped_column(String(80), nullable=True, unique=True)


class ResourceAllocation(Base):
    __tablename__ = "resource_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resource_inventory.id", ondelete="CASCADE"), nullable=False)
    allocated_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    coordinator: Mapped[str] = mapped_column(String(120), nullable=False, default="Coordinator")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="proposed")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    incident: Mapped[Incident] = relationship()
    resource: Mapped[ResourceInventory] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_created", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False, default="Coordinator")
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
