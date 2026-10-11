"""Deterministic, explainable prototype scoring; not an operational standard."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

URGENCY_WEIGHTS = {
    "threat_to_life": 35,
    "time_criticality": 20,
    "people_affected": 15,
    "vulnerability": 10,
    "hazard_escalation": 10,
    "access_difficulty": 10,
}
THREAT_POINTS = {"unknown": None, "none": 0, "possible": 1, "serious": 3, "immediate": 4}


def _level(value: int | None, maximum: int) -> int:
    if value is None:
        return 0
    return round((max(0, min(4, int(value))) / 4) * maximum)


def people_points(people: int | None, maximum: int | None = None) -> int:
    """Piecewise, capped count mapping; unknown is zero points, not evidence of zero need."""
    maximum = URGENCY_WEIGHTS["people_affected"] if maximum is None else maximum
    if people is None or people <= 0:
        return 0
    if people <= 5:
        base_points = 3
    elif people <= 25:
        base_points = 6
    elif people <= 100:
        base_points = 10
    else:
        base_points = 15
    return round((base_points / 15) * maximum)


def urgency_label(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 35:
        return "elevated"
    return "routine"


def score_urgency(values: dict[str, Any]) -> dict[str, Any]:
    """Score urgency independently of source count, confidence, or message popularity."""
    parts: list[tuple[str, int, int]] = []
    missing: list[str] = []
    components: dict[str, int] = {}

    threat = values.get("threat_level") or "unknown"
    threat_level = THREAT_POINTS.get(str(threat), None)
    threat_weight = URGENCY_WEIGHTS["threat_to_life"]
    if threat_level is None:
        missing.append("Threat-to-life level is unknown; no threat points were assigned.")
        threat_points = 0
    else:
        threat_points = _level(threat_level, threat_weight)
        parts.append(("Threat to life", threat_points, threat_weight))
    components["threat_to_life"] = threat_points

    time_value = values.get("time_criticality")
    time_weight = URGENCY_WEIGHTS["time_criticality"]
    if time_value is None:
        missing.append("Time criticality is unknown; no time points were assigned.")
        time_points = 0
    else:
        time_points = _level(time_value, time_weight)
        parts.append(("Time criticality", time_points, time_weight))
    components["time_criticality"] = time_points

    people = values.get("people_affected")
    people_weight = URGENCY_WEIGHTS["people_affected"]
    if people is None:
        missing.append("Number of people affected is unknown; no affected-person points were assigned.")
        affected_points = 0
    else:
        affected_points = people_points(int(people), people_weight)
        parts.append(("People affected", affected_points, people_weight))
    components["people_affected"] = affected_points

    for key, label, output_key in (
        ("vulnerability_level", "Vulnerability of affected people", "vulnerability"),
        ("hazard_escalation", "Escalating hazard conditions", "hazard_escalation"),
        ("access_difficulty", "Difficulty of access or rescue", "access_difficulty"),
    ):
        value = values.get(key)
        weight = URGENCY_WEIGHTS[output_key]
        if value is None:
            missing.append(f"{label} is unknown; no points were assigned.")
            points = 0
        else:
            points = _level(value, weight)
            parts.append((label, points, weight))
        components[output_key] = points

    score = max(0, min(100, sum(components.values())))
    reasons = [f"{name}: {points}/{maximum} points." for name, points, maximum in parts]
    reasons.extend(missing)
    if not parts:
        reasons.insert(0, "No urgency inputs were available; this score is not evidence that the area is safe.")
    return {"score": score, "level": urgency_label(score), "reasons": reasons, "components": components}


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def assess_confidence(
    values: dict[str, Any],
    reports: Iterable[Any],
    *,
    status: str = "unverified",
    latest_reported_at: datetime | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evidence quality heuristic, deliberately separate from incident urgency."""
    report_list = list(reports)
    score = 0
    parts: list[str] = []
    limits: list[str] = []

    verified = status == "verified"
    has_authorized_firsthand = any(bool(getattr(report, "is_firsthand", False)) for report in report_list)
    if verified:
        score += 30
        parts.append("Coordinator verification: +30.")
    elif has_authorized_firsthand:
        score += 18
        parts.append("Firsthand/authorized field source is recorded: +18.")
    else:
        parts.append("No firsthand or authorized verification is recorded: +0.")

    independent_sources = {
        (getattr(getattr(report, "source", None), "source_name", None) or f"source-{getattr(report, 'source_id', getattr(report, 'id', id(report)))}").strip().lower()
        for report in report_list
        if bool(getattr(report, "independence_confirmed", False))
    }
    if len(independent_sources) >= 2:
        score += 25
        parts.append("At least two sources are explicitly marked independent by a coordinator: +25.")
    elif len(independent_sources) == 1:
        parts.append("Only one independently confirmed source is recorded; corroboration points require two: +0.")
    else:
        parts.append("Independent corroboration is not confirmed: +0.")

    precision = values.get("location_precision", "unknown")
    if precision == "verified":
        score += 20
        parts.append("Location is marked verified: +20.")
    elif precision == "approximate":
        score += 10
        parts.append("Location is approximate: +10.")
    else:
        parts.append("Location is unresolved or unknown: +0.")

    latest = _normalize_datetime(latest_reported_at)
    current = _normalize_datetime(now) or datetime.now(timezone.utc).replace(tzinfo=None)
    if latest is None:
        freshness = 0
        parts.append("Report freshness cannot be assessed: +0.")
    else:
        age_hours = max(0.0, (current - latest).total_seconds() / 3600)
        if age_hours <= 2:
            freshness = 15
        elif age_hours <= 8:
            freshness = 12
        elif age_hours <= 24:
            freshness = 8
        else:
            freshness = 2
        parts.append(f"Report freshness ({age_hours:.1f} hours old): +{freshness}.")
    score += freshness

    if len(independent_sources) >= 2:
        independent_reports = [report for report in report_list if bool(getattr(report, "independence_confirmed", False))]
        types = {
            str(getattr(report, "extracted_disaster_type", "") or "").lower()
            for report in independent_reports
            if getattr(report, "extracted_disaster_type", None) not in {None, "", "unknown"}
        }
        locations = {
            str(getattr(report, "extracted_location", "") or "").strip().lower()
            for report in independent_reports
            if getattr(report, "extracted_location", None)
        }
        if not types and not locations:
            parts.append("No comparable type/location details are available across independent sources: +0.")
        elif len(types) <= 1 and len(locations) <= 1:
            score += 10
            parts.append("Details across explicitly independent sources are consistent: +10.")
        else:
            parts.append("Some independent source details conflict; coordinator review is needed: +0.")
    elif report_list:
        score += 3 if len(report_list) == 1 else 0
        if len(report_list) == 1:
            parts.append("A single report has no cross-source consistency check: +3.")
        else:
            parts.append("Cross-source consistency was not scored because independence is not confirmed: +0.")
    else:
        parts.append("No original reports are attached: +0.")

    limits.append("Potentially correlated copies do not add corroboration unless independence is explicitly confirmed.")
    limits.append("This is a heuristic evidence-quality score, not a calibrated probability or a measure of urgency.")
    return {
        "score": max(0, min(100, int(score))),
        "explanation": " ".join(parts + limits),
        "factors": parts,
        "limitations": limits,
    }
