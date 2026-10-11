import { useCallback, useEffect, useState } from 'react';
import {
  Activity, AlertTriangle, Check, ChevronDown, Clock3, FileText, GitMerge, MapPin,
  MessageSquareText, Pencil, ShieldCheck, X,
} from 'lucide-react';
import { api } from '../api.js';
import { StatusBadge, UrgencyBadge } from './StatusBadge.jsx';
import { useToast } from './ToastProvider.jsx';

function formatDate(value) {
  if (!value) return 'Unknown';
  return new Date(value).toLocaleString();
}

function numOrNull(value) {
  if (value === '' || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export default function IncidentDrawer({ incidentId, onClose, onChanged }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [coordinator, setCoordinator] = useState('Coordinator');
  const [reviewNote, setReviewNote] = useState('');
  const [noteText, setNoteText] = useState('');
  const [priority, setPriority] = useState(0);
  const [priorityReason, setPriorityReason] = useState('');
  const [allocResourceId, setAllocResourceId] = useState('');
  const [allocQty, setAllocQty] = useState(1);
  const [allocNote, setAllocNote] = useState('');
  const showToast = useToast();

  const load = useCallback(async () => {
    if (!incidentId) return;
    setLoading(true);
    try {
      const data = await api(`/api/incidents/${incidentId}`);
      setDetail(data);
      setPriority(data.priority_score ?? data.urgency_score ?? 0);
      setEditForm({
        title: data.title || '',
        disaster_type: data.disaster_type || 'unknown',
        location_name: data.location_name || '',
        latitude: data.latitude ?? '',
        longitude: data.longitude ?? '',
        location_precision: data.location_precision || 'unknown',
        people_affected: data.people_affected ?? '',
        needs: (data.needs || []).join(', '),
        threat_level: data.threat_level || 'unknown',
        time_criticality: data.time_criticality ?? '',
        vulnerability_level: data.vulnerability_level ?? '',
        hazard_escalation: data.hazard_escalation ?? '',
        access_difficulty: data.access_difficulty ?? '',
      });
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [incidentId, showToast]);

  useEffect(() => { load(); }, [load]);

  if (!incidentId) return null;

  async function withBusy(action, successMessage, refresh = true) {
    setBusy(true);
    try {
      const result = await action();
      if (result && result.primary) setDetail(result.primary);
      else if (result && result.id && result.urgency_score !== undefined) setDetail(result);
      if (successMessage) showToast(successMessage);
      if (refresh) await load();
      onChanged?.();
      return result;
    } catch (error) {
      showToast(error.message, 'error');
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function review(action) {
    if (action === 'rejected' && !window.confirm('Reject this report? The original report will be retained in the decision log.')) return;
    await withBusy(() => api(`/api/incidents/${incidentId}/verify`, {
      method: 'POST', body: JSON.stringify({ action, coordinator, note: reviewNote || null }),
    }), action === 'needs_info' ? 'More information requested.' : `Incident marked ${action.replace('_', ' ')}.`);
    setReviewNote('');
  }

  async function resolve() {
    if (!window.confirm('Mark this incident resolved? This records a human coordinator decision.')) return;
    const reason = window.prompt('Resolution reason (required):', 'Coordinator confirmed the simulated exercise is complete.');
    if (!reason || reason.trim().length < 3) return;
    await withBusy(() => api(`/api/incidents/${incidentId}/resolve`, {
      method: 'POST', body: JSON.stringify({ coordinator, reason }),
    }), 'Incident marked resolved.');
  }

  async function savePriority(event) {
    event.preventDefault();
    if (priorityReason.trim().length < 5) {
      showToast('Add a reason of at least five characters for the priority override.', 'error');
      return;
    }
    if (!window.confirm('Save a human priority override? The rule-based urgency score will remain visible.')) return;
    await withBusy(() => api(`/api/incidents/${incidentId}/priority`, {
      method: 'POST', body: JSON.stringify({ priority: Number(priority), reason: priorityReason, coordinator }),
    }), 'Human priority override saved.');
    setPriorityReason('');
  }

  async function saveEdit(event) {
    event.preventDefault();
    const lat = numOrNull(editForm.latitude);
    const lon = numOrNull(editForm.longitude);
    if ((lat === null) !== (lon === null)) {
      showToast('Enter both coordinates or leave both blank.', 'error');
      return;
    }
    const update = {
      title: editForm.title,
      disaster_type: editForm.disaster_type,
      location_name: editForm.location_name || null,
      latitude: lat,
      longitude: lon,
      location_precision: editForm.location_precision,
      people_affected: numOrNull(editForm.people_affected),
      needs: editForm.needs.split(',').map((part) => part.trim()).filter(Boolean),
      threat_level: editForm.threat_level,
      time_criticality: numOrNull(editForm.time_criticality),
      vulnerability_level: numOrNull(editForm.vulnerability_level),
      hazard_escalation: numOrNull(editForm.hazard_escalation),
      access_difficulty: numOrNull(editForm.access_difficulty),
    };
    await withBusy(() => api(`/api/incidents/${incidentId}`, { method: 'PATCH', body: JSON.stringify(update) }), 'Incident details updated.');
    setEditing(false);
  }

  async function addNote(event) {
    event.preventDefault();
    if (noteText.trim().length < 2) return;
    const result = await withBusy(() => api(`/api/incidents/${incidentId}/notes`, {
      method: 'POST', body: JSON.stringify({ note: noteText, coordinator }),
    }), 'Coordinator note saved.');
    if (result) setNoteText('');
  }

  async function confirmDuplicate(duplicate) {
    if (!window.confirm(`Merge the report from incident #${duplicate.other_incident_id} into this incident? Original report text and provenance will be retained.`)) return;
    await withBusy(() => api(`/api/reports/${duplicate.candidate_report_id}/confirm-duplicate`, {
      method: 'POST', body: JSON.stringify({ target_incident_id: incidentId, coordinator, note: duplicate.reason }),
    }), 'Duplicate confirmed and reports consolidated.');
  }

  async function markSeparate(duplicate) {
    await withBusy(() => api(`/api/reports/${duplicate.candidate_report_id}/mark-separate`, {
      method: 'POST', body: JSON.stringify({ target_incident_id: incidentId, coordinator, note: 'Coordinator reviewed and marked as a separate incident.' }),
    }), 'Reports marked as separate incidents.');
  }

  async function handleAllocate(event) {
    event.preventDefault();
    if (!allocResourceId || allocQty < 1) return;
    await withBusy(() => api('/api/resources/allocate', {
      method: 'POST',
      body: JSON.stringify({
        incident_id: incidentId,
        resource_id: Number(allocResourceId),
        allocated_quantity: Number(allocQty),
        coordinator,
        note: allocNote || null,
      }),
    }), 'Resource allocation approved and logged.');
    setAllocResourceId('');
    setAllocQty(1);
    setAllocNote('');
  }

  async function handleRelease(allocationId) {
    if (!window.confirm('Release this resource allocation back to available inventory?')) return;
    await withBusy(() => api(`/api/resources/allocate/${allocationId}?coordinator=${encodeURIComponent(coordinator)}`, {
      method: 'DELETE',
    }), 'Allocation released back to inventory.');
  }

  const setField = (key, value) => setEditForm((current) => ({ ...current, [key]: value }));
  const readOnlyDecision = detail?.status === 'merged' || detail?.status === 'resolved';
  const humanDecisionCopy = {
    unverified: 'No coordinator verification decision recorded yet.',
    needs_info: 'Coordinator requested additional information.',
    verified: 'A coordinator marked this report verified.',
    monitoring: 'A coordinator recorded a monitoring status.',
    rejected: 'A coordinator rejected this report.',
    resolved: 'A coordinator marked this incident resolved.',
    merged: `This record was merged into incident #${detail?.merged_into_id || '—'}.`,
  }[detail?.status] || 'Coordinator status not recorded.';

  return (
    <div className="drawer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <aside className="incident-drawer" role="dialog" aria-modal="true" aria-label="Incident details">
        <div className="drawer-header">
          <div><div className="drawer-kicker">INCIDENT RECORD {detail?.id ? `#${detail.id}` : ''}</div><h2>{loading ? 'Loading incident…' : (detail?.title || 'Incident details')}</h2></div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close details"><X size={20} /></button>
        </div>
        {loading && <div className="drawer-loading"><span className="spinner" /> Loading record and history…</div>}
        {!loading && detail && (
          <div className="drawer-scroll">
            {detail.status === 'merged' && <div className="merged-banner"><GitMerge size={16} /> This record was merged into incident #{detail.merged_into_id || '—'}. Its original report remains preserved with the active record.</div>}
            <div className="drawer-summary-row"><StatusBadge status={detail.status} /><UrgencyBadge score={detail.priority_score} level={detail.priority_level} /><span className="confidence-inline">Evidence {detail.confidence_score}/100</span></div>
            <div className="human-caveat"><AlertTriangle size={15} /><span>Decision support only. Low confidence does not lower urgency. No dispatch is authorized here.</span></div>

            <section className="drawer-section score-grid">
              <div className="score-panel score-urgency"><div className="score-label"><Activity size={15} /> RULE-BASED URGENCY</div><strong>{detail.urgency_score}<small>/100</small></strong><span>{detail.urgency_level} · independent of evidence confidence</span></div>
              <div className="score-panel score-confidence"><div className="score-label"><ShieldCheck size={15} /> EVIDENCE QUALITY</div><strong>{detail.confidence_score}<small>/100</small></strong><span>Heuristic evidence score; not a probability</span></div>
            </section>

            <section className="drawer-section">
              <div className="section-heading"><h3>Incident information</h3>{detail.status !== 'merged' && <button className="small-action" onClick={() => setEditing((value) => !value)}><Pencil size={14} /> {editing ? 'Cancel edit' : 'Edit'}</button>}</div>
              {!editing ? (
                <div className="detail-grid">
                  <div><span>Disaster type</span><strong className="capitalize">{detail.disaster_type || 'Unknown'}</strong></div>
                  <div><span>Location</span><strong>{detail.location_name || 'Unresolved'}</strong></div>
                  <div><span>Location precision</span><strong className="capitalize">{detail.location_precision}{detail.latitude != null ? ` · ${detail.latitude.toFixed(3)}, ${detail.longitude.toFixed(3)}` : ''}</strong></div>
                  <div><span>People affected</span><strong>{detail.people_affected ?? 'Unknown'}</strong></div>
                  <div><span>Latest report</span><strong>{formatDate(detail.last_reported_at)}</strong></div>
                  <div><span>Original reports</span><strong>{detail.report_count}</strong></div>
                  <div className="detail-wide"><span>Reported needs</span><strong>{detail.needs?.length ? detail.needs.join(', ') : 'None specified'}</strong></div>
                  {detail.human_priority_override !== null && detail.human_priority_override !== undefined && <div className="detail-wide override-note"><span>Human priority override</span><strong>{detail.human_priority_override}/100 — {detail.priority_override_reason}</strong></div>}
                </div>
              ) : (
                <form className="edit-form" onSubmit={saveEdit}>
                  <label>Incident title<input value={editForm.title} onChange={(e) => setField('title', e.target.value)} maxLength={200} required /></label>
                  <div className="form-grid-two">
                    <label>Disaster type<select value={editForm.disaster_type} onChange={(e) => setField('disaster_type', e.target.value)}><option value="unknown">Unknown</option><option value="flood">Flood</option><option value="earthquake">Earthquake</option><option value="landslide">Landslide</option><option value="fire">Fire</option><option value="storm">Storm</option><option value="other">Other</option></select></label>
                    <label>People affected<input type="number" min="0" value={editForm.people_affected} onChange={(e) => setField('people_affected', e.target.value)} placeholder="Unknown" /></label>
                    <label>Location name<input value={editForm.location_name} onChange={(e) => setField('location_name', e.target.value)} placeholder="Leave blank if unresolved" /></label>
                    <label>Location precision<select value={editForm.location_precision} onChange={(e) => setField('location_precision', e.target.value)}><option value="unknown">Unknown</option><option value="unresolved">Unresolved</option><option value="approximate">Approximate</option><option value="verified">Verified</option></select></label>
                    <label>Latitude<input type="number" step="any" value={editForm.latitude} onChange={(e) => setField('latitude', e.target.value)} placeholder="Optional; do not guess" /></label>
                    <label>Longitude<input type="number" step="any" value={editForm.longitude} onChange={(e) => setField('longitude', e.target.value)} placeholder="Optional; do not guess" /></label>
                    <label>Threat to life<select value={editForm.threat_level} onChange={(e) => setField('threat_level', e.target.value)}><option value="unknown">Unknown</option><option value="none">No threat reported</option><option value="possible">Possible</option><option value="serious">Serious</option><option value="immediate">Immediate</option></select></label>
                    <label>Time criticality (0–4)<input type="number" min="0" max="4" value={editForm.time_criticality} onChange={(e) => setField('time_criticality', e.target.value)} placeholder="Unknown" /></label>
                    <label>Vulnerability (0–4)<input type="number" min="0" max="4" value={editForm.vulnerability_level} onChange={(e) => setField('vulnerability_level', e.target.value)} placeholder="Unknown" /></label>
                    <label>Hazard escalation (0–4)<input type="number" min="0" max="4" value={editForm.hazard_escalation} onChange={(e) => setField('hazard_escalation', e.target.value)} placeholder="Unknown" /></label>
                    <label>Access difficulty (0–4)<input type="number" min="0" max="4" value={editForm.access_difficulty} onChange={(e) => setField('access_difficulty', e.target.value)} placeholder="Unknown" /></label>
                    <label className="form-grid-wide">Resource needs, comma separated<input value={editForm.needs} onChange={(e) => setField('needs', e.target.value)} placeholder="Medical assistance, drinking water…" /></label>
                  </div>
                  <div className="button-row"><button className="button button-secondary" type="button" onClick={() => setEditing(false)}>Cancel</button><button className="button button-primary" disabled={busy}>Save details</button></div>
                </form>
              )}
            </section>

            <section className="drawer-section">
              <h3>Why this urgency score?</h3>
              <p className="urgency-summary">{detail.urgency_summary}</p>
              <ul className="reason-list">{(detail.urgency_reasons || []).map((reason, index) => <li key={index}>{reason}</li>)}</ul>
              {detail.human_priority_override !== null && detail.human_priority_override !== undefined && <p className="muted-note">The displayed queue priority reflects a coordinator override; the rule-based score above is unchanged.</p>}
            </section>

            <section className="drawer-section">
              <h3>Evidence confidence explanation</h3>
              <p className="evidence-copy">{detail.confidence_explanation}</p>
            </section>

            <section className="drawer-section recommendation-box">
              <h3><Activity size={16} /> Recommended next step</h3>
              <p>{detail.recommended_action}</p>
              <div className="decision-separation"><span>HUMAN COORDINATOR RECORD</span><strong>{humanDecisionCopy}</strong><small>{detail.human_priority_override !== null && detail.human_priority_override !== undefined ? `Queue priority override: ${detail.human_priority_override}/100 — ${detail.priority_override_reason}` : 'No human queue-priority override is recorded.'}</small></div>

              <div className="resource-list">
                <strong>Resource needs & inventory status</strong>
                {detail.resource_recommendations?.length ? detail.resource_recommendations.map((item, index) => (
                  <div className="resource-row" key={`${item.need}-${index}`}>
                    <div>
                      <strong>{item.resource_type_to_consider}</strong>
                      <small style={{ display: 'block', color: '#718095' }}>Need: {item.need}</small>
                    </div>
                    <span style={{ textAlign: 'right' }}>
                      <span className={`status-pill status-${item.availability === 'available' ? 'verified' : item.availability === 'limited' ? 'monitoring' : 'unverified'}`}>
                        {item.availability}
                      </span>
                      {item.available_quantity !== null && item.available_quantity !== undefined && (
                        <small style={{ display: 'block', color: '#4a5568' }}>{item.available_quantity} available / {item.quantity} total</small>
                      )}
                    </span>
                  </div>
                )) : <p className="muted-note">No explicit resource needs are recorded.</p>}
                <small>Human approval required. No resources are dispatched automatically.</small>
              </div>

              {/* Active allocations for this incident */}
              {detail.allocations?.length > 0 && (
                <div style={{ marginTop: '14px', borderTop: '1px solid #e2e8f0', paddingTop: '10px' }}>
                  <strong style={{ fontSize: '11px', color: '#1a202c', display: 'block', marginBottom: '6px' }}>Active resource allocations ({detail.allocations.length})</strong>
                  {detail.allocations.map((alloc) => (
                    <div key={alloc.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f7fafc', padding: '8px 10px', borderRadius: '6px', marginBottom: '6px', fontSize: '11px' }}>
                      <div>
                        <strong>{alloc.allocated_quantity} x {alloc.resource_type}</strong>
                        <small style={{ display: 'block', color: '#718095' }}>By {alloc.coordinator} {alloc.note ? `· "${alloc.note}"` : ''}</small>
                      </div>
                      {!readOnlyDecision && (
                        <button type="button" className="button button-danger-outline button-small" disabled={busy} onClick={() => handleRelease(alloc.id)}>Release</button>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Coordinator allocation form */}
              {!readOnlyDecision && detail.resource_recommendations?.some((r) => r.resource_id) && (
                <form onSubmit={handleAllocate} style={{ marginTop: '12px', background: '#edf2f7', padding: '10px', borderRadius: '6px' }}>
                  <strong style={{ fontSize: '11px', display: 'block', marginBottom: '6px' }}>Allocate inventory to incident</strong>
                  <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: '8px', marginBottom: '8px' }}>
                    <label style={{ fontSize: '10px' }}>Resource
                      <select value={allocResourceId} onChange={(e) => setAllocResourceId(e.target.value)} required style={{ width: '100%', fontSize: '11px', padding: '4px' }}>
                        <option value="">Select resource…</option>
                        {detail.resource_recommendations.filter((r) => r.resource_id).map((r) => (
                          <option key={r.resource_id} value={r.resource_id} disabled={r.available_quantity === 0}>
                            {r.resource_type_to_consider} ({r.available_quantity ?? 0} available)
                          </option>
                        ))}
                      </select>
                    </label>
                    <label style={{ fontSize: '10px' }}>Quantity
                      <input type="number" min="1" max="1000" value={allocQty} onChange={(e) => setAllocQty(e.target.value)} required style={{ width: '100%', fontSize: '11px', padding: '4px' }} />
                    </label>
                  </div>
                  <input type="text" placeholder="Allocation note / mission details…" value={allocNote} onChange={(e) => setAllocNote(e.target.value)} style={{ width: '100%', fontSize: '11px', padding: '4px', marginBottom: '8px' }} />
                  <button className="button button-primary button-small" disabled={busy || !allocResourceId}>Approve allocation</button>
                </form>
              )}
            </section>

            <section className="drawer-section">
              <h3><FileText size={16} /> Original reports and provenance</h3>
              {detail.original_reports?.length ? detail.original_reports.map((report) => (
                <details className="report-record" key={report.id}>
                  <summary><span>{report.source_type}{report.source_name ? ` · ${report.source_name}` : ''}</span><ChevronDown size={15} /><small>{formatDate(report.reported_at)}</small></summary>
                  <blockquote>{report.original_text}</blockquote>
                  <div className="report-flags">{report.is_firsthand ? 'Firsthand source' : 'Firsthand status unknown'} · {report.independence_confirmed ? 'independence confirmed' : 'independence not confirmed'}</div>
                </details>
              )) : <p className="muted-note">No attached original reports.</p>}
            </section>

            {detail.possible_duplicates?.length > 0 && <section className="drawer-section">
              <h3><GitMerge size={16} /> Duplicate review</h3>
              {detail.possible_duplicates.map((duplicate) => (
                <div className="duplicate-row" key={duplicate.relationship_id}>
                  <div><strong>#{duplicate.other_incident_id} · {duplicate.other_title}</strong><span>{duplicate.similarity}% text similarity · {duplicate.status}</span><p>{duplicate.reason}</p></div>
                  {duplicate.status === 'possible' && duplicate.candidate_report_id && !readOnlyDecision && !['merged', 'resolved', 'rejected'].includes(duplicate.other_status) && <div className="button-row compact"><button className="button button-primary button-small" disabled={busy} onClick={() => confirmDuplicate(duplicate)}>Confirm same</button><button className="button button-secondary button-small" disabled={busy} onClick={() => markSeparate(duplicate)}>Keep separate</button></div>}
                </div>
              ))}
              <p className="muted-note">Similarity is a review cue only. No report is discarded or merged automatically.</p>
            </section>}

            <section className="drawer-section">
              <h3><ShieldCheck size={16} /> Human review</h3>
              <label className="inline-label">Coordinator<input value={coordinator} onChange={(e) => setCoordinator(e.target.value)} maxLength={120} /></label>
              <label className="stacked-label">Review note<textarea rows="2" value={reviewNote} onChange={(e) => setReviewNote(e.target.value)} placeholder="Record what was checked or what information is needed…" /></label>
              <div className="button-row wrap-actions">
                <button className="button button-secondary" disabled={busy || readOnlyDecision || detail.status === 'verified'} onClick={() => review('verified')}><Check size={15} /> Verify</button>
                <button className="button button-secondary" disabled={busy || readOnlyDecision} onClick={() => review('needs_info')}><MessageSquareText size={15} /> Request info</button>
                <button className="button button-danger-outline" disabled={busy || readOnlyDecision} onClick={() => review('rejected')}>Reject</button>
                {detail.status !== 'resolved' && detail.status !== 'merged' && <button className="button button-secondary" disabled={busy} onClick={resolve}><Check size={15} /> Resolve</button>}
              </div>
            </section>

            <section className="drawer-section">
              <h3>Human priority override</h3>
              <p className="muted-note">Set a queue priority only with a reason. This does not change the explainable urgency calculation.</p>
              <form className="priority-form" onSubmit={savePriority}>
                <label>Queue priority <strong>{priority}</strong><input type="range" min="0" max="100" value={priority} disabled={readOnlyDecision} onChange={(e) => setPriority(Number(e.target.value))} /></label>
                <label className="stacked-label">Mandatory reason<textarea rows="2" value={priorityReason} disabled={readOnlyDecision} onChange={(e) => setPriorityReason(e.target.value)} placeholder="Why should the coordinator queue differ from the rule score?" /></label>
                <button className="button button-primary" disabled={busy || readOnlyDecision}>Save override</button>
              </form>
            </section>

            <section className="drawer-section">
              <h3><MessageSquareText size={16} /> Coordinator notes</h3>
              <form className="note-form" onSubmit={addNote}><textarea rows="2" value={noteText} onChange={(e) => setNoteText(e.target.value)} placeholder="Add a timestamped note to the decision record…" /><button className="button button-secondary" disabled={busy || noteText.trim().length < 2}>Add note</button></form>
              <div className="note-list">{detail.notes?.length ? detail.notes.map((note) => <div className="note-item" key={note.id}><p>{note.note}</p><span>{note.coordinator} · {formatDate(note.created_at)}</span></div>) : <p className="muted-note">No coordinator notes recorded.</p>}</div>
            </section>

            {(detail.verification_history?.length > 0 || detail.history?.length > 0) && <section className="drawer-section">
              <h3><Clock3 size={16} /> Verification & change history</h3>
              <div className="history-list">
                {[...(detail.verification_history || []).map((item) => ({ ...item, kind: `verification · ${item.action}`, reason: item.note })), ...(detail.history || []).map((item) => ({ ...item, kind: item.kind.replaceAll('_', ' '), note: item.reason }))]
                  .sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).map((item, index) => (
                    <div className="history-item" key={`${item.kind}-${item.id}-${index}`}><span className="history-marker" /><div><strong>{item.kind}</strong><p>{item.reason || item.note || item.new_value || 'Record updated.'}</p><small>{item.coordinator || 'Coordinator'} · {formatDate(item.created_at)}</small></div></div>
                  ))}
              </div>
            </section>}
          </div>
        )}
      </aside>
    </div>
  );
}
