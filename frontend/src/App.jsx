import { lazy, Suspense, useEffect, useState } from 'react';
import { BrowserRouter, NavLink, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import {
  Activity, AlertTriangle, ClipboardList, FileInput, LayoutDashboard, MapPinned,
  Menu, ShieldAlert, X, BookOpenCheck, Boxes, Settings,
} from 'lucide-react';
import { ToastProvider } from './components/ToastProvider.jsx';
import { api } from './api.js';
const OverviewPage = lazy(() => import('./pages/OverviewPage.jsx'));
const IncidentsPage = lazy(() => import('./pages/IncidentsPage.jsx'));
const IntakePage = lazy(() => import('./pages/IntakePage.jsx'));
const MapPage = lazy(() => import('./pages/MapPage.jsx'));
const CoveragePage = lazy(() => import('./pages/CoveragePage.jsx'));
const ResourcesPage = lazy(() => import('./pages/ResourcesPage.jsx'));
const AuditPage = lazy(() => import('./pages/AuditPage.jsx'));
const SettingsPage = lazy(() => import('./pages/SettingsPage.jsx'));


const navigation = [
  { label: 'Overview', to: '/', icon: LayoutDashboard, end: true },
  { label: 'Incident register', to: '/incidents', icon: ClipboardList },
  { label: 'Report intake', to: '/intake', icon: FileInput },
  { label: 'Operations map', to: '/map', icon: MapPinned },
  { label: 'Reporting gaps', to: '/coverage', icon: AlertTriangle },
  { label: 'Resources', to: '/resources', icon: Boxes },
  { label: 'Decision log', to: '/audit', icon: BookOpenCheck },
  { label: 'Settings', to: '/settings', icon: Settings },
];

const pageTitles = {
  '/': 'Operations overview',
  '/incidents': 'Incident register',
  '/intake': 'Report intake',
  '/map': 'Operations map',
  '/coverage': 'Reporting-gap monitor',
  '/resources': 'Resource tracking & inventory',
  '/audit': 'Decision log',
  '/settings': 'Settings & Demo Controls',
};

function Shell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [apiStatus, setApiStatus] = useState('checking');
  const location = useLocation();
  const title = pageTitles[location.pathname] || 'Response desk';

  useEffect(() => {
    let active = true;
    const checkHealth = async () => {
      try {
        await api('/api/health');
        if (active) setApiStatus('online');
      } catch {
        if (active) setApiStatus('offline');
      }
    };
    checkHealth();
    const timer = window.setInterval(checkHealth, 30000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  return (
    <div className="app-shell">
      {mobileOpen && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <div className="brand-row">
          <div className="brand-mark"><ShieldAlert size={22} strokeWidth={2.1} /></div>
          <div className="brand-copy"><strong>RescueGrid</strong><span>AI RESPONSE DESK</span></div>
          <button className="icon-button sidebar-close" onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X size={19} /></button>
        </div>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="sidebar-nav" aria-label="Main navigation">
          {navigation.map(({ label, to, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={() => setMobileOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}>
              <Icon size={18} strokeWidth={1.9} /><span>{label}</span>
              {label === 'Reporting gaps' && <span className="nav-dot" />}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note-icon"><Activity size={16} /></div>
          <div><strong>Decision support only</strong><p>Human coordinators approve all consequential actions.</p></div>
        </div>
        <div className="sidebar-version">LOCAL PROTOTYPE <span>v1.0</span></div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={21} /></button>
          <div className="topbar-title"><div className="breadcrumb">RESPONSE DESK <span>/</span> {title.toUpperCase()}</div><h1>{title}</h1></div>
          <div className="topbar-right">
            <span className={`api-health-pill api-${apiStatus}`} title={apiStatus === 'online' ? 'FastAPI service is responding' : 'Checking the FastAPI service'}><span /> {apiStatus === 'online' ? 'API ONLINE' : apiStatus === 'offline' ? 'API OFFLINE' : 'API CHECKING'}</span>
            <span className="simulation-pill"><span className="simulation-dot" /> SYNTHETIC DEMO</span>
            <div className="user-avatar" title="Local coordinator session">C</div>
          </div>
        </header>
        <main className="workspace"><Suspense fallback={<div className="page-loading"><span className="spinner" /> Opening workspace…</div>}><Outlet /></Suspense></main>
        <footer className="page-footer"><span>RescueGrid AI · Local decision-support prototype</span><span>Not for real-world dispatch or safety decisions</span></footer>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <Routes>
          <Route element={<Shell />}>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/incidents" element={<IncidentsPage />} />
            <Route path="/intake" element={<IntakePage />} />
            <Route path="/map" element={<MapPage />} />
            <Route path="/coverage" element={<CoveragePage />} />
            <Route path="/resources" element={<ResourcesPage />} />
            <Route path="/audit" element={<AuditPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </ToastProvider>
    </BrowserRouter>
  );
}
