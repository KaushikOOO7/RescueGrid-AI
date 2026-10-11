from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any, Iterable


def _age_hours(value: datetime | None, now: datetime) -> float | None:
    if value is None:
        return None
    if value.tzinfo:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    current = now.astimezone(timezone.utc).replace(tzinfo=None) if now.tzinfo else now
    return max(0.0, (current - value).total_seconds() / 3600)


def _distance_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    p1, p2 = radians(a_lat), radians(b_lat)
    dlat, dlon = radians(b_lat - a_lat), radians(b_lon - a_lon)
    a = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(a))


def identify_reporting_gaps(areas: Iterable[Any], incidents: Iterable[Any], *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Flag information gaps; never creates or implies an incident or a safe area."""
    current = now or datetime.now(timezone.utc)
    incident_list = list(incidents)
    flagged: list[dict[str, Any]] = []
    for area in areas:
        get = (lambda key, default=None: area.get(key, default)) if isinstance(area, dict) else (lambda key, default=None: getattr(area, key, default))
        nearby = []
        lat, lon = get("latitude"), get("longitude")
        if lat is not None and lon is not None:
            for incident in incident_list:
                iget = (lambda key, default=None: incident.get(key, default)) if isinstance(incident, dict) else (lambda key, default=None: getattr(incident, key, default))
                ilat, ilon = iget("latitude"), iget("longitude")
                if ilat is None or ilon is None or iget("status") in {"merged", "rejected"}:
                    continue
                if _distance_km(float(lat), float(lon), float(ilat), float(ilon)) <= 25:
                    nearby.append(incident)
        recent_incidents = [
            i for i in nearby
            if (_age_hours((i.get("last_reported_at") if isinstance(i, dict) else getattr(i, "last_reported_at", None)), current) or 9999) <= 12
        ]
        last_confirmed = get("last_confirmed_at")
        area_age = _age_hours(last_confirmed, current)
        reasons = []
        exposure = str(get("hazard_exposure", "medium")).lower()
        if exposure == "high" and not recent_incidents:
            reasons.append("High-exposure synthetic cell has no recent incident report; absence of reports is not evidence of safety.")
        elif exposure in {"high", "medium"} and not recent_incidents:
            reasons.append("No incident report in the last 12 hours is available for this monitored cell; status is unknown.")
        if area_age is None:
            reasons.append("No field confirmation timestamp is recorded.")
        elif area_age > 12:
            reasons.append(f"Last field confirmation was {area_age:.1f} hours ago (older than the 12-hour prototype review window).")
        if get("connectivity_limited", False):
            reasons.append("Connectivity limitations were explicitly reported; incoming reports may be delayed.")
        if get("access_limited", False):
            reasons.append("Access limitations were explicitly reported; current conditions may be unobserved.")
        if reasons:
            incident_times = [
                (i.get("last_reported_at") if isinstance(i, dict) else getattr(i, "last_reported_at", None))
                for i in nearby
            ]
            timestamps = [stamp for stamp in [last_confirmed, *incident_times] if stamp]
            last_known = max(timestamps) if timestamps else None
            flagged.append({
                "area_name": get("area_name", "Unnamed monitored cell"),
                "latitude": lat,
                "longitude": lon,
                "hazard_exposure": exposure,
                "last_known_info_at": last_known,
                "last_confirmed_at": last_confirmed,
                "connectivity_limited": bool(get("connectivity_limited", False)),
                "access_limited": bool(get("access_limited", False)),
                "synthetic": bool(get("synthetic", True)),
                "reasons": reasons,
                "nearby_incident_count": len(nearby),
            })
    return flagged
