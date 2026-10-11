"""Duplicate-candidate scoring only; this module never performs an automatic merge."""
from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
from math import asin, cos, radians, sin, sqrt
from typing import Any, Iterable

try:
    from rapidfuzz.fuzz import token_set_ratio
except ImportError:  # lightweight stdlib fallback for minimal environments
    token_set_ratio = None


def text_similarity(left: str, right: str) -> float:
    a, b = " ".join((left or "").lower().split()), " ".join((right or "").lower().split())
    if not a or not b:
        return 0.0
    if token_set_ratio:
        return float(token_set_ratio(a, b))
    return round(100 * SequenceMatcher(None, a, b).ratio(), 1)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_km = 6371.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * earth_km * asin(sqrt(a))


def _naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def find_possible_duplicate_candidates(
    new_report: dict[str, Any],
    existing: Iterable[dict[str, Any]],
    *,
    threshold: float = 78.0,
    max_hours: float = 72.0,
    max_distance_km: float = 15.0,
) -> list[dict[str, Any]]:
    """Return ranked candidates. A high score is a prompt for human review, not a merge."""
    candidates: list[dict[str, Any]] = []
    new_time = _naive_utc(new_report.get("reported_at"))
    for item in existing:
        if item.get("status") in {"merged", "rejected", "resolved"}:
            continue
        new_type, old_type = new_report.get("disaster_type"), item.get("disaster_type")
        if new_type not in {None, "unknown"} and old_type not in {None, "unknown", new_type}:
            continue
        old_time = _naive_utc(item.get("reported_at") or item.get("last_reported_at"))
        if new_time and old_time and abs((new_time - old_time).total_seconds()) > max_hours * 3600:
            continue
        distance = None
        if all(new_report.get(key) is not None for key in ("latitude", "longitude")) and all(item.get(key) is not None for key in ("latitude", "longitude")):
            distance = haversine_km(float(new_report["latitude"]), float(new_report["longitude"]), float(item["latitude"]), float(item["longitude"]))
            if distance > max_distance_km:
                continue
        similarity = text_similarity(new_report.get("text", ""), item.get("text", ""))
        if similarity < threshold:
            continue
        reasons = [f"Text similarity is {similarity:.0f}%."]
        if new_type == old_type and new_type not in {None, "unknown"}:
            reasons.append(f"Both are classified as {new_type}.")
        if distance is not None:
            reasons.append(f"Known coordinates are about {distance:.1f} km apart.")
        if new_time and old_time:
            hours = abs((new_time - old_time).total_seconds()) / 3600
            reasons.append(f"Reports are {hours:.1f} hours apart.")
        candidates.append({
            "incident_id": item.get("incident_id", item.get("id")),
            "similarity": round(similarity, 1),
            "reason": " ".join(reasons),
        })
    return sorted(candidates, key=lambda row: row["similarity"], reverse=True)
