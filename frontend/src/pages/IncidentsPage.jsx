import { useCallback, useEffect, useState } from 'react';
import { ArrowDown, ArrowUp, CheckSquare, ChevronDown, Download, Filter, RefreshCw, Search, SlidersHorizontal, Square } from 'lucide-react';
import { api, getIncidents } from '../api.js';
import IncidentDrawer from '../components/IncidentDrawer.jsx';
import { StatusBadge, UrgencyBadge } from '../components/StatusBadge.jsx';
import { useToast } from '../components/ToastProvider.jsx';

function formatDate(value) {
  if (!value) return 'Unknown';
  return new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
}

export default function IncidentsPage() {
  const [filters, setFilters] = useState({ search: '', disaster_type: '', status: '', urgency: '', since_hours: '' });
  const [sort, setSort] = useState({ sort_by: 'priority_score', sort_order: 'desc' });
  const [result, setResult] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedRowIds, setSelectedRowIds] = useState(new Set());
  const [error, setError] = useState('');
  const [batchBusy, setBatchBusy] = useState(false);
  const showToast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getIncidents({ ...filters, ...sort, limit: 250 });
      setResult(data);
    } catch (err) {
      setError(err.message);
      showToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [filters, sort, showToast]);

  useEffect(() => { load(); }, [load]);

  function setFilter(key, value) {
    setFilters((current) => ({ ...current, [key]: value }));
  }
  function toggleSort(field) {
    setSort((current) => ({ sort_by: field, sort_order: current.sort_by === field && current.sort_order === 'desc' ? 'asc' : 'desc' }));
  }
  const SortIcon = ({ field }) => sort.sort_by !== field ? <ChevronDown size={13} className="sort-neutral" /> : sort.sort_order === 'desc' ? <ArrowDown size={13} /> : <ArrowUp size={13} />;

  const toggleSelectAll = () => {
    if (selectedRowIds.size === result.items.length) {
      setSelectedRowIds(new Set());
    } else {
      setSelectedRowIds(new Set(result.items.map((i) => i.id)));
    }
  };

  const toggleSelectRow = (id, e) => {
    e.stopPropagation();
    setSelectedRowIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const exportFilteredCsv = () => {
    if (!result.items.length) {
      showToast('No incidents to export', 'error');
      return;
    }
    const headers = ['ID', 'Title', 'Disaster Type', 'Location', 'Latitude', 'Longitude', 'Precision', 'Urgency Score', 'Urgency Level', 'Priority Score', 'Evidence Confidence', 'Status', 'Last Reported', 'Reports Count'];
    const rows = result.items.map((i) => [
      i.id,
      `"${(i.title || '').replace(/"/g, '""')}"`,
      i.disaster_type || '',
      `"${(i.location_name || '').replace(/"/g, '""')}"`,
      i.latitude ?? '',
      i.longitude ?? '',
      i.location_precision || '',
      i.urgency_score ?? '',
      i.urgency_level || '',
      i.priority_score ?? '',
      i.confidence_score ?? '',
      i.status || '',
      i.last_reported_at ? new Date(i.last_reported_at).toISOString() : '',
      i.report_count ?? 1,
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `rescuegrid_incidents_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast(`Exported ${result.items.length} incidents to CSV`);
  };

  const handleBatchVerify = async (action) => {
    if (!selectedRowIds.size) return;
    setBatchBusy(true);
    try {
      let count = 0;
      for (const id of selectedRowIds) {
        try {
          await api(`/api/incidents/${id}/verify`, {
            method: 'POST',
            body: JSON.stringify({ action, coordinator: 'Coordinator', note: `Batch action: ${action}` }),
          });
          count++;
        } catch {
          // ignore already merged/resolved
        }
      }
      showToast(`Updated verification status for ${count} incident(s).`);
      setSelectedRowIds(new Set());
      await load();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setBatchBusy(false);
    }
  };

  return (
    <div className="page-content">
      <div className="page-intro page-intro-tight">
        <div><div className="eyebrow"><span className="eyebrow-dot" /> COORDINATOR WORKSPACE</div><h2>Incident register</h2><p>Search original reports, inspect score explanations, and record human review decisions.</p></div>
        <button className="button button-secondary" onClick={load} disabled={loading}><RefreshCw size={15} className={loading ? 'spin-icon' : ''} /> Refresh</button>
      </div>
      <div className="toolbar-panel">
        <div className="search-field"><Search size={17} /><input aria-label="Search incidents" placeholder="Search incident, place, or report text…" value={filters.search} onChange={(e) => setFilter('search', e.target.value)} /></div>
        <div className="toolbar-filters">
          <label className="filter-select"><Filter size={14} /><select aria-label="Filter disaster type" value={filters.disaster_type} onChange={(e) => setFilter('disaster_type', e.target.value)}><option value="">All types</option><option value="flood">Flood</option><option value="earthquake">Earthquake</option><option value="landslide">Landslide</option><option value="fire">Fire</option><option value="storm">Storm</option><option value="other">Other</option><option value="unknown">Unknown</option></select></label>
          <label className="filter-select"><select aria-label="Filter rule-based urgency" value={filters.urgency} onChange={(e) => setFilter('urgency', e.target.value)}><option value="">All rule urgency</option><option value="critical">Critical</option><option value="high">High</option><option value="elevated">Elevated</option><option value="routine">Routine</option></select></label>
          <label className="filter-select"><select aria-label="Filter verification status" value={filters.status} onChange={(e) => setFilter('status', e.target.value)}><option value="">All statuses</option><option value="unverified">Unverified</option><option value="needs_info">Needs information</option><option value="verified">Verified</option><option value="monitoring">Monitoring</option><option value="resolved">Resolved</option><option value="rejected">Rejected</option><option value="merged">Merged</option></select></label>
          <label className="filter-select"><SlidersHorizontal size={14} /><select aria-label="Filter by report time" value={filters.since_hours} onChange={(e) => setFilter('since_hours', e.target.value)}><option value="">Any time</option><option value="24">Last 24 hours</option><option value="72">Last 3 days</option><option value="168">Last 7 days</option></select></label>
          <button className="button button-secondary" onClick={exportFilteredCsv} title="Export filtered results to CSV"><Download size={14} /> Export CSV</button>
        </div>
      </div>

      {selectedRowIds.size > 0 && (
        <div className="batch-toolbar">
          <span><strong>{selectedRowIds.size}</strong> incident(s) selected</span>
          <div className="button-row">
            <button className="button button-secondary button-small" disabled={batchBusy} onClick={() => handleBatchVerify('verified')}>Verify selected</button>
            <button className="button button-secondary button-small" disabled={batchBusy} onClick={() => handleBatchVerify('needs_info')}>Request info</button>
            <button className="button button-secondary button-small" disabled={batchBusy} onClick={() => handleBatchVerify('monitoring')}>Mark monitoring</button>
            <button className="button button-secondary button-small" onClick={() => setSelectedRowIds(new Set())}>Clear selection</button>
          </div>
        </div>
      )}

      <section className="panel table-panel">
        <div className="table-panel-heading"><div><h3>All incidents <span className="record-count">{result.total}</span></h3><p>Original reports are preserved even after a confirmed duplicate merge.</p></div><span className="table-note">Sorted by {sort.sort_by.replaceAll('_', ' ')} <SortIcon field={sort.sort_by} /></span></div>
        {error && <div className="inline-error">{error}</div>}
        <div className="table-scroll">
          <table className="incident-table">
            <thead><tr>
              <th style={{ width: '40px' }}><button type="button" onClick={toggleSelectAll} aria-label="Select all" style={{ background: 'none', border: 'none', padding: 0 }}>{selectedRowIds.size > 0 && selectedRowIds.size === result.items.length ? <CheckSquare size={16} color="#2f6fbe" /> : <Square size={16} color="#718095" />}</button></th>
              <th><button onClick={() => toggleSort('title')}>Incident <SortIcon field="title" /></button></th>
              <th><button onClick={() => toggleSort('disaster_type')}>Type <SortIcon field="disaster_type" /></button></th>
              <th>Location</th>
              <th><button onClick={() => toggleSort('priority_score')}>Queue priority <SortIcon field="priority_score" /></button></th>
              <th><button onClick={() => toggleSort('confidence_score')}>Evidence <SortIcon field="confidence_score" /></button></th>
              <th><button onClick={() => toggleSort('status')}>Status <SortIcon field="status" /></button></th>
              <th><button onClick={() => toggleSort('last_reported_at')}>Last report <SortIcon field="last_reported_at" /></button></th>
            </tr></thead>
            <tbody>
              {loading && !result.items.length && <tr><td colSpan="8"><div className="table-state"><span className="spinner" /> Loading incidents…</div></td></tr>}
              {!loading && result.items.length === 0 && <tr><td colSpan="8"><div className="table-state empty-table"><Search size={20} /><strong>No incidents match these filters</strong><span>Try clearing a filter or importing a synthetic report.</span></div></td></tr>}
              {result.items.map((incident) => {
                const isSelected = selectedRowIds.has(incident.id);
                return (
                  <tr key={incident.id} onClick={() => setSelectedId(incident.id)} tabIndex="0" onKeyDown={(event) => event.key === 'Enter' && setSelectedId(incident.id)} className={isSelected ? 'row-selected' : ''}>
                    <td onClick={(e) => toggleSelectRow(incident.id, e)}><span style={{ display: 'grid', placeItems: 'center' }}>{isSelected ? <CheckSquare size={16} color="#2f6fbe" /> : <Square size={16} color="#a0aec0" />}</span></td>
                    <td><div className="incident-name-cell"><span className={`row-priority-dot row-dot-${incident.priority_level}`} /><div><strong>{incident.title}</strong><small>RG-{String(incident.id).padStart(4, '0')} · {incident.report_count} report{incident.report_count === 1 ? '' : 's'}</small></div></div></td>
                    <td><span className="type-cell">{incident.disaster_type}</span></td>
                    <td><div className="location-cell">{incident.location_name || <span className="text-unknown">Unresolved</span>}{incident.location_precision === 'approximate' && <small>Approximate</small>}</div></td>
                    <td><UrgencyBadge score={incident.priority_score} level={incident.priority_level} />{incident.human_priority_override !== null && incident.human_priority_override !== undefined && <small className="override-tag">Human override</small>}</td>
                    <td><div className="evidence-cell"><strong className={incident.confidence_score < 40 ? 'text-warning' : ''}>{incident.confidence_score}</strong><span>/100</span><div className="confidence-track"><i style={{ width: `${incident.confidence_score}%` }} /></div></div></td>
                    <td><StatusBadge status={incident.status} /></td>
                    <td className="date-cell">{formatDate(incident.last_reported_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="table-footer"><span>Showing {result.items.length} of {result.total} records</span><span><i className="footer-dot" /> Low evidence never suppresses urgency</span></div>
      </section>
      <IncidentDrawer incidentId={selectedId} onClose={() => setSelectedId(null)} onChanged={load} />
    </div>
  );
}
