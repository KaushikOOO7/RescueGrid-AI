export function StatusBadge({ status }) {
  const value = (status || 'unknown').toLowerCase();
  const label = value.replaceAll('_', ' ');
  return <span className={`status-badge status-${value}`}>{label}</span>;
}

export function UrgencyBadge({ score, level }) {
  const label = level || (score >= 80 ? 'critical' : score >= 60 ? 'high' : score >= 35 ? 'elevated' : 'routine');
  return <span className={`urgency-badge urgency-${label.toLowerCase()}`}>{label} <span>{score ?? '—'}</span></span>;
}
