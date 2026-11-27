export type UserManagementRecord = {
  id: string
  full_name: string | null
  email: string
  role: 'admin' | 'user'
  is_active: boolean
  must_change_password: boolean
  created_at: string
}

export function filterAndSortUsers(
  users: UserManagementRecord[],
  options?: { query?: string; role?: 'all' | 'admin' | 'user'; status?: 'all' | 'active' | 'inactive'; sort?: 'newest' | 'oldest' | 'name-asc' | 'name-desc' },
): UserManagementRecord[]

export function getUserPage<T>(users: T[], requestedPage: number, pageSize?: number): {
  items: T[]
  page: number
  pageCount: number
  start: number
  end: number
  total: number
}

export function getUserActionAvailability(
  selectedUser: UserManagementRecord | null,
  currentUser: Pick<UserManagementRecord, 'id'> | null,
  users: UserManagementRecord[],
): { canChangeRole: boolean; canDeactivate: boolean; canResetPassword: boolean }

export function getCleanupStatusErrorMessage(error: unknown): string
