import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Clock3, Info, RefreshCw, WifiOff } from 'lucide-react';
import { api, getIncidents } from '../api.js';
import IncidentMap from '../components/IncidentMap.jsx';
import { useToast } from '../components/ToastProvider.jsx';

function formatDate(value) {
  return value ? new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : 'No timestamp recorded';
}

export default function CoveragePage() {
  const [result, setResult] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const showToast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [gaps, records] = await Promise.all([api('/api/coverage-gaps'), getIncidents({ limit: 500 })]);
      setResult(gaps);
      setIncidents(records.items || []);
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="page-content">
      <div className="page-intro page-intro-tight"><div><div className="eyebrow"><span className="eyebrow-dot" /> INFORMATION COVERAGE</div><h2>Reporting-gap monitor</h2><p>Highlight where available information may be stale or limited. A gap is not a fabricated incident or a safety finding.</p></div><button className="button button-secondary" onClick={load} disabled={loading}><RefreshCw size={15} className={loading ? 'spin-icon' : ''} /> Refresh</button></div>
      <div className="gap-principle"><AlertTriangle size={18} /><div><strong>Missing data should trigger a check-in, not a guess.</strong><span>Cells use synthetic demonstration exposure and field-confirmation records; they are not real community monitoring.</span></div></div>
      <div className="coverage-summary-grid"><div className="coverage-summary-card"><span>Flagged cells</span><strong>{result?.flagged_count ?? '—'}</strong><small>Information review needed</small></div><div className="coverage-summary-card"><span>Review window</span><strong>{result?.review_window_hours ?? 12}<small>h</small></strong><small>Prototype freshness threshold</small></div><div className="coverage-summary-card"><span>Located incidents</span><strong>{incidents.filter((i) => i.latitude != null && i.longitude != null).length}</strong><small>Source/coordinator-provided only</small></div><div className="coverage-summary-card"><span>Simulation records</span><strong>{result?.simulation_data ? 'Yes' : '—'}</strong><small>Not a live monitoring feed</small></div></div>

      <section className="panel coverage-map-panel">
        <div className="panel-heading"><div><h3>Coverage and incident layers</h3><p>Amber rings indicate synthetic monitored cells flagged for an information gap.</p></div><div className="coverage-legend"><i className="legend-ring" /> Reporting gap</div></div>
        <IncidentMap incidents={incidents.filter((item) => item.status !== 'merged')} coverage={result?.areas || []} showCoverage className="coverage-map" />
      </section>

      <section className="coverage-area-list">
        <div className="section-heading"><div><h3>Flagged areas</h3><p>{result?.note || 'Loading area review reasons…'}</p></div><span className="count-pill">{result?.areas?.length ?? 0} flagged</span></div>
        {loading && !result ? <div className="page-loading inline-loading"><span className="spinner" /> Checking reporting coverage…</div> : result?.areas?.length ? <div className="coverage-cards">{result.areas.map((area) => (
          <article className="panel coverage-area-card" key={area.area_name}>
            <div className="coverage-area-header"><div className="coverage-area-icon"><AlertTriangle size={17} /></div><div className="coverage-area-title"><h4>{area.area_name}</h4><span className={`exposure-tag exposure-${area.hazard_exposure}`}>{area.hazard_exposure} exposure</span></div><span className="synthetic-tag">SYNTHETIC</span></div>
            <div className="coverage-meta"><span><Clock3 size={14} /> Last known: {formatDate(area.last_known_info_at)}</span><span><WifiOff size={14} /> {area.connectivity_limited ? 'Connectivity limited' : 'No connectivity flag'}</span></div>
            <ul className="gap-reasons">{area.reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ul>
            {area.nearby_incident_count > 0 && <div className="nearby-count">{area.nearby_incident_count} nearby incident record(s) within the prototype radius. This does not confirm conditions in the area.</div>}
          </article>
        ))}</div> : <div className="panel empty-state coverage-empty"><Info size={22} /><strong>No reporting-gap flags</strong><span>This only means no current synthetic coverage rule was triggered. It does not mean any area is confirmed safe.</span></div>}
      </section>
      <div className="footer-disclaimer"><AlertTriangle size={14} /><span>Reporting gaps indicate missing or stale information only. RescueGrid does not infer incidents from silence.</span></div>
    </div>
  );
}
