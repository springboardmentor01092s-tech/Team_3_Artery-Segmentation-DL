import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'

const SIDEBAR_PREFERENCE_KEY = 'artery-analysis:sidebar-collapsed:v2'

function readCollapsedPreference() {
  try {
    const preference = window.localStorage.getItem(SIDEBAR_PREFERENCE_KEY)
    return preference === null ? true : preference === 'true'
  } catch {
    return true
  }
}

export default function AppShell() {
  const location = useLocation()
  const [isCollapsed, setIsCollapsed] = useState(readCollapsedPreference)
  const [isNarrowViewport, setIsNarrowViewport] = useState(() => window.matchMedia('(max-width: 880px)').matches)
  const [isMobileOpen, setIsMobileOpen] = useState(false)

  useEffect(() => {
    const media = window.matchMedia('(max-width: 880px)')
    const syncViewport = (event: MediaQueryListEvent) => {
      setIsNarrowViewport(event.matches)
      setIsMobileOpen(false)
    }
    media.addEventListener('change', syncViewport)
    return () => media.removeEventListener('change', syncViewport)
  }, [])

  useEffect(() => {
    try {
      window.localStorage.setItem(SIDEBAR_PREFERENCE_KEY, String(isCollapsed))
    } catch {
      // The sidebar remains usable when browser storage is unavailable.
    }
  }, [isCollapsed])

  useEffect(() => {
    if (!isMobileOpen) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setIsMobileOpen(false)
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [isMobileOpen])

  function toggleSidebar() {
    if (isNarrowViewport) setIsMobileOpen((open) => !open)
    else setIsCollapsed((collapsed) => !collapsed)
  }

  function closeMobileSidebar() {
    if (isNarrowViewport) setIsMobileOpen(false)
  }

  return (
    <div className={`app-frame${location.pathname === '/dashboard' ? ' app-frame--dashboard' : ''}`}>
      <TopBar onMenuToggle={toggleSidebar} menuExpanded={isNarrowViewport ? isMobileOpen : !isCollapsed} />
      <div className="app-body">
        <Sidebar collapsed={isCollapsed} mobileOpen={isMobileOpen} onNavigate={closeMobileSidebar} />
        {isNarrowViewport && isMobileOpen && <button className="sidebar-backdrop" type="button" aria-label="Close navigation menu" onClick={() => setIsMobileOpen(false)} />}
        <main className="main-content"><Outlet /></main>
      </div>
    </div>
  )
}
