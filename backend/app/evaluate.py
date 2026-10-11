"""Print a small deterministic walkthrough of the synthetic scoring examples."""
from __future__ import annotations

from .scoring import score_urgency

CASES = [
    ("High urgency, single uncertain report", {
        "threat_level": "immediate", "time_criticality": 4, "people_affected": 6,
        "vulnerability_level": 2, "hazard_escalation": 4, "access_difficulty": 3,
    }),
    ("Damage report with unknown people count", {
        "threat_level": "serious", "time_criticality": 2, "people_affected": None,
        "vulnerability_level": None, "hazard_escalation": 1, "access_difficulty": None,
    }),
    ("Vague report with missing urgency details", {}),
]


def main() -> None:
    print("RescueGrid AI — deterministic synthetic walkthrough")
    print("Illustrative rule outputs only; this is not an accuracy or effectiveness evaluation.\n")
    for name, fields in CASES:
        result = score_urgency(fields)
        print(f"{name}: {result['score']}/100 ({result['level']})")
        print("  " + " | ".join(result["reasons"][:3]))


if __name__ == "__main__":
    main()
