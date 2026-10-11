import { useMemo, useState } from 'react';
import { CircleMarker, MapContainer, Popup, TileLayer, ZoomControl } from 'react-leaflet';
import { ExternalLink, MapPinOff } from 'lucide-react';
import { UrgencyBadge } from './StatusBadge.jsx';

function severityColor(score = 0) {
  if (score >= 80) return '#c2413b';
  if (score >= 60) return '#d97706';
  if (score >= 35) return '#2f6fbe';
  return '#54806c';
}

export default function IncidentMap({ incidents = [], coverage = [], showCoverage = false, onSelectIncident, className = '' }) {
  const [tileError, setTileError] = useState(false);
  const locatedIncidents = useMemo(() => incidents.filter((item) =>
    item.latitude !== null && item.latitude !== undefined && item.longitude !== null && item.longitude !== undefined && item.status !== 'merged'
  ), [incidents]);
  const visibleCoverage = showCoverage ? coverage : [];
  const center = locatedIncidents.length ? [locatedIncidents[0].latitude, locatedIncidents[0].longitude] : [13.02, 77.60];

  return (
    <div className={`map-frame ${className}`}>
      <MapContainer center={center} zoom={locatedIncidents.length ? 9 : 8} scrollWheelZoom zoomControl={false} className="leaflet-map">
        <ZoomControl position="bottomright" />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          eventHandlers={{ tileerror: () => setTileError(true), tileload: () => setTileError(false) }}
        />
        {locatedIncidents.map((incident) => {
          const color = severityColor(incident.priority_score ?? incident.urgency_score);
          const verificationColor = incident.status === 'verified' ? '#25634b' : incident.status === 'unverified' || incident.status === 'needs_info' ? '#b66b00' : color;
          return (
            <CircleMarker
              key={`incident-${incident.id}`}
              center={[incident.latitude, incident.longitude]}
              radius={incident.priority_score >= 80 ? 11 : 9}
              pathOptions={{ color: verificationColor, weight: 3, fillColor: color, fillOpacity: 0.82 }}
            >
              <Popup className="rescue-popup">
                <div className="map-popup-content">
                  <div className="map-popup-kicker">{incident.disaster_type || 'incident'} · {incident.status?.replaceAll('_', ' ')}</div>
                  <strong>{incident.title}</strong>
                  <div className="map-popup-location">{incident.location_name || 'Location not resolved'}{incident.location_precision === 'approximate' ? ' · approximate' : ''}</div>
                  <div className="map-popup-badges"><UrgencyBadge score={incident.priority_score ?? incident.urgency_score} level={incident.priority_level || incident.urgency_level} /></div>
                  {onSelectIncident && <button type="button" className="text-button map-open" onClick={() => onSelectIncident(incident.id)}>Open incident <ExternalLink size={13} /></button>}
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
        {visibleCoverage.map((area, index) => area.latitude != null && area.longitude != null && (
          <CircleMarker
            key={`coverage-${area.area_name}-${index}`}
            center={[area.latitude, area.longitude]}
            radius={18}
            pathOptions={{ color: '#c47b13', weight: 2, dashArray: '5 5', fillColor: '#e8ab47', fillOpacity: 0.16 }}
          >
            <Popup>
              <div className="map-popup-content">
                <div className="map-popup-kicker">REPORTING GAP · {area.hazard_exposure} exposure</div>
                <strong>{area.area_name}</strong>
                <p>{area.reasons?.[0] || 'Reporting information is limited.'}</p>
                <small>Last known information: {area.last_known_info_at ? new Date(area.last_known_info_at).toLocaleString() : 'not recorded'}</small>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
      {tileError && (
        <div className="map-tile-warning"><MapPinOff size={15} /><span>Map tiles are unavailable. Markers and records remain usable; reconnect to view the OpenStreetMap basemap.</span></div>
      )}
      <div className="map-scale-legend">
        <span><i className="legend-dot legend-critical" /> Critical / high</span>
        <span><i className="legend-dot legend-standard" /> Other incidents</span>
        {showCoverage && <span><i className="legend-ring" /> Reporting gap</span>}
      </div>
      {!locatedIncidents.length && !visibleCoverage.length && (
        <div className="map-empty"><MapPinOff size={17} /> No incidents with confirmed coordinates. Unresolved reports stay off the map.</div>
      )}
      {locatedIncidents.length === 0 && visibleCoverage.length > 0 && (
        <div className="map-empty map-empty-small">No incident coordinates available; showing coverage cells only.</div>
      )}
    </div>
  );
}
