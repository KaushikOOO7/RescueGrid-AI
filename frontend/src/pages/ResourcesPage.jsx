import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, Box, CheckCircle2, Edit3, Package, Plus, RefreshCw, Truck, X } from 'lucide-react';
import { createResource, getResources, updateResource } from '../api.js';
import { useToast } from '../components/ToastProvider.jsx';

export default function ResourcesPage() {
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    resource_type: '',
    area_name: '',
    quantity: 10,
    availability_status: 'available',
    updated_by: 'Logistics Lead',
  });
  const showToast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getResources();
      setResources(data || []);
    } catch (err) {
      setError(err.message);
      showToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.resource_type.trim()) return;
    setBusy(true);
    try {
      await createResource({
        ...form,
        quantity: form.quantity ? Number(form.quantity) : null,
      });
      showToast('Resource item created successfully.');
      setShowAddForm(false);
      setForm({ resource_type: '', area_name: '', quantity: 10, availability_status: 'available', updated_by: 'Logistics Lead' });
      await load();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const [editingResource, setEditingResource] = useState(null);
  const [editForm, setEditForm] = useState({ quantity: 0, area_name: '', availability_status: 'available' });

  const handleEditOpen = (res) => {
    setEditingResource(res);
    setEditForm({
      quantity: res.quantity ?? 0,
      area_name: res.area_name || '',
      availability_status: res.availability_status || 'available',
    });
  };

  const handleEditSave = async (e) => {
    e.preventDefault();
    if (!editingResource) return;
    setBusy(true);
    try {
      await updateResource(editingResource.id, {
        quantity: editForm.quantity !== '' ? Number(editForm.quantity) : null,
        area_name: editForm.area_name || null,
        availability_status: editForm.availability_status,
      });
      showToast(`Updated ${editingResource.resource_type} inventory.`);
      setEditingResource(null);
      await load();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const handleStatusChange = async (id, status) => {
    try {
      await updateResource(id, { availability_status: status });
      showToast('Status updated.');
      await load();
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const totalQuantity = resources.reduce((sum, r) => sum + (r.quantity || 0), 0);
  const totalAllocated = resources.reduce((sum, r) => sum + (r.allocated_quantity || 0), 0);
  const totalAvailable = resources.reduce((sum, r) => sum + (r.available_quantity || 0), 0);

  return (
    <div className="page-content">
      <div className="page-intro page-intro-tight">
        <div>
          <div className="eyebrow"><span className="eyebrow-dot" /> LOGISTICS & INVENTORY</div>
          <h2>Resource availability</h2>
          <p>Track rescue craft, medical supplies, personnel, and staging inventory. Allocations are validated against current available capacity.</p>
        </div>
        <div className="button-row">
          <button className="button button-secondary" onClick={load} disabled={loading}><RefreshCw size={15} className={loading ? 'spin-icon' : ''} /> Refresh</button>
          <button className="button button-primary" onClick={() => setShowAddForm((v) => !v)}><Plus size={15} /> {showAddForm ? 'Cancel' : 'Add resource'}</button>
        </div>
      </div>

      <div className="simulation-notice compact-notice">
        <AlertCircle size={16} />
        <div>
          <strong>Decision support only</strong>
          <span>Availability quantities reflect operator-entered depot numbers. The system prevents over-allocation but does not execute real-world dispatch.</span>
        </div>
      </div>

      {showAddForm && (
        <section className="panel" style={{ padding: '20px' }}>
          <h3 style={{ margin: '0 0 14px', fontSize: '15px' }}>Register new resource inventory</h3>
          <form onSubmit={handleCreate} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
            <label>Resource type
              <input value={form.resource_type} onChange={(e) => setForm({ ...form, resource_type: e.target.value })} required placeholder="e.g. rescue boat, medical team…" style={{ width: '100%', padding: '7px', marginTop: '4px' }} />
            </label>
            <label>Staging base / location (optional)
              <input value={form.area_name} onChange={(e) => setForm({ ...form, area_name: e.target.value })} placeholder="e.g. Central Depot, Kestrel Footbridge…" style={{ width: '100%', padding: '7px', marginTop: '4px' }} />
            </label>
            <label>Total quantity
              <input type="number" min="0" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} style={{ width: '100%', padding: '7px', marginTop: '4px' }} />
            </label>
            <label>Initial status
              <select value={form.availability_status} onChange={(e) => setForm({ ...form, availability_status: e.target.value })} style={{ width: '100%', padding: '7px', marginTop: '4px' }}>
                <option value="available">Available</option>
                <option value="limited">Limited</option>
                <option value="in_transit">In transit</option>
                <option value="exhausted">Exhausted</option>
                <option value="unknown">Unknown</option>
              </select>
            </label>
            <div style={{ gridColumn: '1 / -1', display: 'flex', gap: '10px', marginTop: '6px' }}>
              <button className="button button-primary" disabled={busy}>Save resource</button>
              <button type="button" className="button button-secondary" onClick={() => setShowAddForm(false)}>Cancel</button>
            </div>
          </form>
        </section>
      )}

      <div className="coverage-summary-grid">
        <div className="coverage-summary-card">
          <span>Registered types</span>
          <strong>{resources.length}</strong>
          <small>Tracked categories</small>
        </div>
        <div className="coverage-summary-card">
          <span>Total capacity</span>
          <strong>{totalQuantity}</strong>
          <small>Recorded units</small>
        </div>
        <div className="coverage-summary-card">
          <span>Allocated units</span>
          <strong style={{ color: totalAllocated > 0 ? '#ad6b0a' : '#1d2b3b' }}>{totalAllocated}</strong>
          <small>Assigned to active incidents</small>
        </div>
        <div className="coverage-summary-card">
          <span>Remaining available</span>
          <strong style={{ color: '#247a57' }}>{totalAvailable}</strong>
          <small>Ready for allocation</small>
        </div>
      </div>

      <section className="panel table-panel">
        <div className="table-panel-heading">
          <div>
            <h3>Resource registry <span className="record-count">{resources.length}</span></h3>
            <p>Operational quantities and base locations entered by emergency coordinators.</p>
          </div>
        </div>
        {error && <div className="inline-error">{error}</div>}
        <div className="table-scroll">
          <table className="incident-table">
            <thead>
              <tr>
                <th>Resource type</th>
                <th>Base / area</th>
                <th>Total capacity</th>
                <th>Allocated</th>
                <th>Available</th>
                <th>Status</th>
                <th>Quick status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && !resources.length && (
                <tr><td colSpan="8"><div className="table-state"><span className="spinner" /> Loading inventory…</div></td></tr>
              )}
              {!loading && resources.length === 0 && (
                <tr><td colSpan="8"><div className="table-state empty-table"><Package size={20} /><strong>No resources registered yet</strong><span>Click "Add resource" to register local staging assets.</span></div></td></tr>
              )}
              {resources.map((res) => (
                <tr key={res.id}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Box size={16} color="#2f6fbe" />
                      <strong>{res.resource_type}</strong>
                    </div>
                  </td>
                  <td>{res.area_name || <span className="text-unknown">Central / unassigned</span>}</td>
                  <td><strong>{res.quantity ?? '—'}</strong></td>
                  <td>
                    <span style={{ color: res.allocated_quantity > 0 ? '#ad6b0a' : '#718095', fontWeight: res.allocated_quantity > 0 ? '700' : 'normal' }}>
                      {res.allocated_quantity}
                    </span>
                  </td>
                  <td>
                    <span style={{ color: (res.available_quantity || 0) > 0 ? '#247a57' : '#b4403c', fontWeight: '700' }}>
                      {res.available_quantity ?? '—'}
                    </span>
                  </td>
                  <td>
                    <span className={`status-pill status-${res.availability_status === 'available' ? 'verified' : res.availability_status === 'limited' ? 'monitoring' : 'unverified'}`}>
                      {res.availability_status}
                    </span>
                  </td>
                  <td>
                    <select
                      value={res.availability_status}
                      onChange={(e) => handleStatusChange(res.id, e.target.value)}
                      style={{ fontSize: '11px', padding: '3px 6px', borderRadius: '4px', border: '1px solid #cbd5e0' }}
                    >
                      <option value="available">Available</option>
                      <option value="limited">Limited</option>
                      <option value="in_transit">In transit</option>
                      <option value="exhausted">Exhausted</option>
                      <option value="unknown">Unknown</option>
                    </select>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="button button-secondary button-small"
                      onClick={() => handleEditOpen(res)}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px', padding: '3px 8px' }}
                      title="Edit capacity and details"
                    >
                      <Edit3 size={13} /> Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="table-footer">
          <span>Showing {resources.length} inventory categories</span>
          <span><i className="footer-dot" /> Quantities checked before every allocation</span>
        </div>
      </section>

      {editingResource && (
        <div className="drawer-backdrop" onMouseDown={(e) => e.target === e.currentTarget && setEditingResource(null)}>
          <div className="panel" role="dialog" aria-modal="true" style={{ width: '90%', maxWidth: '480px', margin: 'auto', padding: '24px', background: '#fff', borderRadius: '8px', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '16px' }}>Update Inventory: {editingResource.resource_type}</h3>
              <button type="button" className="icon-button" onClick={() => setEditingResource(null)} aria-label="Close dialog"><X size={18} /></button>
            </div>
            <form onSubmit={handleEditSave} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <label style={{ fontSize: '12px' }}>Total capacity
                <input
                  type="number"
                  min="0"
                  value={editForm.quantity}
                  onChange={(e) => setEditForm({ ...editForm, quantity: e.target.value })}
                  style={{ width: '100%', padding: '7px', marginTop: '4px' }}
                  required
                />
                <small style={{ color: '#718095', display: 'block', marginTop: '4px' }}>
                  Current allocated units: {editingResource.allocated_quantity}. Total capacity cannot be reduced below current allocations.
                </small>
              </label>

              <label style={{ fontSize: '12px' }}>Base / Depot Location
                <input
                  type="text"
                  value={editForm.area_name}
                  onChange={(e) => setEditForm({ ...editForm, area_name: e.target.value })}
                  placeholder="e.g. Central Depot, Kestrel Footbridge"
                  style={{ width: '100%', padding: '7px', marginTop: '4px' }}
                />
              </label>

              <label style={{ fontSize: '12px' }}>Availability status
                <select
                  value={editForm.availability_status}
                  onChange={(e) => setEditForm({ ...editForm, availability_status: e.target.value })}
                  style={{ width: '100%', padding: '7px', marginTop: '4px' }}
                >
                  <option value="available">Available</option>
                  <option value="limited">Limited</option>
                  <option value="in_transit">In transit</option>
                  <option value="exhausted">Exhausted</option>
                  <option value="unknown">Unknown</option>
                </select>
              </label>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button type="button" className="button button-secondary" onClick={() => setEditingResource(null)} disabled={busy}>Cancel</button>
                <button type="submit" className="button button-primary" disabled={busy}>Save changes</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
