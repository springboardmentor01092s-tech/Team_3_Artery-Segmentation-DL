export type NotificationFormat = 'PDF' | 'JSON' | 'CSV'
export type ReportDownloadNotification = {
  id: string
  format?: NotificationFormat
  filename?: string
  message: string
  createdAt: string
  read: boolean
}

export declare function createReportDownloadNotification(format: NotificationFormat, filename: string, now?: Date): ReportDownloadNotification
export declare function createMessageNotification(message: string, now?: Date): ReportDownloadNotification
export declare function createUserManagementNotification(message: string, now?: Date): ReportDownloadNotification
export declare function markNotificationsRead(notifications: ReportDownloadNotification[]): ReportDownloadNotification[]
export declare function unreadNotificationCount(notifications: ReportDownloadNotification[]): number
