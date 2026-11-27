import { useEffect, useRef, useState } from 'react'
import { Bell, Menu } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import Brand from './Brand'
import { useAuth } from '../auth/AuthProvider'
import { useNotifications } from '../features/notifications/NotificationProvider'

export default function TopBar({ onMenuToggle, menuExpanded }: { onMenuToggle: () => void; menuExpanded: boolean }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { notifications, unreadCount, markAllRead } = useNotifications()
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const notificationMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!notificationsOpen) return
    const closeOnOutsideClick = (event: PointerEvent) => {
      if (event.target instanceof Node && !notificationMenuRef.current?.contains(event.target)) setNotificationsOpen(false)
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setNotificationsOpen(false)
    }
    document.addEventListener('pointerdown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsideClick)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [notificationsOpen])

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  function toggleNotifications() {
    if (!notificationsOpen) markAllRead()
    setNotificationsOpen((open) => !open)
  }

  return (
    <header className="topbar">
      <button className="topbar-menu-button" type="button" aria-label={menuExpanded ? 'Close navigation' : 'Open navigation'} aria-expanded={menuExpanded} aria-controls="primary-navigation" onClick={onMenuToggle}>
        <Menu size={20} strokeWidth={2} aria-hidden="true" />
      </button>
      <Link to="/dashboard" className="topbar__brand" aria-label="CoronAI dashboard"><Brand /></Link>
      <div className="topbar__right">
        <div className="notification-menu" ref={notificationMenuRef}>
          <button className="icon-button notification-button" type="button" aria-label="Notifications" aria-expanded={notificationsOpen} aria-controls="notification-panel" onClick={toggleNotifications}>
            <Bell size={20} aria-hidden="true" />
            {unreadCount > 0 && <span className="notification-dot" aria-hidden="true" />}
          </button>
          {notificationsOpen && <section className="notification-panel" id="notification-panel" aria-label="Recent notifications">
            <div className="notification-panel__heading"><strong>Notifications</strong><span>{notifications.length}</span></div>
            {notifications.length ? <ul className="notification-list">
              {notifications.map((notice) => <li className="notification-list__item" key={notice.id}>
                <strong>{notice.message}</strong>
                {notice.filename && <span>{notice.filename}</span>}
                <time dateTime={notice.createdAt}>{new Date(notice.createdAt).toLocaleString()}</time>
              </li>)}
            </ul> : <p className="notification-empty">No notifications yet.</p>}
          </section>}
        </div>
        <div className="profile-actions">
          <span className="avatar" aria-hidden="true">{user?.email.slice(0, 1).toUpperCase() ?? 'U'}</span>
          <button className="button button--secondary profile-signout" type="button" onClick={handleLogout}>Sign out</button>
        </div>
      </div>
    </header>
  )
}
