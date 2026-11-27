import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { filterAndSortUsers, getCleanupStatusErrorMessage, getUserActionAvailability, getUserPage } from '../src/features/users/user-management.mjs'

const records = [
  { id: 'u1', full_name: 'Alex Admin', email: 'alex@example.test', role: 'admin', is_active: true, created_at: '2026-02-01T00:00:00Z' },
  { id: 'u2', full_name: 'Bea User', email: 'bea@example.test', role: 'user', is_active: false, created_at: '2026-02-03T00:00:00Z' },
  { id: 'u3', full_name: null, email: 'casey@example.test', role: 'user', is_active: true, created_at: '2026-02-02T00:00:00Z' },
]

test('user search, role/status filtering and sorting use actual account fields', () => {
  assert.deepEqual(filterAndSortUsers(records, { query: 'bea@', role: 'user', status: 'inactive' }).map((item) => item.id), ['u2'])
  assert.deepEqual(filterAndSortUsers(records, { query: 'casey', status: 'active' }).map((item) => item.id), ['u3'])
  assert.deepEqual(filterAndSortUsers(records, { sort: 'newest' }).map((item) => item.id), ['u2', 'u3', 'u1'])
  assert.deepEqual(filterAndSortUsers(records, { sort: 'oldest' }).map((item) => item.id), ['u1', 'u3', 'u2'])
  assert.deepEqual(filterAndSortUsers(records, { sort: 'name-asc' }).map((item) => item.id), ['u3', 'u1', 'u2'])
})

test('user pagination clamps page and reports an accurate range', () => {
  const rows = Array.from({ length: 23 }, (_, index) => index)
  const second = getUserPage(rows, 2, 10)
  assert.deepEqual({ page: second.page, pageCount: second.pageCount, start: second.start, end: second.end }, { page: 2, pageCount: 3, start: 11, end: 20 })
  const last = getUserPage(rows, 20, 10)
  assert.deepEqual({ page: last.page, start: last.start, end: last.end }, { page: 3, start: 21, end: 23 })
})

test('user action rules prevent self-deactivation and last-admin removal', () => {
  const self = getUserActionAvailability(records[0], { id: 'u1' }, records)
  assert.equal(self.canDeactivate, false)
  assert.equal(self.canResetPassword, false)
  assert.equal(self.canChangeRole, false)

  const onlyAdmin = getUserActionAvailability(records[0], { id: 'other-admin' }, [records[0]])
  assert.equal(onlyAdmin.canChangeRole, false)
  assert.equal(onlyAdmin.canDeactivate, false)

  const anotherAdminAvailable = getUserActionAvailability(records[0], { id: 'other-admin' }, [records[0], { ...records[0], id: 'u4' }])
  assert.equal(anotherAdminAvailable.canChangeRole, true)
  assert.equal(anotherAdminAvailable.canDeactivate, true)
})

test('Users page uses authenticated user APIs and does not invent last-login data', async () => {
  const page = await readFile(new URL('../src/pages/UsersPage.tsx', import.meta.url), 'utf8')
  const dialog = await readFile(new URL('../src/features/users/UserManagementDialog.tsx', import.meta.url), 'utf8')
  assert.match(page, /apiRequest<UserManagementRecord\[]>\('\/users'\)/)
  assert.match(page, /`\/users\/\$\{selectedUser\.id\}\/role`/)
  assert.match(page, /`\/users\/\$\{selectedUser\.id\}\/status`/)
  assert.match(page, /`\/users\/\$\{selectedUser\.id\}\/password-reset`/)
  assert.match(page, /Last login[\s\S]*?Not available/)
  assert.match(dialog, /full_name/)
  assert.match(dialog, /temporary_password|onResetPassword/)
  assert.match(page, /`\/users\/\$\{selectedUser\.id\}`[\s\S]*?method: 'DELETE'/)
  assert.match(page, /selectedUser\?\.role === 'user'[\s\S]*?Delete user/)
  assert.match(dialog, /Delete User and All Associated Data/)
  assert.match(dialog, /deleteConfirmed/)
  assert.doesNotMatch(page, /Role permissions|Administrator access – managed through authenticated backend APIs/)
  assert.doesNotMatch(page, /role-permissions-panel|admin-preview-badge/)
})

test('user deletion requires explicit confirmation and reports persisted cleanup status', async () => {
  const page = await readFile(new URL('../src/pages/UsersPage.tsx', import.meta.url), 'utf8')
  const dialog = await readFile(new URL('../src/features/users/UserManagementDialog.tsx', import.meta.url), 'utf8')
  assert.match(page, /deletion-cleanups/)
  assert.match(page, /retryDeletionCleanup/)
  assert.match(page, /setSelectedUserId\(null\)[\s\S]*?setKeepSelectionEmpty\(true\)[\s\S]*?await reloadUsers\(\)/)
  assert.match(page, /cleanup_status === 'complete'/)
  assert.match(page, /Some managed files still need cleanup/)
  assert.match(dialog, /Delete User and All Associated Data\?/)
  assert.match(dialog, /This action is permanent and cannot be undone\./)
  assert.match(dialog, /You are about to permanently delete:/)
  assert.match(dialog, /The following data owned by this user will also be deleted:/)
  for (const item of ['Patients', 'Cases', 'Uploaded Images', 'Analysis Runs &amp; Results', 'Preprocessing Records', 'Notifications']) {
    assert.match(dialog, new RegExp(item.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
  assert.match(dialog, /Regular User/)
  assert.match(dialog, /checked=\{deleteConfirmed\}/)
  assert.match(dialog, /const canDelete = user\?\.role === 'user' && deleteConfirmed && !isSaving/)
  assert.match(dialog, /disabled=\{!canDelete\}/)
  assert.match(dialog, /if \(!user \|\| user\.role !== 'user'\)/)
  assert.match(dialog, /type="button" onClick=\{onClose\}/)
})

test('cleanup status reports route mismatch clearly and preserves genuine API errors', () => {
  assert.match(getCleanupStatusErrorMessage({ status: 404, message: 'Not Found' }), /running backend does not provide the deletion-cleanup status route/)
  assert.equal(getCleanupStatusErrorMessage(new Error('Service unavailable')), 'Pending file cleanup status could not be loaded: Service unavailable')
})

test('forced password flow requires current password and logs out after successful change', async () => {
  const route = await readFile(new URL('../src/auth/ProtectedRoute.tsx', import.meta.url), 'utf8')
  const page = await readFile(new URL('../src/auth/ForcedPasswordChange.tsx', import.meta.url), 'utf8')
  assert.match(route, /user\.must_change_password.*ForcedPasswordChange/)
  assert.match(page, /apiRequest<AuthUser>\('\/auth\/change-password'/)
  assert.match(page, /current_password:\s*currentPassword/)
  assert.match(page, /logout\(\)[\s\S]*?navigate\('\/login\?passwordChanged=1'/)
})
