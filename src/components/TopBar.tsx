import { Bell, ChevronDown, Search } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import Brand from './Brand'
import { useAuth } from '../auth/AuthProvider'

export default function TopBar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="topbar">
      <Link to="/dashboard" className="topbar__brand" aria-label="Artery Analysis System dashboard"><Brand /></Link>
      <label className="global-search">
        <Search size={17} aria-hidden="true" />
        <input type="search" placeholder="Search cases, patients, or reports..." aria-label="Search" />
        <kbd>⌘ K</kbd>
      </label>
      <div className="topbar__right">
        <button className="icon-button notification-button" type="button" aria-label="Notifications">
          <Bell size={20} aria-hidden="true" />
        </button>
        <button className="profile-button" type="button" onClick={handleLogout} aria-label="Sign out">
          <span className="avatar">{user?.email.slice(0, 1).toUpperCase() ?? 'U'}</span>
          <span className="profile-button__text"><strong>{user?.email ?? 'User'}</strong><small>{user?.role === 'admin' ? 'Administrator' : 'Regular user'} · Sign out</small></span>
          <ChevronDown size={16} aria-hidden="true" />
        </button>
      </div>
    </header>
  )
}
