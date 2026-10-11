import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Layers3, MapPinned, RefreshCw, Search } from 'lucide-react';
import { api, getIncidents } from '../api.js';
import IncidentMap from '../components/IncidentMap.jsx';
import IncidentDrawer from '../components/IncidentDrawer.jsx';
import { useToast } from '../components/ToastProvider.jsx';

export default function MapPage() {
  const [incidents, setIncidents] = useState([]);
  const [coverage, setCoverage] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [showCoverage, setShowCoverage] = useState(true);
  const [urgency, setUrgency] = useState('');
  const [status, setStatus] = useState('');
  const [search, setSearch] = useState('');
  const showToast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [records, gaps] = await Promise.all([getIncidents({ limit: 500 }), api('/api/coverage-gaps')]);
      setIncidents(records.items || []);
      setCoverage(gaps.areas || []);
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);
  useEffect(() => { load(); }, [load]);

  const visible = useMemo(() => incidents.filter((item) => {
    const matchesUrgency = !urgency || item.urgency_level === urgency;
    const matchesStatus = !status || item.status === status;
    const matchesText = !search || `${item.title} ${item.location_name || ''} ${item.disaster_type}`.toLowerCase().includes(search.toLowerCase());
    return matchesUrgency && matchesStatus && matchesText;
  }), [incidents, urgency, status, search]);
  const locatedCount = visible.filter((item) => item.latitude != null && item.longitude != null && item.status !== 'merged').length;

  return (
    <div className="page-content">
      <div className="page-intro page-intro-tight"><div><div className="eyebrow"><span className="eyebrow-dot" /> SPATIAL REVIEW</div><h2>Operations map</h2><p>Pan and zoom through explicitly located records. Unresolved place names are not geocoded.</p></div><button className="button button-secondary" onClick={load} disabled={loading}><RefreshCw size={15} /> Refresh</button></div>
      <div className="simulation-notice compact-notice"><AlertTriangle size={16} /><div><strong>Synthetic demo layer</strong><span>Markers and coverage cells are fictional training data. OpenStreetMap tiles require internet; local incident records remain available without them.</span></div></div>
      <section className="panel map-workspace-panel">
        <div className="map-toolbar">
          <div className="map-toolbar-title"><MapPinned size={18} /><div><strong>Incident and coverage view</strong><span>{locatedCount} located incident{locatedCount === 1 ? '' : 's'} · {visible.length - locatedCount} without map coordinates</span></div></div>
          <div className="map-filter-controls">
            <div className="compact-search"><Search size={15} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Find on map" /></div>
            <select aria-label="Filter rule-based urgency on map" value={urgency} onChange={(e) => setUrgency(e.target.value)}><option value="">All rule urgency</option><option value="critical">Critical</option><option value="high">High</option><option value="elevated">Elevated</option><option value="routine">Routine</option></select>
            <select aria-label="Filter status on map" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option><option value="unverified">Unverified</option><option value="needs_info">Needs info</option><option value="verified">Verified</option><option value="monitoring">Monitoring</option><option value="resolved">Resolved</option></select>
            <label className="layer-toggle"><input type="checkbox" checked={showCoverage} onChange={(e) => setShowCoverage(e.target.checked)} /><Layers3 size={15} /> Coverage gaps</label>
          </div>
        </div>
        <IncidentMap incidents={visible} coverage={coverage} showCoverage={showCoverage} onSelectIncident={setSelectedId} className="operations-map" />
        <div className="map-workspace-footer"><span><i className="legend-dot legend-critical" /> Higher queue priority</span><span><i className="legend-dot legend-standard" /> Other incidents</span><span><i className="legend-ring" /> Reporting-gap area</span><span className="map-coordinate-note">Only coordinator/source-provided coordinates are mapped.</span></div>
      </section>
      {visible.filter((item) => item.latitude == null || item.longitude == null).length > 0 && <div className="unresolved-strip"><AlertTriangle size={15} /><span>{visible.filter((item) => item.latitude == null || item.longitude == null).length} report(s) remain off map because safe coordinates are not available.</span><button type="button" className="text-button" onClick={() => setStatus('needs_info')}>Review unresolved</button></div>}
      <IncidentDrawer incidentId={selectedId} onClose={() => setSelectedId(null)} onChanged={load} />
    </div>
  );
}
