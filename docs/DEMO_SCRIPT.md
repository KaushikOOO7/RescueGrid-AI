# 4–6 minute judge demo script

## 1. Open with the safety principle (30 sec)

“RescueGrid is a local decision-support prototype, not a dispatch system. The central design choice is that urgency and evidence confidence are separate. An uncertain urgent report stays visible and asks for verification; silence is never treated as proof of safety.”

Point out the synthetic demo badge and the warnings on the Overview.

## 2. Show the operational picture (45 sec)

- Explain that active, high-urgency, awaiting-verification, and reporting-gap metrics come from SQLite records.
- Open the queue’s single-report flood incident and note that it has a high rule-based urgency but limited evidence confidence.
- Show that the map contains only explicitly supplied synthetic coordinates; the unresolved earthquake report stays off map.

## 3. Ingest a report (60–90 sec)

- Go to **Report intake**, choose the sample flood report, and click **Extract for review**.
- Review location, needs, people, threat and urgency fields. Point out that missing values remain “Unknown” and no coordinate is fabricated.
- Save the incident. Mention that the frontend only reports success after the API saves the incident and original report in SQLite.
- Optional: preview `data/sample_reports.csv` and import after reviewing the extracted rows.

## 4. Review a duplicate candidate (45–60 sec)

- Open the seeded Kestrel Footbridge report and its possible duplicate.
- Show the similarity reason and both source reports.
- Select **Confirm same** only for the synthetic demo. Explain that no candidate is automatically merged and that report provenance stays attached after confirmation. **Keep separate** is also available.

## 5. Make a human decision (60 sec)

- Verify or request more information on a record.
- Add a coordinator note.
- If useful, demonstrate a queue-priority override and emphasize that a reason is mandatory and the original rule score remains visible.
- Open the Decision log to show the actor/action history.

## 6. Discuss reporting gaps and limitations (45 sec)

- Open **Reporting-gap monitor**. Explain the stale synthetic confirmation and explicit connectivity/access notes.
- Say: “This is a prompt to collect information, not a claim that an incident exists or that the area is safe.”
- Close with limitations: deterministic keyword extraction, unvalidated weights, no live feeds/geocoder/inventory/routes/dispatch, and OSM tiles need internet.

## Claims to avoid

Do not describe scores as probabilities, claim measured accuracy, claim that the app monitors real communities, or imply that a recommendation dispatches a resource. The demo records are fictional and the prototype has not been validated for operations.
