import { useEffect, useState } from 'react';
import PublicPages from './PublicPages';
import AttendeeApp from './AttendeeApp';
import OrganizerApp from './OrganizerApp';
import PlatformAdminApp from './PlatformAdminApp';
import { Topbar, Link } from './app-shared';
import './ProductApp.css';

export default function ProductApp() {
  const [hash, setHash] = useState(location.hash);
  useEffect(() => { const update = () => setHash(location.hash); window.addEventListener('hashchange', update); return () => window.removeEventListener('hashchange', update); }, []);
  const path = hash.replace(/^#/, '') || '/events';
  if (path.startsWith('/account')) return <AttendeeApp path={path}/>;
  if (path.startsWith('/organizer')) return <OrganizerApp path={path}/>;
  if (path.startsWith('/admin')) return <PlatformAdminApp path={path}/>;
  if (path === '/') return <><Topbar/><main className="bf-public bf-home-bridge"><span className="bf-kicker">WELCOME TO BILETFLOW</span><h1>Make room for<br/><em>something memorable.</em></h1><p>Discover what’s happening around you.</p><Link to="/events" className="bf-button">Explore events <span>→</span></Link><div className="bf-bridge-links"><Link to="/login">Sign in</Link><Link to="/organizer">Organizer workspace</Link><Link to="/admin">Platform admin</Link></div></main></>;
  return <PublicPages path={path}/>;
}
