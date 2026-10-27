import {
  BellRing, ChartNoAxesCombined, ClipboardList, FileText, House,
  ImagePlus, Settings, UsersRound,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'
import Brand from './Brand'
import { useAuth } from '../auth/AuthProvider'

const links = [
  { label: 'Dashboard', to: '/dashboard', icon: House },
  { label: 'Patients', to: '/patients', icon: UsersRound },
  { label: 'Cases', to: '/cases', icon: ClipboardList },
  { label: 'Image Upload & Analysis', to: '/upload', icon: ImagePlus },
  { label: 'Results', to: '/results', icon: ChartNoAxesCombined },
  { label: 'Reports', to: '/reports', icon: FileText },
]

export default function Sidebar() {
  const { user } = useAuth()
  return (
    <aside className="sidebar">
      <div className="sidebar__mobile-brand"><Brand /></div>
      <nav className="sidebar__nav" aria-label="Main navigation">
        {links.map(({ label, to, icon: Icon }) => (
          <NavLink key={label} to={to} className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}>
            <Icon size={19} strokeWidth={2.1} aria-hidden="true" /><span>{label}</span>
          </NavLink>
        ))}
        <div className="sidebar__divider" />
        {user?.role === 'admin' && <NavLink to="/users" className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}>
          <UsersRound size={19} strokeWidth={2.1} aria-hidden="true" /><span>Users</span>
        </NavLink>}
        <NavLink to="/settings" className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}>
          <Settings size={19} strokeWidth={2.1} aria-hidden="true" /><span>Settings</span>
        </NavLink>
      </nav>
      <div className="sidebar__footer">
        <div className="sidebar__security-icon"><BellRing size={16} aria-hidden="true" /></div>
        <div><strong>Private workspace</strong><span>Frontend preview</span></div>
      </div>
    </aside>
  )
}
