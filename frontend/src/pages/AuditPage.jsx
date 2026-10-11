import { useCallback, useEffect, useState } from 'react';
import { Activity, BookOpenCheck, RefreshCw, Search } from 'lucide-react';
import { api } from '../api.js';
import { useToast } from '../components/ToastProvider.jsx';

function formatDate(value) {
  return value ? new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : 'Unknown';
}

function humanize(action = '') {
  return action.replaceAll('_', ' ');
}

export default function AuditPage() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const showToast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api('/api/audit-log?limit=250');
      setItems(result.items || []);
      setTotal(result.total || 0);
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);
  useEffect(() => { load(); }, [load]);

  const filtered = items.filter((item) => `${item.action} ${item.actor} ${item.entity_id} ${JSON.stringify(item.details)}`.toLowerCase().includes(query.toLowerCase()));

  return (
    <div className="page-content">
      <div className="page-intro page-intro-tight"><div><div className="eyebrow"><span className="eyebrow-dot" /> ACCOUNTABILITY</div><h2>Decision log</h2><p>Review report ingestion, verification, priority changes, duplicate decisions, and coordinator actions.</p></div><button className="button button-secondary" onClick={load} disabled={loading}><RefreshCw size={15} /> Refresh</button></div>
      <div className="audit-banner"><BookOpenCheck size={18} /><div><strong>Human decisions are recorded</strong><span>Priority overrides require a reason. Duplicate merging preserves original reports and provenance. The log is local to this SQLite prototype.</span></div><span className="audit-total">{total} events</span></div>
      <section className="panel audit-panel">
        <div className="audit-toolbar"><div className="search-field"><Search size={16} /><input placeholder="Filter events or coordinator…" value={query} onChange={(e) => setQuery(e.target.value)} /></div><span>{filtered.length} events shown</span></div>
        {loading && !items.length ? <div className="page-loading inline-loading"><span className="spinner" /> Loading decision history…</div> : filtered.length ? <div className="audit-list">{filtered.map((item) => (
          <article className="audit-row" key={item.id}>
            <span className={`audit-action-icon audit-${item.action.includes('priority') ? 'priority' : item.action.includes('duplicate') ? 'duplicate' : item.action.includes('verification') ? 'verification' : 'default'}`}><Activity size={16} /></span>
            <div className="audit-event-copy"><div><strong className="capitalize">{humanize(item.action)}</strong><span className="audit-entity">{item.entity_type} {item.entity_id ? `#${item.entity_id}` : ''}</span></div><p>{item.details?.reason || item.details?.note || (item.details?.fields ? `Updated fields: ${item.details.fields.join(', ')}` : item.details?.source_type ? `Source: ${item.details.source_type}` : 'Decision or record event saved.')}</p><small>{item.actor} · {formatDate(item.created_at)}</small></div>
            <span className="audit-event-id">EV-{String(item.id).padStart(5, '0')}</span>
          </article>
        ))}</div> : <div className="empty-state audit-empty"><BookOpenCheck size={23} /><strong>No matching decision events</strong><span>Try another filter or record a review decision on an incident.</span></div>}
      </section>
      <div className="footer-disclaimer"><Activity size={14} /><span>Audit events document application actions; they do not prove that a real-world event occurred.</span></div>
    </div>
  );
}
