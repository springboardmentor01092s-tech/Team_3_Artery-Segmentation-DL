import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createReportDownloadNotification, markNotificationsRead, unreadNotificationCount } from '../src/features/notifications/notification-state.mjs'

test('opening the notification panel can mark unread entries read without removing them', () => {
  const first = createReportDownloadNotification('PDF', 'report.pdf', new Date('2026-11-14T10:00:00Z'))
  const second = createReportDownloadNotification('CSV', 'report.csv', new Date('2026-11-14T10:01:00Z'))
  const notifications = [first, second]
  assert.equal(unreadNotificationCount(notifications), 2)
  const readNotifications = markNotificationsRead(notifications)
  assert.equal(readNotifications.length, 2)
  assert.equal(unreadNotificationCount(readNotifications), 0)
  const laterNotice = createReportDownloadNotification('JSON', 'report.json', new Date('2026-11-14T10:02:00Z'))
  assert.equal(unreadNotificationCount([laterNotice, ...readNotifications]), 1)
})

test('TopBar marks unread notices when opening and renders the dot only for unread entries', async () => {
  const source = await readFile(new URL('../src/components/TopBar.tsx', import.meta.url), 'utf8')
  assert.match(source, /if \(!notificationsOpen\) markAllRead\(\)/)
  assert.match(source, /unreadCount > 0 && <span className="notification-dot"/)
  assert.match(source, /notifications\.map\(\(notice\)/)
})
