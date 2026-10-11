"""Small, local, deterministic report extraction. Unknown fields stay unknown."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


NEED_KEYWORDS = {
    "medical assistance": ("medical", "medic", "injur", "ambulance", "first aid"),
    "rescue support": ("rescue", "trapped", "stranded", "search and rescue"),
    "rescue boat": ("boat", "boat rescue", "floodwater", "water rescue"),
    "evacuation support": ("evacuat", "move people", "leave now"),
    "drinking water": ("drinking water", "clean water", "potable water"),
    "food": ("food", "meals", "ration"),
    "shelter": ("shelter", "temporary housing", "roof collapsed"),
    "communications": ("no signal", "network down", "radio", "connectivity"),
}


def _parse_location(text: str) -> str | None:
    # Deliberately only accept title-cased candidate names; coordinates are never inferred.
    pattern = re.compile(
        r"\b(?:near|at|in|by|around)\s+((?:[A-Z][a-zA-Z0-9'’-]*)(?:[\s-]+(?:[A-Z][a-zA-Z0-9'’-]*|(?:Footbridge|Bridge|Village|Ward|Road|School|Market|Colony|Camp|Weir|Ghat|Hill|Valley)))?)"
    )
    for match in pattern.finditer(text):
        candidate = re.sub(r"\s+", " ", match.group(1)).strip(" ,.;:")
        if candidate.lower() not in {"least", "the", "need", "urgent", "total", "approximately", "around"}:
            return candidate[:240]
    return None


def _extract_people_count(lower: str) -> int | None:
    count_words = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
        "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
        "nineteen": 19, "twenty": 20, "couple": 2, "dozen": 12, "a dozen": 12,
    }
    match = re.search(
        r"\b(\d{1,7}|a dozen|dozen|couple|zero|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\s+"
        r"(?:people|persons|residents|children|workers|patients)\b",
        lower,
    )
    if not match:
        return None
    token = match.group(1)
    return int(token) if token.isdigit() else count_words[token]


def extract_report(text: str) -> dict[str, Any]:
    clean = " ".join((text or "").split())
    lower = clean.lower()
    disaster_type = "unknown"
    for kind, words in (
        ("flood", ("flood", "floodwater", "water rising", "river overflow", "inundat")),
        ("earthquake", ("earthquake", "quake", "aftershock", "tremor", "shaking")),
        ("landslide", ("landslide", "mudslide", "slope collapsed")),
        ("fire", ("fire", "smoke", "burning")),
        ("storm", ("cyclone", "storm", "high wind", "lightning")),
    ):
        if any(word in lower for word in words):
            disaster_type = kind
            break

    location = _parse_location(clean)
    people_affected = _extract_people_count(lower)

    needs = [label for label, keywords in NEED_KEYWORDS.items() if any(word in lower for word in keywords)]
    # Avoid treating a water hazard alone as a confirmed request for drinking water.
    if "drinking water" in needs and not any(word in lower for word in ("drinking water", "clean water", "potable water")):
        needs.remove("drinking water")

    immediate = ("trapped", "injured", "missing", "collapsed on", "swept away", "life threatening", "people inside")
    serious = ("rising", "rapidly spreading", "water entering", "building collapsed", "wall collapsed", "road washed", "active fire")
    possible = ("damage", "crack", "evacuate", "flood", "shaking", "unsafe")
    if any(word in lower for word in immediate):
        threat_level = "immediate"
        time_criticality = 4
    elif any(word in lower for word in serious):
        threat_level = "serious"
        time_criticality = 3
    elif any(word in lower for word in possible):
        threat_level = "possible"
        time_criticality = 2
    else:
        threat_level = "unknown"
        time_criticality = None

    vulnerability_level = 4 if any(word in lower for word in ("infant", "child", "children", "elderly", "disabled", "pregnant")) else None
    hazard_escalation = 4 if any(word in lower for word in ("rising fast", "rising rapidly", "rises rapidly", "rapidly rising", "rising quickly", "keeps rising", "spreading", "continuing to rise", "ongoing aftershock")) else (2 if "rising" in lower else None)
    access_difficulty = 4 if any(word in lower for word in ("road blocked", "bridge blocked", "cut off", "inaccessible", "roads washed")) else None
    precision = "approximate" if location else "unresolved"
    warnings = []
    if not location:
        warnings.append("Location not safely resolved from the text; leave it unresolved until a coordinator or authorized source confirms it.")
    if people_affected is None:
        warnings.append("Affected-person count is unknown; no count was inferred.")

    return {
        "title": f"{disaster_type.title()} report — {location}" if location and disaster_type != "unknown" else (f"{disaster_type.title()} report" if disaster_type != "unknown" else "Unclassified emergency report"),
        "disaster_type": disaster_type,
        "location_name": location,
        "latitude": None,
        "longitude": None,
        "location_precision": precision,
        "needs": needs,
        "people_affected": people_affected,
        "threat_level": threat_level,
        "time_criticality": time_criticality,
        "vulnerability_level": vulnerability_level,
        "hazard_escalation": hazard_escalation,
        "access_difficulty": access_difficulty,
        "warnings": warnings,
    }
