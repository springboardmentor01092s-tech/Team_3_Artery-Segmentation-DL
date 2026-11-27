import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { buildDashboardData, caseAnalysisStatus, loadDashboardData } from '../src/features/dashboard/dashboard-data.mjs'

const cases = [
  { id: 'c1', case_ref: 'CASE-1', patient_id: 'p1', created_at: '2026-11-01T10:00:00Z' },
  { id: 'c2', case_ref: 'CASE-2', patient_id: 'p1', created_at: '2026-11-02T10:00:00Z' },
  { id: 'c3', case_ref: 'CASE-3', patient_id: 'p2', created_at: '2026-11-03T10:00:00Z' },
  { id: 'c4', case_ref: 'CASE-4', patient_id: 'p2', created_at: '2026-11-04T10:00:00Z' },
]

test('dashboard totals and case status chart aggregate real case image and run records', () => {
  const data = buildDashboardData({
    cases,
    patients: [{ id: 'p1', patient_ref: 'SUBJECT-1' }, { id: 'p2', patient_ref: 'SUBJECT-2' }],
    imagesByCase: {
      c1: [{ id: 'i1', case_id: 'c1', original_filename: 'a.png', created_at: '2026-11-05T10:00:00Z' }, { id: 'i2', case_id: 'c1', original_filename: 'b.png', created_at: '2026-11-05T11:00:00Z' }],
      c2: [{ id: 'i3', case_id: 'c2', original_filename: 'c.png', created_at: '2026-11-05T12:00:00Z' }],
      c3: [], c4: [],
    },
    runsByCase: {
      c1: [{ id: 'r1', image_id: 'i1', status: 'completed', created_at: '2026-11-06T10:00:00Z', completed_at: '2026-11-06T10:01:00Z' }, { id: 'r2', image_id: 'i2', status: 'failed', created_at: '2026-11-06T11:00:00Z' }],
      c2: [{ id: 'r3', image_id: 'i3', status: 'processing', created_at: '2026-11-07T10:00:00Z' }],
      c3: [{ id: 'r4', image_id: null, status: 'failed', created_at: '2026-11-08T10:00:00Z' }],
      c4: [],
    },
  })
  assert.deepEqual(data.summary, { cases: 4, images: 3, analysesCompleted: 1, analysesInProgress: 1 })
  assert.deepEqual(data.statusCounts, { completed: 1, in_progress: 1, failed: 1, pending: 1 })
  assert.equal(data.recentCases[0].case_ref, 'CASE-4')
  assert.equal(data.recentCases[0].patient_ref, 'SUBJECT-2')
  assert.equal(data.recentAnalyses[0].id, 'r4')
  assert.ok(data.recentActivity.some((event) => event.id === 'image-i2'))
})

test('case status follows Completed > In Progress > Failed > Pending precedence', () => {
  assert.equal(caseAnalysisStatus([]), 'pending')
  assert.equal(caseAnalysisStatus([{ status: 'failed' }]), 'failed')
  assert.equal(caseAnalysisStatus([{ status: 'failed' }, { status: 'queued' }]), 'in_progress')
  assert.equal(caseAnalysisStatus([{ status: 'failed' }, { status: 'processing' }, { status: 'completed' }]), 'completed')
})

test('dashboard requests case-scoped authenticated API records and propagates API errors', async () => {
  const calls = []
  const request = async (path) => {
    calls.push(path)
    if (path === '/cases') return [{ id: 'case/1', case_ref: 'CASE-1', patient_id: 'p1', created_at: '2026-11-01' }]
    if (path === '/patients') return [{ id: 'p1', patient_ref: 'SUBJECT-1' }]
    if (path.includes('/images')) return []
    if (path.includes('/analysis-runs')) return []
    throw new Error('unexpected path')
  }
  const data = await loadDashboardData(request)
  assert.deepEqual(calls.sort(), ['/cases', '/patients', '/cases/case%2F1/analysis-runs', '/cases/case%2F1/images'].sort())
  assert.equal(data.summary.cases, 1)
  await assert.rejects(loadDashboardData(async (path) => {
    if (path === '/patients') return []
    if (path === '/cases') return [{ id: 'case-2', case_ref: 'CASE-2', patient_id: 'p', created_at: '2026-11-01' }]
    throw new Error('API unavailable')
  }), /API unavailable/)
})

test('Dashboard has explicit loading/error handling and View Reports uses the existing route', async () => {
  const source = await readFile(new URL('../src/pages/DashboardPage.tsx', import.meta.url), 'utf8')
  assert.match(source, /Loading authenticated workspace records/)
  assert.match(source, /Dashboard data is unavailable/)
  assert.match(source, /onClick=\{\(\) => void load\(\)\}/)
  assert.match(source, /to="\/reports"/)
})
