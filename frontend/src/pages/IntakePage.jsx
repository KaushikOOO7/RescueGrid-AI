import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, ArrowRight, CheckCircle2, FileSpreadsheet, FileText, Info, UploadCloud, WandSparkles } from 'lucide-react';
import { api } from '../api.js';
import { useToast } from '../components/ToastProvider.jsx';

const examples = [
  {
    label: 'Flood · trapped residents',
    source_type: 'simulated volunteer',
    source_name: 'Synthetic volunteer channel',
    text: 'Volunteer SMS: Six residents are trapped above the ground floor near Kestrel Footbridge. Floodwater is rising rapidly. Need a rescue boat and medical assistance now.',
  },
  {
    label: 'Earthquake · damage report',
    source_type: 'simulated field',
    source_name: 'Synthetic field team',
    text: 'Field note: Earthquake shaking damaged a wall at Pineglass School; 18 people are sheltering outside and two report minor injuries. Medical check and temporary shelter requested.',
  },
  {
    label: 'Unclear location · request follow-up',
    source_type: 'simulated public post',
    source_name: 'Synthetic community channel',
    text: 'Strong shaking and a wall has fallen somewhere near the hills. We need shelter but cannot share a safe location right now.',
  },
];

const numberOrNull = (value) => value === '' || value === null || value === undefined ? null : Number(value);

export default function IntakePage() {
  const navigate = useNavigate();
  const [reportText, setReportText] = useState('');
  const [sourceType, setSourceType] = useState('sms');
  const [sourceName, setSourceName] = useState('');
  const [firsthand, setFirsthand] = useState(false);
  const [independent, setIndependent] = useState(false);
  const [preview, setPreview] = useState(null);
  const [fields, setFields] = useState({});
  const [analyzing, setAnalyzing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(null);

  const [csvFile, setCsvFile] = useState(null);
  const [csvText, setCsvText] = useState('');
  const [csvPreview, setCsvPreview] = useState(null);
  const [csvBusy, setCsvBusy] = useState(false);
  const [csvError, setCsvError] = useState('');
  const [importResult, setImportResult] = useState(null);
  const showToast = useToast();

  function loadExample(example) {
    setReportText(example.text);
    setSourceType(example.source_type);
    setSourceName(example.source_name);
    setFirsthand(example.source_type.includes('field'));
    setIndependent(false);
    setPreview(null);
    setSaved(null);
    setError('');
  }

  async function analyzeText(event) {
    event.preventDefault();
    setError('');
    setSaved(null);
    setAnalyzing(true);
    try {
      const result = await api('/api/reports/preview', {
        method: 'POST', body: JSON.stringify({ text: reportText, source_type: sourceType, source_name: sourceName || null }),
      });
      setPreview(result);
      setFields({ ...result.extracted, needsText: (result.extracted.needs || []).join(', '), latitude: '', longitude: '' });
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzing(false);
    }
  }

  async function saveIncident(event) {
    event.preventDefault();
    setError('');
    setSaving(true);
    const lat = numberOrNull(fields.latitude);
    const lon = numberOrNull(fields.longitude);
    if ((lat === null) !== (lon === null)) {
      setError('Enter both coordinates, or leave both blank. Coordinates are never inferred.');
      setSaving(false);
      return;
    }
    try {
      const result = await api('/api/incidents', {
        method: 'POST',
        body: JSON.stringify({
          report_text: reportText,
          title: fields.title || 'Emergency report',
          disaster_type: fields.disaster_type || 'unknown',
          location_name: fields.location_name || null,
          latitude: lat,
          longitude: lon,
          location_precision: fields.location_precision || 'unresolved',
          needs: (fields.needsText || '').split(',').map((item) => item.trim()).filter(Boolean),
          people_affected: numberOrNull(fields.people_affected),
          threat_level: fields.threat_level || 'unknown',
          time_criticality: numberOrNull(fields.time_criticality),
          vulnerability_level: numberOrNull(fields.vulnerability_level),
          hazard_escalation: numberOrNull(fields.hazard_escalation),
          access_difficulty: numberOrNull(fields.access_difficulty),
          source_type: sourceType,
          source_name: sourceName || null,
          is_firsthand: firsthand,
          independence_confirmed: independent,
        }),
      });
      setSaved(result);
      showToast('Report and incident saved to the local database.');
    } catch (err) {
      setError(err.message);
      showToast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  }

  async function readAndPreviewCsv(file = csvFile) {
    if (!file) {
      setCsvError('Choose a CSV file first.');
      return;
    }
    setCsvError('');
    setImportResult(null);
    setCsvBusy(true);
    try {
      const text = await file.text();
      setCsvText(text);
      const result = await api('/api/reports/preview-csv', {
        method: 'POST', body: text, headers: { 'Content-Type': 'text/csv' },
      });
      setCsvPreview(result);
    } catch (err) {
      setCsvError(err.message);
      setCsvPreview(null);
    } finally {
      setCsvBusy(false);
    }
  }

  async function importCsv() {
    if (!csvText || !csvPreview) return;
    setCsvError('');
    setCsvBusy(true);
    try {
      const result = await api('/api/reports/import', {
        method: 'POST', body: csvText, headers: { 'Content-Type': 'text/csv' },
      });
      setImportResult(result);
      setCsvPreview(null);
      setCsvFile(null);
      setCsvText('');
      showToast(`${result.imported} report${result.imported === 1 ? '' : 's'} imported and saved.`);
    } catch (err) {
      setCsvError(err.message);
      showToast(err.message, 'error');
    } finally {
      setCsvBusy(false);
    }
  }

  function setField(key, value) {
    setFields((current) => ({ ...current, [key]: value }));
  }

  return (
    <div className="page-content">
      <div className="page-intro page-intro-tight">
        <div><div className="eyebrow"><span className="eyebrow-dot" /> REPORT PROCESSING</div><h2>Report intake</h2><p>Turn fragmented messages into a reviewable record. Nothing is saved until a coordinator approves the extracted fields.</p></div>
      </div>
      <div className="intake-principle"><Info size={17} /><span><strong>Urgency and evidence are separate.</strong> A single uncertain report can still score high urgency and stays visible for urgent verification.</span></div>

      <div className="intake-layout">
        <section className="panel intake-main-panel">
          <div className="intake-tabs"><div className="intake-tab active"><FileText size={16} /> Manual report</div><button type="button" className="intake-tab intake-tab-button" onClick={() => document.getElementById('csv-import-panel')?.scrollIntoView({ behavior: 'smooth', block: 'center' })}><FileSpreadsheet size={16} /> CSV import</button></div>
          <div className="intake-section">
            <div className="intake-section-heading"><div><h3>1. Enter an incoming report</h3><p>SMS, field notes, or public posts can be messy. Keep the original text intact.</p></div><span className="step-number">01</span></div>
            <div className="example-row"><span>Try a synthetic example:</span>{examples.map((example) => <button className="example-chip" key={example.label} type="button" onClick={() => loadExample(example)}>{example.label}</button>)}</div>
            <form onSubmit={analyzeText}>
              <label className="stacked-label">Original report text<textarea rows="5" required minLength="5" maxLength="5000" value={reportText} onChange={(e) => { setReportText(e.target.value); setPreview(null); setSaved(null); }} placeholder="Paste a report exactly as received. Avoid adding unverified details…" /></label>
              <div className="source-form-row">
                <label>Source type<select value={sourceType} onChange={(e) => setSourceType(e.target.value)}><option value="sms">SMS</option><option value="field">Field report</option><option value="authorized">Authorized channel</option><option value="volunteer">Volunteer</option><option value="social">Social media</option><option value="phone">Phone call</option><option value="manual">Other / manual</option></select></label>
                <label>Source name / channel<input value={sourceName} onChange={(e) => setSourceName(e.target.value)} placeholder="Optional source label" /></label>
              </div>
              <div className="checkbox-row"><label><input type="checkbox" checked={firsthand} onChange={(e) => setFirsthand(e.target.checked)} /> Firsthand / field source</label><label><input type="checkbox" checked={independent} onChange={(e) => setIndependent(e.target.checked)} /> Independence confirmed by coordinator</label></div>
              <div className="form-actions"><button className="button button-primary" disabled={analyzing || reportText.trim().length < 5}>{analyzing ? <><span className="button-spinner" /> Extracting…</> : <><WandSparkles size={16} /> Extract for review</>}</button><span className="form-hint">Local rule-based extraction · no paid AI service</span></div>
            </form>
            {error && <div className="inline-error"><AlertTriangle size={15} /> {error}</div>}
            {saved && <div className="success-panel"><CheckCircle2 size={18} /><div><strong>Report saved · incident #{saved.id}</strong><span>{saved.new_duplicate_candidates?.length ? `${saved.new_duplicate_candidates.length} possible duplicate candidate(s) need human review.` : 'No duplicate candidates were identified.'} Incident data and original report are now stored.</span></div>{saved.new_duplicate_candidates?.length > 0 && <button className="text-button" type="button" onClick={() => navigate('/incidents')}>Review candidates</button>}</div>}
          </div>

          {preview && <div className="review-section">
            <div className="intake-section-heading"><div><h3>2. Review extracted information</h3><p>Correct or clear any field before saving. Unknown means not provided — it does not mean zero.</p></div><span className="step-number">02</span></div>
            <div className="preview-score-row"><div className="preview-score"><span>RULE URGENCY</span><strong>{preview.urgency.score}<small>/100</small></strong><em>{preview.urgency.level}</em></div><div className="preview-confidence-note"><Info size={16} /><span>Evidence confidence is assessed separately after saving. This score is a rule output, not a calibrated probability.</span></div></div>
            {preview.extracted.warnings?.length > 0 && <div className="warning-list">{preview.extracted.warnings.map((warning, index) => <div key={index}><AlertTriangle size={14} />{warning}</div>)}</div>}
            <form className="review-form" onSubmit={saveIncident}>
              <div className="form-grid-two">
                <label className="form-grid-wide">Suggested incident title<input value={fields.title || ''} onChange={(e) => setField('title', e.target.value)} maxLength={200} /></label>
                <label>Disaster type<select value={fields.disaster_type || 'unknown'} onChange={(e) => setField('disaster_type', e.target.value)}><option value="unknown">Unknown</option><option value="flood">Flood</option><option value="earthquake">Earthquake</option><option value="landslide">Landslide</option><option value="fire">Fire</option><option value="storm">Storm</option><option value="other">Other</option></select></label>
                <label>Location name<input value={fields.location_name || ''} onChange={(e) => setField('location_name', e.target.value)} placeholder="Unresolved unless explicit" /></label>
                <label>Location precision<select value={fields.location_precision || 'unresolved'} onChange={(e) => setField('location_precision', e.target.value)}><option value="unknown">Unknown</option><option value="unresolved">Unresolved</option><option value="approximate">Approximate</option><option value="verified">Verified</option></select></label>
                <label>People affected<input type="number" min="0" value={fields.people_affected ?? ''} onChange={(e) => setField('people_affected', e.target.value)} placeholder="Unknown" /></label>
                <label>Threat to life<select value={fields.threat_level || 'unknown'} onChange={(e) => setField('threat_level', e.target.value)}><option value="unknown">Unknown</option><option value="none">No threat reported</option><option value="possible">Possible</option><option value="serious">Serious</option><option value="immediate">Immediate</option></select></label>
                <label>Time criticality (0–4)<input type="number" min="0" max="4" value={fields.time_criticality ?? ''} onChange={(e) => setField('time_criticality', e.target.value)} placeholder="Unknown" /></label>
                <label>Vulnerability (0–4)<input type="number" min="0" max="4" value={fields.vulnerability_level ?? ''} onChange={(e) => setField('vulnerability_level', e.target.value)} placeholder="Unknown" /></label>
                <label>Hazard escalation (0–4)<input type="number" min="0" max="4" value={fields.hazard_escalation ?? ''} onChange={(e) => setField('hazard_escalation', e.target.value)} placeholder="Unknown" /></label>
                <label>Access difficulty (0–4)<input type="number" min="0" max="4" value={fields.access_difficulty ?? ''} onChange={(e) => setField('access_difficulty', e.target.value)} placeholder="Unknown" /></label>
                <label className="form-grid-wide">Reported needs, comma separated<input value={fields.needsText ?? (fields.needs || []).join(', ')} onChange={(e) => setField('needsText', e.target.value)} placeholder="Leave empty if no need was mentioned" /></label>
                <label>Latitude (optional)<input type="number" step="any" value={fields.latitude ?? ''} onChange={(e) => setField('latitude', e.target.value)} placeholder="Do not guess coordinates" /></label>
                <label>Longitude (optional)<input type="number" step="any" value={fields.longitude ?? ''} onChange={(e) => setField('longitude', e.target.value)} placeholder="Both coordinates required" /></label>
              </div>
              <div className="rule-explain"><strong>Urgency inputs and weights</strong><span>Threat to life 35 · Time criticality 20 · People affected 15 · Vulnerability 10 · Escalation 10 · Access 10</span><small>Configurable prototype rules only; not an operational standard.</small></div>
              <div className="form-actions"><button className="button button-primary" disabled={saving}>{saving ? <><span className="button-spinner" /> Saving…</> : <>Save incident <ArrowRight size={16} /></>}</button><button type="button" className="button button-secondary" onClick={() => setPreview(null)}>Back to report</button></div>
            </form>
          </div>}
        </section>

        <aside className="intake-side-column">
          <section className="panel csv-panel" id="csv-import-panel">
            <div className="side-panel-title"><span className="side-panel-icon"><FileSpreadsheet size={18} /></span><div><h3>Batch CSV import</h3><p>Preview rows before they are written.</p></div></div>
            <div className="csv-dropzone"><UploadCloud size={24} /><strong>Choose a CSV file</strong><span>UTF-8 · max 2 MB · up to 500 reports</span><input type="file" accept=".csv,text/csv" onChange={(event) => { setCsvFile(event.target.files?.[0] || null); setCsvPreview(null); setImportResult(null); setCsvError(''); }} /><small>{csvFile ? csvFile.name : 'Headers: text, source_type, source_name, reported_at, location_name, latitude, longitude, needs…'}</small></div>
            <div className="csv-actions"><button className="button button-secondary button-full" disabled={!csvFile || csvBusy} onClick={() => readAndPreviewCsv()}>{csvBusy && !importResult ? <><span className="button-spinner" /> Working…</> : 'Preview CSV extraction'}</button></div>
            {csvError && <div className="inline-error"><AlertTriangle size={14} />{csvError}</div>}
            {csvPreview && <div className="csv-preview-summary"><div className="csv-summary-head"><strong>{csvPreview.count} rows ready for review</strong><span>Not saved yet</span></div><div className="csv-preview-table">{csvPreview.items.map((row) => <div className="csv-preview-row" key={row.row}><strong>Row {row.row} · {row.extracted.disaster_type} · urgency {row.urgency.score}/100</strong><span>{row.extracted.location_name || 'Location unresolved'} · {row.extracted.people_affected ?? 'People count unknown'}</span><small>Needs: {row.extracted.needs?.length ? row.extracted.needs.join(', ') : 'unknown'} · Threat: {row.extracted.threat_level || 'unknown'}</small><small>Source: {row.source_type}{row.source_name ? ` · ${row.source_name}` : ''} · {row.is_firsthand ? 'firsthand' : 'firsthand unknown'} · {row.independence_confirmed ? 'independent confirmed' : 'independence not confirmed'}</small><p>{row.original_text}</p>{row.warnings?.map((warning, index) => <em key={index}>{warning}</em>)}</div>)}</div><button className="button button-primary button-full" disabled={csvBusy} onClick={importCsv}>{csvBusy ? 'Importing…' : `Import ${csvPreview.count} reports`}</button><p className="tiny-caution">Possible duplicates are identified only after import and remain separate until a coordinator confirms a merge.</p></div>}
            {importResult && <div className="import-result"><CheckCircle2 size={16} /><div><strong>{importResult.imported} reports saved</strong><span>{importResult.possible_duplicates?.length ? `${importResult.possible_duplicates.length} duplicate candidate(s) need review.` : 'No possible duplicates found.'}</span></div>{importResult.possible_duplicates?.length > 0 && <button className="text-button" type="button" onClick={() => navigate('/incidents')}>Review candidates</button>}</div>}
          </section>
          <section className="panel intake-help-panel"><h3>Safe intake checklist</h3><ul><li>Preserve the original message and source.</li><li>Do not invent a location or population count.</li><li>Similar copies are not independent confirmation.</li><li>Unknown information remains visible as unknown.</li><li>Human review is required before consequential action.</li></ul></section>
          <div className="synthetic-callout"><Info size={15} /><span>The included seeded dataset uses fictional incident names and synthetic geographic cells for demonstration only.</span></div>
        </aside>
      </div>
    </div>
  );
}
