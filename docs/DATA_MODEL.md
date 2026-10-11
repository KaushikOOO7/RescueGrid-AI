# Data model and retention

SQLite is the default local store. SQLAlchemy initializes missing tables on startup without dropping existing tables or rows. A production migration workflow is outside this prototype; back up SQLite before schema changes.

- `incidents`: structured incident state, coordinates/precision, urgency inputs and result, independent evidence score, human status and queue override, timestamps, merge pointer, optional `demo_key`.
- `original_reports`: immutable source text, reported time, source link, extraction snapshot, firsthand and coordinator-confirmed independence flags, optional `demo_key`. A confirmed duplicate merge moves the report association to the primary incident; it does not delete or rewrite the original text/source.
- `report_sources`: source type and label for provenance.
- `possible_duplicate_relationships`: incident pair, similarity, reason, possible/confirmed/separate review status, reviewer and note.
- `incident_verifications`: verify/reject/request-information decisions.
- `incident_status_priority_history`: prior/current status, priority, detail and merge changes with actor and reason.
- `coordinator_notes`: timestamped coordinator notes.
- `reporting_coverage_records`: monitored cells, exposure label, last confirmation, connectivity/access observations, synthetic flag and optional demo key.
- `resource_inventory`: optional explicitly entered resource type, quantity and availability status. No availability is assumed when absent.
- `audit_log`: actions, actor, entity and JSON details.

### Demo data safety

Each seeded incident/report/coverage/source uses a demo tag. Normal startup seeds only an entirely empty incident database. `python -m app.seed --reset-demo` removes only explicitly demo-tagged rows and dependent demo-linked records, retaining untagged user incidents. There is no in-app destructive reset button.
