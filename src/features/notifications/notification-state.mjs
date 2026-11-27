export function createReportDownloadNotification(format, filename, now = new Date()) {
  return {
    id: `${now.getTime()}-${format}-${filename}`,
    format,
    filename,
    message: `${format} report download started`,
    createdAt: now.toISOString(),
    read: false,
  }
}

export function createMessageNotification(message, now = new Date()) {
  return {
    id: `${now.getTime()}-notice-${message}`,
    message,
    createdAt: now.toISOString(),
    read: false,
  }
}

export function createUserManagementNotification(message, now = new Date()) {
  return createMessageNotification(message, now)
}

export function markNotificationsRead(notifications) {
  return notifications.map((notification) => notification.read ? notification : { ...notification, read: true })
}

export function unreadNotificationCount(notifications) {
  return notifications.filter((notification) => !notification.read).length
}
