from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.duplicates import find_possible_duplicate_candidates
from app.extraction import extract_report
from app.gaps import identify_reporting_gaps
from app.scoring import assess_confidence, score_urgency


def test_urgency_score_is_bounded_and_max_weights_total_100():
    result = score_urgency({
        "threat_level": "immediate",
        "time_criticality": 4,
        "people_affected": 1000,
        "vulnerability_level": 4,
        "hazard_escalation": 4,
        "access_difficulty": 4,
    })
    assert result["score"] == 100
    assert result["level"] == "critical"
    assert sum(result["components"].values()) == 100


def test_unknown_inputs_are_explicit_and_not_treated_as_safe():
    result = score_urgency({})
    assert 0 <= result["score"] <= 100
    assert any("unknown" in reason.lower() for reason in result["reasons"])
    assert any("not evidence that the area is safe" in reason for reason in result["reasons"])


def test_urgency_and_confidence_are_independent():
    urgency_input = {"threat_level": "immediate", "time_criticality": 4, "people_affected": 6,
                     "vulnerability_level": 2, "hazard_escalation": 4, "access_difficulty": 3}
    urgent_score = score_urgency(urgency_input)["score"]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    one_report = SimpleNamespace(is_firsthand=False, independence_confirmed=False,
                                 source=SimpleNamespace(source_type="sms", source_name="one"),
                                 extracted_disaster_type="flood", extracted_location="Kestrel")
    low = assess_confidence({"location_precision": "approximate"}, [one_report], latest_reported_at=now, now=now)["score"]
    two = [one_report, SimpleNamespace(is_firsthand=True, independence_confirmed=True,
             source=SimpleNamespace(source_type="field", source_name="two"),
             extracted_disaster_type="flood", extracted_location="Kestrel")]
    higher = assess_confidence({"location_precision": "approximate"}, two,
                               latest_reported_at=now, now=now)["score"]
    assert higher > low
    assert score_urgency(urgency_input)["score"] == urgent_score
    # Message count/confidence is deliberately not a score_urgency input.


def test_missing_cross_source_fields_do_not_increase_consistency_confidence():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    reports = [
        SimpleNamespace(is_firsthand=False, independence_confirmed=False, source_id=index,
                        source=SimpleNamespace(source_type="sms", source_name=f"source-{index}"),
                        extracted_disaster_type="unknown", extracted_location=None)
        for index in (1, 2)
    ]
    result = assess_confidence({"location_precision": "unresolved"}, reports,
                               latest_reported_at=now, now=now)
    assert result["score"] == 15  # freshness only; absent details are not treated as agreement
    assert any("independence is not confirmed" in item for item in result["factors"])


def test_duplicate_candidates_are_ranked_but_never_merged_by_detector():
    now = datetime.now(timezone.utc)
    incoming = {"text": "Flood water rising fast near Kestrel Footbridge; six residents trapped and need a rescue boat.",
                "disaster_type": "flood", "reported_at": now, "latitude": 13.10, "longitude": 77.61}
    existing = [{"incident_id": 7, "text": "Six residents are trapped near Kestrel Footbridge as floodwater rises quickly. Boat rescue requested.",
                 "disaster_type": "flood", "last_reported_at": now - timedelta(minutes=20),
                 "latitude": 13.101, "longitude": 77.611, "status": "unverified"}]
    matches = find_possible_duplicate_candidates(incoming, existing, threshold=70)
    assert len(matches) == 1
    assert matches[0]["incident_id"] == 7
    # The pure detector returns candidates only; it has no database merge side effect.
    assert matches[0]["similarity"] >= 70


def test_duplicate_detector_respects_time_and_reliable_coordinate_distance():
    now = datetime.now(timezone.utc)
    incoming = {"text": "Earthquake damage reported at Pineglass School with wall cracks and injuries.",
                "disaster_type": "earthquake", "reported_at": now, "latitude": 12.9, "longitude": 77.5}
    far = {"incident_id": 2, "text": incoming["text"], "disaster_type": "earthquake", "last_reported_at": now,
           "latitude": 19.0, "longitude": 72.0, "status": "unverified"}
    stale = {"incident_id": 3, "text": incoming["text"], "disaster_type": "earthquake",
             "last_reported_at": now - timedelta(days=8), "status": "unverified"}
    assert find_possible_duplicate_candidates(incoming, [far, stale], threshold=50) == []


def test_extractor_reads_simple_spelled_counts_without_guessing_coordinates():
    result = extract_report("Six residents are trapped near Kestrel Footbridge; need a rescue boat.")
    assert result["people_affected"] == 6
    assert result["location_name"] == "Kestrel Footbridge"
    assert result["latitude"] is None and result["longitude"] is None
    assert not any("count is unknown" in warning for warning in result["warnings"])
    escalating = extract_report("Floodwater rises rapidly near Kestrel Footbridge.")
    assert escalating["hazard_escalation"] == 4


def test_uncertain_location_is_not_geocoded_or_guessed():
    result = extract_report("Strong shaking and a wall fell somewhere near the hills. We need shelter.")
    assert result["latitude"] is None and result["longitude"] is None
    assert result["location_name"] is None
    assert result["location_precision"] == "unresolved"
    assert result["warnings"]


def test_reporting_gap_is_warning_not_fabricated_incident():
    now = datetime.now(timezone.utc)
    areas = [{"area_name": "Remote Demo Cell", "latitude": 13.4, "longitude": 77.8,
              "hazard_exposure": "high", "last_confirmed_at": now - timedelta(hours=30),
              "connectivity_limited": True, "access_limited": True, "synthetic": True}]
    gaps = identify_reporting_gaps(areas, [], now=now)
    assert len(gaps) == 1
    assert any("not evidence of safety" in reason for reason in gaps[0]["reasons"])
    assert gaps[0]["nearby_incident_count"] == 0
