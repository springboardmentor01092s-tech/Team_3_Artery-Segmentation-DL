import {
  ChartNoAxesCombined, ClipboardList, FileText, House,
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

export default function Sidebar({ collapsed = false, mobileOpen = false, onNavigate }: {
  collapsed?: boolean
  mobileOpen?: boolean
  onNavigate?: () => void
}) {
  const { user } = useAuth()
  return (
    <aside className={`sidebar${collapsed ? ' sidebar--collapsed' : ''}${mobileOpen ? ' sidebar--mobile-open' : ''}`}>
      <div className="sidebar__mobile-brand"><Brand /></div>
      <nav className="sidebar__nav" id="primary-navigation" aria-label="Main navigation">
        <div className="sidebar__nav-main">
          {links.map(({ label, to, icon: Icon }) => (
            <NavLink key={label} to={to} title={collapsed && !mobileOpen ? label : undefined} aria-label={label} onClick={onNavigate} className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}>
              <Icon size={19} strokeWidth={2.1} aria-hidden="true" /><span>{label}</span>
            </NavLink>
          ))}
        </div>
        <div className="sidebar__nav-bottom">
          <div className="sidebar__divider" />
          {user?.role === 'admin' && <NavLink to="/users" title={collapsed && !mobileOpen ? 'Users' : undefined} aria-label="Users" onClick={onNavigate} className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}>
            <UsersRound size={19} strokeWidth={2.1} aria-hidden="true" /><span>Users</span>
          </NavLink>}
          <NavLink to="/settings" title={collapsed && !mobileOpen ? 'Settings' : undefined} aria-label="Settings" onClick={onNavigate} className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}>
            <Settings size={19} strokeWidth={2.1} aria-hidden="true" /><span>Settings</span>
          </NavLink>
        </div>
      </nav>
    </aside>
  )
}
