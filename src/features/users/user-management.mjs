export function filterAndSortUsers(users, { query = '', role = 'all', status = 'all', sort = 'newest' } = {}) {
  const normalizedQuery = query.trim().toLocaleLowerCase()
  const filtered = users.filter((user) => {
    const matchesQuery = !normalizedQuery || `${user.full_name ?? ''} ${user.email}`.toLocaleLowerCase().includes(normalizedQuery)
    const matchesRole = role === 'all' || user.role === role
    const matchesStatus = status === 'all' || (status === 'active' ? user.is_active : !user.is_active)
    return matchesQuery && matchesRole && matchesStatus
  })

  return filtered.sort((left, right) => {
    if (sort === 'oldest') return new Date(left.created_at) - new Date(right.created_at)
    if (sort === 'name-asc') return (left.full_name ?? '').localeCompare(right.full_name ?? '') || left.email.localeCompare(right.email)
    if (sort === 'name-desc') return (right.full_name ?? '').localeCompare(left.full_name ?? '') || left.email.localeCompare(right.email)
    return new Date(right.created_at) - new Date(left.created_at)
  })
}

export function getUserPage(users, requestedPage, pageSize = 10) {
  const pageCount = Math.max(1, Math.ceil(users.length / pageSize))
  const page = Math.min(Math.max(1, requestedPage), pageCount)
  const start = users.length ? (page - 1) * pageSize : 0
  return {
    items: users.slice(start, start + pageSize),
    page,
    pageCount,
    start: users.length ? start + 1 : 0,
    end: Math.min(start + pageSize, users.length),
    total: users.length,
  }
}

export function getUserActionAvailability(selectedUser, currentUser, users) {
  if (!selectedUser) return { canChangeRole: false, canDeactivate: false, canResetPassword: false }
  const activeAdminCount = users.filter((user) => user.role === 'admin' && user.is_active).length
  const isLastActiveAdmin = selectedUser.role === 'admin' && selectedUser.is_active && activeAdminCount <= 1
  const isSelf = selectedUser.id === currentUser?.id
  return {
    canChangeRole: !(isLastActiveAdmin && selectedUser.role === 'admin'),
    canDeactivate: selectedUser.is_active && !isSelf && !isLastActiveAdmin,
    canResetPassword: !isSelf,
  }
}

export function getCleanupStatusErrorMessage(error) {
  if (error && typeof error === 'object' && error.status === 404) {
    return 'The running backend does not provide the deletion-cleanup status route. Restart it from the current project source, then retry.'
  }
  const detail = error instanceof Error ? error.message : 'Unknown API error'
  return `Pending file cleanup status could not be loaded: ${detail}`
}
