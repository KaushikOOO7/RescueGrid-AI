export default function StatCard({ label, value, detail, icon: Icon, tone = 'blue', onClick }) {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag className={`stat-card stat-${tone} ${onClick ? 'stat-clickable' : ''}`} onClick={onClick} type={onClick ? 'button' : undefined}>
      <div className="stat-card-top">
        <span className="stat-label">{label}</span>
        <span className="stat-icon">{Icon && <Icon size={18} strokeWidth={2} />}</span>
      </div>
      <div className="stat-value">{value ?? '—'}</div>
      <div className="stat-detail">{detail}</div>
    </Tag>
  );
}
