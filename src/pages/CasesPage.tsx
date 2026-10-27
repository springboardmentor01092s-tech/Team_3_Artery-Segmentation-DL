import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, ClipboardList, Eye, Image, Pencil, Plus, UsersRound } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import PageHeader from '../components/PageHeader'
import Panel from '../components/Panel'
import WorkspaceNotice from '../components/WorkspaceNotice'
import { apiRequest } from '../auth/api'
import CaseFormDialog from '../features/cases/CaseFormDialog'
import { useCases } from '../features/cases/useCases'
import type { CasePayload, CaseUpdatePayload } from '../features/cases/types'

const PAGE_SIZE = 10
type CaseImageSummary = { id: string }
type ImageCountResult = { id: string; count: number } | { id: string; error: true }

function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date)
}

function errorMessage(error: unknown) {
  if (error instanceof Error && 'status' in error && error.status === 409) return 'A case with this reference already exists for this account.'
  return error instanceof Error ? error.message : 'Unable to save this case. Please try again.'
}

export default function CasesPage() {
  const { cases, patients, selectedCase, isLoading, hasLoadedData, error, setError, reload, openCase, createCase, updateCase } = useCases()
  const [searchParams, setSearchParams] = useSearchParams()
  const [query, setQuery] = useState('')
  const [modalityFilter, setModalityFilter] = useState('all')
  const [page, setPage] = useState(1)
  const [dialog, setDialog] = useState<'create' | 'edit' | null>(null)
  const [feedback, setFeedback] = useState('')
  const [imageCounts, setImageCounts] = useState<Record<string, number>>({})
  const [imageCountStatus, setImageCountStatus] = useState<Record<string, 'loading' | 'error'>>({})
  const patientById = useMemo(() => new Map(patients.map((patient) => [patient.id, patient])), [patients])
  const modalities = useMemo(() => [...new Set(cases.map((item) => item.modality).filter((value): value is string => Boolean(value)))].sort(), [cases])
  const filteredCases = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase()
    return cases.filter((item) => {
      const patientRef = patientById.get(item.patient_id)?.patient_ref ?? ''
      const matchesQuery = !normalizedQuery || `${item.case_ref} ${patientRef} ${item.modality ?? ''}`.toLocaleLowerCase().includes(normalizedQuery)
      return matchesQuery && (modalityFilter === 'all' || item.modality === modalityFilter)
    })
  }, [cases, modalityFilter, patientById, query])
  const pageCount = Math.max(1, Math.ceil(filteredCases.length / PAGE_SIZE))
  const visibleCases = filteredCases.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const visibleCaseIds = visibleCases.map((item) => item.id).join(',')

  useEffect(() => {
    const ids = visibleCaseIds ? visibleCaseIds.split(',') : []
    if (!ids.length) return
    let active = true
    setImageCountStatus((current) => ({ ...current, ...Object.fromEntries(ids.map((id) => [id, 'loading' as const])) }))

    Promise.all(ids.map(async (id): Promise<ImageCountResult> => {
      try {
        const imageRecords = await apiRequest<CaseImageSummary[]>(`/cases/${id}/images`)
        return { id, count: imageRecords.length }
      } catch {
        return { id, error: true as const }
      }
    })).then((results) => {
      if (!active) return
      setImageCounts((current) => {
        const next = { ...current }
        for (const result of results) if ('count' in result) next[result.id] = result.count
        return next
      })
      setImageCountStatus((current) => {
        const next = { ...current }
        for (const result of results) {
          if ('error' in result) next[result.id] = 'error'
          else delete next[result.id]
        }
        return next
      })
    })

    return () => { active = false }
  }, [visibleCaseIds])

  useEffect(() => {
    if (hasLoadedData && searchParams.get('action') === 'create') {
      setDialog('create')
      setSearchParams({}, { replace: true })
    }
  }, [hasLoadedData, searchParams, setSearchParams])

  async function submitCase(payload: CasePayload | CaseUpdatePayload) {
    try {
      if (dialog === 'create') {
        await createCase(payload as CasePayload)
        setFeedback('Case created and saved.')
      } else if (dialog === 'edit' && selectedCase) {
        await updateCase(selectedCase.id, payload as CaseUpdatePayload)
        setFeedback('Case changes saved.')
      }
      setDialog(null)
      setError('')
    } catch (cause) {
      throw new Error(errorMessage(cause))
    }
  }

  function changeFilters(search: string, modality: string) {
    setQuery(search)
    setModalityFilter(modality)
    setPage(1)
  }

  return (
    <div className="feature-page">
      <WorkspaceNotice />
      <PageHeader title="Case Management" description="Organize imaging cases and review saved case details." action={<button className="button button--primary button--small" type="button" disabled={!hasLoadedData} title={!hasLoadedData ? 'Load case and patient records before creating a case.' : undefined} onClick={() => { setFeedback(''); setDialog('create') }}><Plus size={16} /> Create new case</button>} />
      <div className="module-tabs" role="tablist" aria-label="Patient and case modules">
        <Link className="module-tab" role="tab" aria-selected="false" to="/patients"><UsersRound size={15} /> Patients</Link>
        <Link className="module-tab module-tab--active" role="tab" aria-selected="true" to="/cases"><ClipboardList size={15} /> Cases</Link>
      </div>

      {feedback && <div className="case-feedback" role="status">{feedback}<button type="button" aria-label="Dismiss message" onClick={() => setFeedback('')}>×</button></div>}
      {error && <div className="case-error" role="alert"><span>{error}</span><button className="button button--secondary button--small" type="button" onClick={() => void reload()}>Retry</button></div>}
      {hasLoadedData && patients.length === 0 && <div className="case-dependency-banner" role="status"><strong>Patient required:</strong> Cases must be linked to an existing patient. No patient records are available for this account. Patient creation is outside this update. <Link to="/patients">Open Patient Management</Link></div>}

      <div className="cases-management-layout">
        <Panel title={`Cases (${cases.length})`} className="case-table-panel">
          <div className="list-toolbar">
            <input type="search" placeholder="Search case or patient reference..." aria-label="Search cases" value={query} onChange={(event) => changeFilters(event.target.value, modalityFilter)} />
            <select aria-label="Filter cases by modality" value={modalityFilter} onChange={(event) => changeFilters(query, event.target.value)}>
              <option value="all">All modalities</option>
              {modalities.map((modality) => <option key={modality} value={modality}>{modality}</option>)}
            </select>
          </div>
          <div className="data-table-wrap">
            <table className="data-table">
              <thead><tr>{['Case ID', 'Patient reference', 'Imaging modality', 'Images', 'Analysis status', 'Created on', 'Actions'].map((name) => <th key={name} scope="col">{name}</th>)}</tr></thead>
              <tbody>
                {isLoading ? <tr><td colSpan={7}><div className="case-table-message" role="status">Loading cases…</div></td></tr> : filteredCases.length === 0 ? (
                  <tr><td colSpan={7}><EmptyState icon={ClipboardList} title={cases.length ? 'No matching cases' : 'No cases found'} description={cases.length ? 'Adjust the search or modality filter.' : 'Create a case after a patient record is available.'} /></td></tr>
                ) : visibleCases.map((record) => (
                  <tr key={record.id} className={selectedCase?.id === record.id ? 'case-row case-row--selected' : 'case-row'}>
                    <td><button className="case-ref-button" type="button" onClick={() => void openCase(record.id)}>{record.case_ref}</button></td>
                    <td>{patientById.get(record.patient_id)?.patient_ref ?? 'Patient reference unavailable'}</td>
                    <td>{record.modality || '—'}</td>
                    <td title={imageCountStatus[record.id] === 'error' ? 'Unable to load this case’s image count.' : undefined}>{imageCountStatus[record.id] === 'error' ? '—' : imageCountStatus[record.id] === 'loading' ? '…' : (imageCounts[record.id] ?? '…')}</td>
                    <td><span className="state-pill state-pill--muted">Unavailable</span></td>
                    <td>{formatDate(record.created_at)}</td>
                    <td><div className="case-row-actions">
                      <button className="case-icon-button" type="button" aria-label={`Open ${record.case_ref}`} title="Open case details" onClick={() => void openCase(record.id)}><Eye size={15} /></button>
                      <button className="case-icon-button" type="button" aria-label={`Edit ${record.case_ref}`} title="Edit case" onClick={async () => { const opened = await openCase(record.id); if (opened) setDialog('edit') }}><Pencil size={14} /></button>
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="table-pagination"><span>Showing {filteredCases.length ? (page - 1) * PAGE_SIZE + 1 : 0}–{Math.min(page * PAGE_SIZE, filteredCases.length)} of {filteredCases.length} cases</span><div>
            <button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page <= 1} aria-label="Previous page">‹</button>
            <button className="pagination-current" type="button" aria-current="page">{page} / {pageCount}</button>
            <button type="button" onClick={() => setPage((current) => Math.min(pageCount, current + 1))} disabled={page >= pageCount} aria-label="Next page">›</button>
          </div></div>
        </Panel>

        <aside className="case-detail-stack">
          <Panel title="Case details" action={selectedCase && <button className="button button--secondary button--small" type="button" onClick={() => { setFeedback(''); setDialog('edit') }}><Pencil size={14} /> Edit case</button>}>
            {selectedCase ? <div className="case-detail-list">
              <div><span>Case reference</span><strong>{selectedCase.case_ref}</strong></div>
              <div><span>Patient reference</span><strong>{patientById.get(selectedCase.patient_id)?.patient_ref ?? 'Patient reference unavailable'}</strong></div>
              <div><span>Imaging modality</span><strong>{selectedCase.modality || 'Not specified'}</strong></div>
              <div><span>Created on</span><strong>{formatDate(selectedCase.created_at)}</strong></div>
              <div><span>Analysis status</span><strong><span className="state-pill state-pill--muted">Unavailable — no model configured</span></strong></div>
            </div> : <EmptyState icon={ClipboardList} title={isLoading ? 'Loading cases' : 'Select a case'} description="Open a case from the list to review its saved metadata and associated patient." />}
          </Panel>
          <Panel title="Images" action={<Link className="link-button" to="/upload">Go to upload <ArrowRight size={14} /></Link>}>
            {selectedCase ? <div className="case-images-unavailable"><Image size={20} /><strong>Image listing is not included here</strong><span>Image upload and image management remain separate from this case-management update.</span></div> : <EmptyState icon={Image} title="No case selected" description="Select a case to view its image section. Image management is not part of this update." />}
          </Panel>
        </aside>
      </div>

      {dialog && <CaseFormDialog mode={dialog} patients={patients} record={dialog === 'edit' ? selectedCase ?? undefined : undefined} onClose={() => setDialog(null)} onSubmit={submitCase} />}
    </div>
  )
}
