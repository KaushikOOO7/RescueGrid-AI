import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, AlertOctagon, AlertTriangle, Clock3, PlusCircle, RefreshCw, Upload } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api.js';
import StatCard from '../components/StatCard.jsx';
import IncidentMap from '../components/IncidentMap.jsx';
import IncidentDrawer from '../components/IncidentDrawer.jsx';
import { StatusBadge, UrgencyBadge } from '../components/StatusBadge.jsx';
import { useToast } from '../components/ToastProvider.jsx';

function formatTime(value) {
  if (!value) return 'Time unknown';
  const age = Math.max(0, Date.now() - new Date(value).getTime());
  const minutes = Math.floor(age / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function OverviewPage() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const showToast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [result, analysis] = await Promise.all([api('/api/dashboard'), api('/api/analytics')]);
      setData(result);
      setAnalytics(analysis);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading && !data) return <div className="page-loading"><span className="spinner" /> Loading operations picture…</div>;
  if (error && !data) return <div className="error-panel"><AlertTriangle size={20} /><div><strong>Dashboard unavailable</strong><p>{error}. Confirm the FastAPI service is running.</p><button className="button button-secondary" onClick={load}><RefreshCw size={15} /> Retry</button></div></div>;

  const queue = data?.priority_queue || [];
  const recent = data?.recent_updates || [];
  const distribution = data?.priority_distribution || [];

  return (
    <div className="page-content">
      <div className="page-intro">
        <div><div className="eyebrow"><span className="eyebrow-dot" /> SIMULATED OPERATIONS PICTURE</div><h2>Operations picture</h2><p>Review new information, prioritize by reported need, and close the gaps that keep teams uncertain.</p></div>
        <button className="button button-secondary refresh-button" onClick={load} disabled={loading}><RefreshCw size={15} className={loading ? 'spin-icon' : ''} /> Refresh</button>
      </div>
      <div className="simulation-notice"><AlertTriangle size={17} /><div><strong>Simulation environment</strong><span>All seeded incidents and coverage cells are fictional demonstration data. This system does not authorize dispatch.</span></div></div>

      {data?.active_incidents === 0 && (
        <div className="panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '10px', background: '#fffaf0', border: '1px solid #eadbbd' }}>
          <strong style={{ fontSize: '15px', color: '#896225' }}>Welcome to RescueGrid AI · Getting Started</strong>
          <p style={{ margin: 0, fontSize: '12px', color: '#65758a', lineHeight: 1.6 }}>
            The database currently has no active incidents. To begin coordinating, enter a new incoming message via Report Intake or import a batch CSV file.
          </p>
          <div className="button-row" style={{ marginTop: '8px' }}>
            <button className="button button-primary" onClick={() => navigate('/intake')}>
              <PlusCircle size={15} /> Enter first report
            </button>
            <button className="button button-secondary" onClick={() => navigate('/intake')}>
              <Upload size={15} /> Import CSV
            </button>
          </div>
        </div>
      )}

      <div className="stats-grid">
        <StatCard
          label="Active incidents"
          value={data?.active_incidents ?? 0}
          detail="Click to view all incidents in register"
          icon={Activity}
          tone="blue"
          onClick={() => navigate('/incidents')}
        />
        <StatCard
          label="High urgency"
          value={data?.high_urgency_incidents ?? 0}
          detail="Queue priority ≥ 60; click to filter"
          icon={AlertOctagon}
          tone="red"
          onClick={() => navigate('/incidents')}
        />
        <StatCard
          label="Awaiting verification"
          value={data?.awaiting_verification ?? 0}
          detail="Unverified reports; click to review"
          icon={Clock3}
          tone="amber"
          onClick={() => navigate('/incidents')}
        />
        <StatCard
          label="Reporting gaps"
          value={data?.reporting_gaps ?? 0}
          detail="Information gaps; click to inspect"
          icon={AlertTriangle}
          tone="slate"
          onClick={() => navigate('/coverage')}
        />
      </div>

      <div className="dashboard-grid dashboard-map-row">
        <section className="panel map-panel">
          <div className="panel-heading"><div><h3>Incident map</h3><p>Only records with explicitly entered coordinates appear.</p></div><span className="panel-label"><span className="pulse-dot" /> LIVE LOCAL DATA</span></div>
          <IncidentMap incidents={data?.map_incidents || []} onSelectIncident={setSelectedId} className="dashboard-map" />
        </section>
        <section className="panel distribution-panel">
          <div className="panel-heading"><div><h3>Priority distribution</h3><p>Active records by effective queue score</p></div><span className="mini-icon"><Activity size={17} /></span></div>
          <div className="chart-wrap">
            {distribution.some((item) => item.count > 0) ? <ResponsiveContainer width="100%" height="100%">
              <BarChart data={distribution} layout="vertical" margin={{ top: 2, right: 18, left: 12, bottom: 0 }}>
                <CartesianGrid stroke="#edf1f5" horizontal={false} />
                <XAxis type="number" allowDecimals={false} hide />
                <YAxis dataKey="label" type="category" width={74} tick={{ fill: '#65758a', fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: '#f5f7fa' }} formatter={(value) => [`${value} incidents`, 'Count']} />
                <Bar dataKey="count" radius={[0, 5, 5, 0]} fill="#2f6fbe" barSize={15} />
              </BarChart>
            </ResponsiveContainer> : <div className="chart-empty">No active incidents to chart.</div>}
          </div>
          <div className="chart-footnote"><span>By hazard type · {analytics?.disaster_type_distribution?.length ? analytics.disaster_type_distribution.map((item) => `${item.label} ${item.count}`).join(' · ') : 'No active records'}</span><small>Queue bands use prototype thresholds. A human override is shown separately from rule-based urgency.</small></div>
        </section>
      </div>

      <div className="dashboard-grid lower-dashboard-row">
        <section className="panel priority-panel">
          <div className="panel-heading"><div><h3>Highest-priority queue</h3><p>Low-confidence, high-urgency reports remain visible for verification.</p></div><span className="queue-count">{queue.length} shown</span></div>
          {queue.length ? <div className="queue-list">{queue.map((item, index) => (
            <button type="button" className="queue-item" key={item.id} onClick={() => setSelectedId(item.id)}>
              <span className={`queue-rank ${index === 0 ? 'queue-rank-first' : ''}`}>{String(index + 1).padStart(2, '0')}</span>
              <span className="queue-copy"><strong>{item.title}</strong><span>{item.location_name || 'Location unresolved'} · {item.disaster_type}</span></span>
              <span className="queue-meta"><UrgencyBadge score={item.priority_score} level={item.priority_level} /><small>Evidence {item.confidence_score}/100</small></span>
            </button>
          ))}</div> : <div className="empty-state"><Activity size={22} /><strong>Queue is clear</strong><span>New incident reports will appear here.</span></div>}
          {queue.some((item) => item.priority_score >= 60 && item.confidence_score < 40) && <div className="queue-warning"><AlertTriangle size={14} /> High urgency with limited evidence: prioritize verification, not automatic dispatch.</div>}
        </section>
        <section className="panel updates-panel">
          <div className="panel-heading"><div><h3>Recent updates</h3><p>Latest incident record changes</p></div><Clock3 size={17} className="heading-muted-icon" /></div>
          {recent.length ? <div className="update-list">{recent.map((item) => (
            <button type="button" className="update-row" key={item.id} onClick={() => setSelectedId(item.id)}>
              <span className={`update-indicator update-${item.status}`} />
              <span className="update-copy"><strong>{item.title}</strong><span><StatusBadge status={item.status} /> <span className="update-location">{item.location_name || 'Location unresolved'}</span></span></span>
              <time>{formatTime(item.updated_at)}</time>
            </button>
          ))}</div> : <div className="empty-state compact-empty"><span>No incident activity recorded yet.</span></div>}
          {data?.gap_preview?.length > 0 && <div className="gap-preview"><div className="gap-preview-heading"><AlertTriangle size={14} /> Reporting-gap watch</div>{data.gap_preview.slice(0, 2).map((gap) => <div className="gap-preview-row" key={gap.area_name}><strong>{gap.area_name}</strong><span>{gap.reasons?.[0]}</span></div>)}</div>}
        </section>
      </div>

      <div className="footer-disclaimer"><AlertTriangle size={14} /><span>Prototype scoring weights are unvalidated. Message volume, duplicates, and social popularity do not add urgency points.</span></div>
      <IncidentDrawer incidentId={selectedId} onClose={() => setSelectedId(null)} onChanged={load} />
    </div>
  );
}
