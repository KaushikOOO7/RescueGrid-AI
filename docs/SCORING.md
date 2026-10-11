# RescueGrid scoring rules (prototype)

These deterministic rules are transparent demonstration logic, **not an emergency triage standard**. They are not calibrated, tested against outcomes, or validated for operational use. Human coordinators must review records and approve consequential actions.

## Urgency score

The score is `clamp(sum of components, 0, 100)`. Missing values receive zero points **and an explicit unknown explanation**; zero points do not mean “no danger.” The scoring function has no input for report count, social-media popularity, duplicate count, evidence confidence, or source reliability.

| Component | Maximum | Conversion |
|---|---:|---|
| Threat to human life | 35 | `none = 0`, `possible = 1`, `serious = 3`, `immediate = 4`; points are `round(level / 4 × 35)`. `unknown` is missing. |
| Time criticality | 20 | Coordinator/extractor level 0–4; points are `round(level / 4 × 20)`. |
| Number of people affected | 15 | `1–5 → 3`, `6–25 → 6`, `26–100 → 10`, `101+ → 15`. Missing and explicit zero each add zero, but only missing is described as unknown. |
| Vulnerability | 10 | Coordinator/extractor level 0–4; points are `round(level / 4 × 10)`. |
| Escalating hazard conditions | 10 | Level 0–4 using the same proportional conversion. |
| Difficulty of access or rescue | 10 | Level 0–4 using the same proportional conversion. |

Rule-based urgency bands are: `routine` 0–34, `elevated` 35–59, `high` 60–79, and `critical` 80–100. The high-urgency dashboard count uses the **rule-based** score. Queue ordering may use a separate coordinator override.

The maxima are centralized in `URGENCY_WEIGHTS` in `backend/app/scoring.py`. A developer may change these prototype rules there; keep the maxima summing to 100 and update tests/documentation when changing them. Such a change is configuration for the prototype, not validation for operational use.

A human priority override is stored alongside the base urgency score and requires a reason. It changes the effective queue score only; it does not rewrite the algorithmic urgency calculation.

## Evidence confidence (separate heuristic)

Evidence confidence is a separate 0–100 evidence-quality score, not a probability. The current additive factors are:

- Coordinator verification: +30; otherwise an explicitly firsthand field/authorized/official source: +18.
- At least two distinct source labels explicitly marked independent by a coordinator: +25. Suspected copies are not automatically counted as independent corroboration.
- Location precision: unknown/unresolved +0, approximate +10, verified +20.
- Freshness of most recent report: at most 2 hours +15; at most 8 hours +12; at most 24 hours +8; older +2; unavailable +0.
- Source consistency: one report +3 (no cross-source check); two or more reports with consistent extracted type/location +10; conflicting available fields +0.

The result is clamped to 0–100. Its explanation states key evidence limitations. A low-confidence, high-urgency record remains high in the queue and should prompt urgent verification; confidence never reduces urgency.

## Local text extraction

`backend/app/extraction.py` uses deterministic keyword rules. It may identify a disaster category, title-cased location candidate, needs, count, and several urgency inputs. It never assigns coordinates. If a place cannot be safely resolved, location remains unknown/unresolved. Every extracted field can be edited before the incident is saved.

## Duplicate candidates

`backend/app/duplicates.py` uses RapidFuzz `token_set_ratio` (stdlib `SequenceMatcher` fallback) and a configurable default text threshold of 78 (`DUPLICATE_SIMILARITY_THRESHOLD`). Candidates must also pass broad disaster-type compatibility and a 72-hour window when timestamps are available. If both records have coordinates, reliable-coordinate distance must be no more than 15 km. These checks only produce review suggestions. No merge happens without a coordinator POST to the confirmation endpoint.

## Reporting-gap rules

`backend/app/gaps.py` flags synthetic/monitored cells when there is no nearby recent report (12-hour window), field confirmation is missing/stale, or connectivity/access limits were explicitly recorded. Nearby is a 25 km prototype radius where coordinates exist. This indicates an **information gap only**, never an incident and never safety.

## Resources

Need strings can suggest a type of resource to consider (such as medical support, evacuation support, or a rescue boat). Inventory is unknown unless an explicit `ResourceInventory` record exists. The app does not infer availability, safe routes, travel time, or dispatch feasibility.
