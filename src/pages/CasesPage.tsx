import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, ClipboardList, Eye, Image, Pencil, Plus, Search, UsersRound } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import Panel from '../components/Panel'
import { apiRequest, apiRequestBlob } from '../auth/api'
import CaseFormDialog from '../features/cases/CaseFormDialog'
import { useCases } from '../features/cases/useCases'
import type { CasePayload, CaseUpdatePayload } from '../features/cases/types'
import { caseAnalysisStatus } from '../features/dashboard/dashboard-data.mjs'
import { caseImageContentPath, getCasePreviewImages } from '../features/cases/case-preview.mjs'
import { filterCases } from '../features/cases/case-filter.mjs'

const PAGE_SIZE = 10
type CaseImageSummary = { id: string; case_id: string; original_filename: string; created_at: string }
type CaseAnalysisRun = { id: string; case_id: string; image_id: string | null; status: string; created_at: string; started_at?: string | null; completed_at?: string | null }
type CaseDataStatus = { images: 'loading' | 'ready' | 'error'; runs: 'loading' | 'ready' | 'error' }
type PreviewImage = { id: string; filename: string; url: string | null; failed: boolean }

function caseStatusLabel(status: ReturnType<typeof caseAnalysisStatus>) {
  if (status === 'completed') return 'Available'
  if (status === 'in_progress') return 'In Progress'
  if (status === 'failed') return 'Failed'
  return 'Unavailable'
}

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
  const [imagesByCase, setImagesByCase] = useState<Record<string, CaseImageSummary[]>>({})
  const [runsByCase, setRunsByCase] = useState<Record<string, CaseAnalysisRun[]>>({})
  const [caseDataStatus, setCaseDataStatus] = useState<Record<string, CaseDataStatus>>({})
  const [previewState, setPreviewState] = useState<{ caseId: string; status: 'idle' | 'loading' | 'ready' | 'error'; images: PreviewImage[] }>({ caseId: '', status: 'idle', images: [] })
  const [caseDataReloadKey, setCaseDataReloadKey] = useState(0)
  const patientById = useMemo(() => new Map(patients.map((patient) => [patient.id, patient])), [patients])
  const modalities = useMemo(() => [...new Set(cases.map((item) => item.modality).filter((value): value is string => Boolean(value)))].sort(), [cases])
  const filteredCases = useMemo(() => filterCases(cases, patientById, query, modalityFilter), [cases, modalityFilter, patientById, query])
  const pageCount = Math.max(1, Math.ceil(filteredCases.length / PAGE_SIZE))
  const visibleCases = filteredCases.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const visibleCaseIds = [...new Set([...visibleCases.map((item) => item.id), ...(selectedCase ? [selectedCase.id] : [])])].join(',')

  useEffect(() => {
    const ids = visibleCaseIds ? visibleCaseIds.split(',') : []
    if (!ids.length) return
    let active = true
    setCaseDataStatus((current) => ({ ...current, ...Object.fromEntries(ids.map((id) => [id, { images: 'loading' as const, runs: 'loading' as const }])) }))

    Promise.all(ids.map(async (id) => {
      const encodedId = encodeURIComponent(id)
      const [imagesResult, runsResult] = await Promise.allSettled([
        apiRequest<CaseImageSummary[]>(`/cases/${encodedId}/images`),
        apiRequest<CaseAnalysisRun[]>(`/cases/${encodedId}/analysis-runs`),
      ])
      return { id, imagesResult, runsResult }
    })).then((results) => {
      if (!active) return
      setImagesByCase((current) => {
        const next = { ...current }
        for (const result of results) if (result.imagesResult.status === 'fulfilled') next[result.id] = result.imagesResult.value
        return next
      })
      setRunsByCase((current) => {
        const next = { ...current }
        for (const result of results) if (result.runsResult.status === 'fulfilled') next[result.id] = result.runsResult.value
        return next
      })
      setCaseDataStatus((current) => {
        const next = { ...current }
        for (const result of results) next[result.id] = {
          images: result.imagesResult.status === 'fulfilled' ? 'ready' : 'error',
          runs: result.runsResult.status === 'fulfilled' ? 'ready' : 'error',
        }
        return next
      })
    })

    return () => { active = false }
  }, [visibleCaseIds, caseDataReloadKey])

  useEffect(() => {
    const caseId = selectedCase?.id
    if (!caseId) {
      setPreviewState({ caseId: '', status: 'idle', images: [] })
      return
    }
    const caseStatus = caseDataStatus[caseId]
    if (!caseStatus || caseStatus.images === 'loading') {
      setPreviewState({ caseId, status: 'loading', images: [] })
      return
    }
    if (caseStatus.images === 'error') {
      setPreviewState({ caseId, status: 'error', images: [] })
      return
    }
    const records = getCasePreviewImages(imagesByCase[caseId] ?? [])
    if (!records.length) {
      setPreviewState({ caseId, status: 'ready', images: [] })
      return
    }
    let active = true
    const objectUrls: string[] = []
    setPreviewState({ caseId, status: 'loading', images: [] })
    Promise.all(records.map(async (image): Promise<PreviewImage> => {
      try {
        const blob = await apiRequestBlob(caseImageContentPath(image.id))
        const url = URL.createObjectURL(blob)
        if (!active) {
          URL.revokeObjectURL(url)
          return { id: image.id, filename: image.original_filename, url: null, failed: true }
        }
        objectUrls.push(url)
        return { id: image.id, filename: image.original_filename, url, failed: false }
      } catch {
        return { id: image.id, filename: image.original_filename, url: null, failed: true }
      }
    })).then((previewImages) => {
      if (active) setPreviewState({ caseId, status: 'ready', images: previewImages })
    })
    return () => {
      active = false
      objectUrls.forEach((url) => URL.revokeObjectURL(url))
    }
  }, [selectedCase?.id, caseDataStatus, imagesByCase])

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

  function retryCaseData() {
    setCaseDataReloadKey((current) => current + 1)
  }

  function caseRunPresentation(caseId: string) {
    const state = caseDataStatus[caseId]?.runs
    if (state === 'loading' || !state) return { label: '…', title: 'Loading persisted analysis runs.', status: 'muted' }
    if (state === 'error') return { label: '—', title: 'Unable to load analysis runs for this case.', status: 'muted' }
    const result = caseStatusLabel(caseAnalysisStatus(runsByCase[caseId] ?? []))
    return {
      label: result,
      title: result === 'Available' ? 'At least one image has a completed persisted analysis run.' : undefined,
      status: result === 'Available' ? 'available' : result === 'In Progress' ? 'progress' : result === 'Failed' ? 'failed' : 'muted',
    }
  }

  return (
    <div className="feature-page cases-page">
      <div className="patients-toolbar cases-toolbar">
        <div className="module-tabs" role="tablist" aria-label="Patient and case modules">
          <Link className="module-tab" role="tab" aria-selected="false" to="/patients"><UsersRound size={15} /> Patients</Link>
          <Link className="module-tab module-tab--active" role="tab" aria-selected="true" to="/cases"><ClipboardList size={15} /> Cases</Link>
        </div>
        <button className="button button--primary button--small" type="button" disabled={!hasLoadedData} title={!hasLoadedData ? 'Load case and patient records before creating a case.' : undefined} onClick={() => { setFeedback(''); setDialog('create') }}><Plus size={16} /> Create new case</button>
      </div>

      {feedback && <div className="case-feedback" role="status">{feedback}<button type="button" aria-label="Dismiss message" onClick={() => setFeedback('')}>×</button></div>}
      {error && <div className="case-error" role="alert"><span>{error}</span><button className="button button--secondary button--small" type="button" onClick={() => void reload()}>Retry</button></div>}
      {hasLoadedData && patients.length === 0 && <div className="case-dependency-banner" role="status"><strong>Patient required:</strong> Cases must be linked to an existing patient. No patient records are available for this account. Patient creation is outside this update. <Link to="/patients">Open Patient Management</Link></div>}

      <Panel title={`Cases (${cases.length})`} className="case-table-panel" action={<label className="case-table-search"><Search size={14} aria-hidden="true" /><input type="search" placeholder="Search cases or patient references…" aria-label="Search cases" value={query} onChange={(event) => changeFilters(event.target.value, modalityFilter)} /></label>}>
          <div className="list-toolbar case-modality-filter-toolbar">
            <select aria-label="Filter cases by modality" value={modalityFilter} onChange={(event) => changeFilters(query, event.target.value)}>
              <option value="all">All modalities</option>
              {modalities.map((modality) => <option key={modality} value={modality}>{modality}</option>)}
            </select>
          </div>
          <div className={`data-table-wrap case-table-wrap${isLoading || filteredCases.length === 0 ? ' case-table-wrap--message' : ''}`}>
            <table className="data-table case-table">
              <colgroup><col className="case-col-id" /><col className="case-col-patient" /><col className="case-col-owner" /><col className="case-col-images" /><col className="case-col-status" /><col className="case-col-created" /><col className="case-col-actions" /></colgroup>
              <thead><tr>{['Case ID', 'Patient reference', 'Created By', 'Images', 'Analysis status', 'Created on', 'Actions'].map((name, index) => <th key={name} className={`case-table__cell-${index + 1}`} scope="col">{name}</th>)}</tr></thead>
              <tbody>
                {isLoading ? <tr><td colSpan={7}><div className="case-table-message" role="status">Loading cases…</div></td></tr> : filteredCases.length === 0 ? (
                  <tr><td colSpan={7}><EmptyState icon={ClipboardList} title={cases.length ? 'No matching cases' : 'No cases found'} description={cases.length ? 'Adjust the search or modality filter.' : 'Create a case after a patient record is available.'} /></td></tr>
                ) : visibleCases.map((record) => (
                  <tr key={record.id} className={selectedCase?.id === record.id ? 'case-row case-row--selected' : 'case-row'}>
                    <td className="case-table__cell-1"><button className="case-ref-button" type="button" onClick={() => void openCase(record.id)}>{record.case_ref}</button></td>
                    <td className="case-table__cell-2">{patientById.get(record.patient_id)?.patient_ref ?? 'Patient reference unavailable'}</td>
                    <td className="case-table__cell-3">{record.owner_name?.trim() || 'Not available'}</td>
                    <td className="case-table__cell-4" title={caseDataStatus[record.id]?.images === 'error' ? 'Unable to load this case’s image count.' : undefined}>{caseDataStatus[record.id]?.images === 'error' ? '—' : caseDataStatus[record.id]?.images === 'loading' ? '…' : caseDataStatus[record.id]?.images === 'ready' ? (imagesByCase[record.id]?.length ?? 0) : '…'}</td>
                    <td className="case-table__cell-5">{(() => { const status = caseRunPresentation(record.id); return <span className={`state-pill state-pill--${status.status}`} title={status.title}>{status.label}</span> })()}</td>
                    <td className="case-table__cell-6">{formatDate(record.created_at)}</td>
                    <td className="case-table__cell-7"><div className="case-row-actions">
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

      <div className="patients-bottom-grid cases-bottom-grid">
          <Panel title="Case details" className="case-details-panel" action={selectedCase && <button className="button button--secondary button--small" type="button" onClick={() => { setFeedback(''); setDialog('edit') }}><Pencil size={14} /> Edit case</button>}>
            {selectedCase ? <div className="case-detail-list">
              <div><span>Case reference</span><strong>{selectedCase.case_ref}</strong></div>
              <div><span>Patient reference</span><strong>{patientById.get(selectedCase.patient_id)?.patient_ref ?? 'Patient reference unavailable'}</strong></div>
              <div><span>Imaging modality</span><strong>{selectedCase.modality || 'Not specified'}</strong></div>
              <div><span>Created on</span><strong>{formatDate(selectedCase.created_at)}</strong></div>
              <div><span>Analysis status</span><strong>{(() => { const status = caseRunPresentation(selectedCase.id); return <span className={`state-pill state-pill--${status.status}`} title={status.title}>{status.label}</span> })()}</strong></div>
            </div> : <EmptyState icon={ClipboardList} title={isLoading ? 'Loading cases' : 'Select a case'} description="Open a case from the list to review its saved metadata and associated patient." />}
          </Panel>
          <Panel title="Images" className="case-images-panel" action={<Link className="link-button" to="/upload">Go to upload <ArrowRight size={14} /></Link>}>
            {!selectedCase ? <EmptyState icon={Image} title="No case selected" description="Select a case to view its uploaded image previews." />
              : previewState.caseId !== selectedCase.id || previewState.status === 'loading' ? <div className="case-images-unavailable" role="status"><Image size={18} /><span>Loading case image previews…</span></div>
                : previewState.status === 'error' ? <div className="case-images-unavailable" role="alert"><Image size={18} /><strong>Unable to load images</strong><button className="button button--secondary button--small" type="button" onClick={retryCaseData}>Retry</button></div>
                  : previewState.images.length === 0 ? <div className="case-images-empty"><Image size={18} /><strong>No images uploaded</strong><span>Images associated with this case will appear here.</span></div>
                    : <div className="case-image-preview-wrap"><div className="case-image-preview-grid" aria-label="Uploaded image previews">{previewState.images.map((preview) => <div className="case-image-preview" key={preview.id} title={preview.filename}>
                      {preview.url ? <img src={preview.url} alt={`${preview.filename} preview`} /> : <span className="case-image-preview__error" role="img" aria-label={`Preview unavailable for ${preview.filename}`}>Preview unavailable</span>}
                    </div>)}</div>{imagesByCase[selectedCase.id]?.length > 6 && <small className="case-image-preview-more">+{imagesByCase[selectedCase.id].length - 6} more</small>}{previewState.images.some((preview) => preview.failed) && <span className="sr-only" role="status">Some image previews could not be loaded.</span>}</div>}
          </Panel>
      </div>

      {dialog && <CaseFormDialog mode={dialog} patients={patients} record={dialog === 'edit' ? selectedCase ?? undefined : undefined} onClose={() => setDialog(null)} onSubmit={submitCase} />}
    </div>
  )
}
