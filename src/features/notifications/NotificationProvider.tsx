import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { createMessageNotification, createReportDownloadNotification, createUserManagementNotification, markNotificationsRead, unreadNotificationCount } from './notification-state.mjs'
import type { NotificationFormat, ReportDownloadNotification } from './notification-state.mjs'

export type ReportDownloadNotice = ReportDownloadNotification

type NotificationContextValue = {
  notifications: ReportDownloadNotice[]
  addReportDownload: (format: NotificationFormat, filename: string) => void
  addMessageNotification: (message: string) => void
  addUserManagementNotice: (message: string) => void
  unreadCount: number
  markAllRead: () => void
}

const NotificationContext = createContext<NotificationContextValue | null>(null)

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<ReportDownloadNotice[]>([])

  const addReportDownload = useCallback((format: NotificationFormat, filename: string) => {
    const notice = createReportDownloadNotification(format, filename)
    setNotifications((current) => [notice, ...current].slice(0, 8))
  }, [])

  const addUserManagementNotice = useCallback((message: string) => {
    const notice = createUserManagementNotification(message)
    setNotifications((current) => [notice, ...current].slice(0, 8))
  }, [])

  const addMessageNotification = useCallback((message: string) => {
    const notice = createMessageNotification(message)
    setNotifications((current) => [notice, ...current].slice(0, 8))
  }, [])

  const markAllRead = useCallback(() => setNotifications((current) => markNotificationsRead(current)), [])
  const unreadCount = unreadNotificationCount(notifications)
  const value = useMemo(() => ({ notifications, addReportDownload, addMessageNotification, addUserManagementNotice, unreadCount, markAllRead }), [notifications, addReportDownload, addMessageNotification, addUserManagementNotice, unreadCount, markAllRead])
  return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>
}

export function useNotifications() {
  const context = useContext(NotificationContext)
  if (!context) throw new Error('useNotifications must be used within NotificationProvider')
  return context
}
