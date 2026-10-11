import { useState } from 'react';
import { AlertOctagon, CheckCircle2, RotateCcw, ShieldAlert, Sparkles } from 'lucide-react';
import { resetDemoData } from '../api.js';
import { useToast } from '../components/ToastProvider.jsx';

export default function SettingsPage() {
  const [resetting, setResetting] = useState(false);
  const [resetDone, setResetDone] = useState(false);
  const showToast = useToast();

  const handleReset = async () => {
    if (!window.confirm('Reset all synthetic demo records? User-created incidents and original reports will remain safe.')) {
      return;
    }
    setResetting(true);
    setResetDone(false);
    try {
      const res = await resetDemoData();
      showToast(res.note || 'Synthetic demo data has been reset.');
      setResetDone(true);
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="page-content">
      <div className="page-intro page-intro-tight">
        <div>
          <div className="eyebrow"><span className="eyebrow-dot" /> SYSTEM & PREFERENCES</div>
          <h2>Settings & Demonstration Controls</h2>
          <p>Review system parameters, scoring weights, transparency guarantees, and manage evaluation demo data.</p>
        </div>
      </div>

      <div className="stats-grid">
        <section className="panel" style={{ padding: '20px' }}>
          <h3 style={{ margin: '0 0 10px', fontSize: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <RotateCcw size={18} color="#2f6fbe" /> Demonstration Reset
          </h3>
          <p style={{ fontSize: '12px', color: '#718095', lineHeight: 1.6, margin: '0 0 16px' }}>
            Safely reset seeded demo incidents, coverage cells, and duplicate pairs to their initial testing baseline.
            <strong> User-created reports and custom incidents will not be affected.</strong>
          </p>
          <button className="button button-danger-outline" disabled={resetting} onClick={handleReset}>
            <RotateCcw size={14} className={resetting ? 'spin-icon' : ''} />
            {resetting ? 'Resetting demo data…' : 'Reset synthetic demo records'}
          </button>
          {resetDone && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#247a57', fontSize: '12px', marginTop: '10px' }}>
              <CheckCircle2 size={16} /> Seeded demo scenario restored successfully.
            </div>
          )}
        </section>

        <section className="panel" style={{ padding: '20px' }}>
          <h3 style={{ margin: '0 0 10px', fontSize: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={18} color="#2f6fbe" /> Configurable Scoring Weights
          </h3>
          <p style={{ fontSize: '12px', color: '#718095', lineHeight: 1.6, margin: '0 0 12px' }}>
            RescueGrid prioritizes transparent, explainable decision support over opaque AI outputs:
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px', fontSize: '11px' }}>
            <div style={{ background: '#f7fafc', padding: '6px 8px', borderRadius: '4px' }}>Threat to human life: <strong>35 pts</strong></div>
            <div style={{ background: '#f7fafc', padding: '6px 8px', borderRadius: '4px' }}>Time criticality: <strong>20 pts</strong></div>
            <div style={{ background: '#f7fafc', padding: '6px 8px', borderRadius: '4px' }}>People affected: <strong>15 pts</strong></div>
            <div style={{ background: '#f7fafc', padding: '6px 8px', borderRadius: '4px' }}>Vulnerability indicators: <strong>10 pts</strong></div>
            <div style={{ background: '#f7fafc', padding: '6px 8px', borderRadius: '4px' }}>Hazard escalation: <strong>10 pts</strong></div>
            <div style={{ background: '#f7fafc', padding: '6px 8px', borderRadius: '4px' }}>Access difficulty: <strong>10 pts</strong></div>
          </div>
          <small style={{ display: 'block', color: '#a0aec0', marginTop: '8px', fontSize: '10px' }}>
            Configurable demonstration rules; not an operational standard. Evidence confidence is calculated independently.
          </small>
        </section>
      </div>

      <section className="panel" style={{ padding: '20px' }}>
        <h3 style={{ margin: '0 0 12px', fontSize: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldAlert size={18} color="#2f6fbe" /> Operational Guardrails & Architecture
        </h3>
        <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12px', color: '#4a5568', lineHeight: 1.8 }}>
          <li><strong>No autonomous dispatch:</strong> All priority overrides, verifications, and resource allocations require human coordinator sign-off.</li>
          <li><strong>Provenance preservation:</strong> Original report texts and sources are permanently retained, even when duplicate candidates are merged.</li>
          <li><strong>Missing information principle:</strong> Lack of reporting is treated as an information gap to be investigated, never as proof of safety.</li>
          <li><strong>No fabricated coordinates:</strong> Only explicit coordinates provided by operators or reports are mapped; vague place names remain off-map.</li>
          <li><strong>Audit accountability:</strong> Every status update, priority override, and inventory allocation creates a permanent audit log entry.</li>
        </ul>
      </section>
    </div>
  );
}
