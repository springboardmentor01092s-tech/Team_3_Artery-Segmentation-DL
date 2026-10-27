import { useMemo, useState } from 'react'
import { ArrowRight, Download, Eye, Pencil, Plus, UsersRound } from 'lucide-react'
import { Link } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import PageHeader from '../components/PageHeader'
import Panel from '../components/Panel'
import WorkspaceNotice from '../components/WorkspaceNotice'
import PatientFormDialog from '../features/patients/PatientFormDialog'
import { usePatients } from '../features/patients/usePatients'
import type { PatientPayload } from '../features/patients/types'

const PAGE_SIZE = 10

function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date)
}

function errorMessage(error: unknown) {
  if (error instanceof Error && 'status' in error && error.status === 409) return 'A patient with this reference already exists for this account.'
  return error instanceof Error ? error.message : 'Unable to save this patient record. Please try again.'
}

export default function PatientsPage() {
  const { patients, cases, selectedPatient, isLoading, hasLoadedData, error, setError, reload, openPatient, createPatient, updatePatient } = usePatients()
  const [query, setQuery] = useState('')
  const [caseFilter, setCaseFilter] = useState('all')
  const [page, setPage] = useState(1)
  const [dialog, setDialog] = useState<'create' | 'edit' | null>(null)
  const [feedback, setFeedback] = useState('')
  const casesByPatient = useMemo(() => {
    const grouped = new Map<string, typeof cases>()
    for (const item of cases) grouped.set(item.patient_id, [...(grouped.get(item.patient_id) ?? []), item])
    return grouped
  }, [cases])
  const filteredPatients = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase()
    return patients.filter((patient) => {
      const count = casesByPatient.get(patient.id)?.length ?? 0
      const matchesText = !normalizedQuery || patient.patient_ref.toLocaleLowerCase().includes(normalizedQuery)
      const matchesCase = caseFilter === 'all' || (caseFilter === 'with-cases' ? count > 0 : count === 0)
      return matchesText && matchesCase
    })
  }, [caseFilter, casesByPatient, patients, query])
  const pageCount = Math.max(1, Math.ceil(filteredPatients.length / PAGE_SIZE))
  const visiblePatients = filteredPatients.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  async function submitPatient(payload: PatientPayload) {
    try {
      if (dialog === 'create') {
        await createPatient(payload)
        setFeedback('Patient record created and saved.')
      } else if (dialog === 'edit' && selectedPatient) {
        await updatePatient(selectedPatient.id, payload)
        setFeedback('Patient reference updated and saved.')
      }
      setDialog(null)
      setError('')
    } catch (cause) {
      throw new Error(errorMessage(cause))
    }
  }

  function changeFilters(search: string, casesFilter: string) {
    setQuery(search)
    setCaseFilter(casesFilter)
    setPage(1)
  }

  return (
    <div className="feature-page">
      <WorkspaceNotice />
      <PageHeader title="Patient Management" description="Manage patient records and their imaging cases." action={<>
        <button className="button button--secondary button--small" type="button" disabled title="Patient import is not supported by the existing backend API."><Download size={15} /> Import patient data</button>
        <button className="button button--primary button--small" type="button" disabled={!hasLoadedData} title={!hasLoadedData ? 'Load patient records before creating a patient.' : undefined} onClick={() => { setFeedback(''); setDialog('create') }}><Plus size={16} /> Add new patient</button>
      </>} />
      <div className="module-tabs" role="tablist" aria-label="Patient and case modules">
        <Link className="module-tab module-tab--active" role="tab" aria-selected="true" to="/patients"><UsersRound size={15} /> Patients</Link>
        <Link className="module-tab" role="tab" aria-selected="false" to="/cases">Cases <ArrowRight size={14} /></Link>
      </div>
      {feedback && <div className="case-feedback" role="status">{feedback}<button type="button" aria-label="Dismiss message" onClick={() => setFeedback('')}>×</button></div>}
      {error && <div className="case-error" role="alert"><span>{error}</span><button className="button button--secondary button--small" type="button" onClick={() => void reload()}>Retry</button></div>}
      <div className="management-layout">
        <Panel title={`Patients (${patients.length})`} className="management-list-panel">
          <div className="list-toolbar">
            <input type="search" placeholder="Search patient references..." aria-label="Search patients" value={query} onChange={(event) => changeFilters(event.target.value, caseFilter)} />
            <select aria-label="Filter patients by case association" value={caseFilter} onChange={(event) => changeFilters(query, event.target.value)}>
              <option value="all">All patients</option><option value="with-cases">With cases</option><option value="without-cases">Without cases</option>
            </select>
          </div>
          <div className="data-table-wrap">
            <table className="data-table patient-table">
              <thead><tr>{['Patient reference', 'No. of cases', 'Created on', 'Actions'].map((name) => <th key={name} scope="col">{name}</th>)}</tr></thead>
              <tbody>
                {isLoading ? <tr><td colSpan={4}><div className="case-table-message" role="status">Loading patients…</div></td></tr> : filteredPatients.length === 0 ? (
                  <tr><td colSpan={4}><EmptyState icon={UsersRound} title={patients.length ? 'No matching patients' : 'No patient records'} description={patients.length ? 'Adjust the search or case filter.' : 'Add a patient record to make it available for case creation.'} /></td></tr>
                ) : visiblePatients.map((patient) => <tr key={patient.id} className={selectedPatient?.id === patient.id ? 'case-row case-row--selected' : 'case-row'}>
                  <td><button className="case-ref-button" type="button" onClick={() => void openPatient(patient.id)}>{patient.patient_ref}</button></td>
                  <td>{casesByPatient.get(patient.id)?.length ?? 0}</td>
                  <td>{formatDate(patient.created_at)}</td>
                  <td><div className="case-row-actions">
                    <button className="case-icon-button" type="button" aria-label={`View ${patient.patient_ref}`} title="View patient details" onClick={() => void openPatient(patient.id)}><Eye size={15} /></button>
                    <button className="case-icon-button" type="button" aria-label={`Edit ${patient.patient_ref}`} title="Edit patient reference" onClick={async () => { const opened = await openPatient(patient.id); if (opened) setDialog('edit') }}><Pencil size={14} /></button>
                  </div></td>
                </tr>)}
              </tbody>
            </table>
          </div>
          <div className="table-pagination"><span>Showing {filteredPatients.length ? (page - 1) * PAGE_SIZE + 1 : 0}–{Math.min(page * PAGE_SIZE, filteredPatients.length)} of {filteredPatients.length} patients</span><div>
            <button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page <= 1} aria-label="Previous page">‹</button>
            <button className="pagination-current" type="button" aria-current="page">{page} / {pageCount}</button>
            <button type="button" onClick={() => setPage((current) => Math.min(pageCount, current + 1))} disabled={page >= pageCount} aria-label="Next page">›</button>
          </div></div>
        </Panel>
        <div className="management-detail-stack">
          <Panel title="Patient details" action={selectedPatient && <button className="button button--secondary button--small" type="button" onClick={() => { setFeedback(''); setDialog('edit') }}><Pencil size={14} /> Edit reference</button>}>
            {selectedPatient ? <div className="patient-detail-list">
              <div><span>Patient reference</span><strong>{selectedPatient.patient_ref}</strong></div>
              <div><span>Created on</span><strong>{formatDate(selectedPatient.created_at)}</strong></div>
              <div><span>Associated cases</span><strong>{casesByPatient.get(selectedPatient.id)?.length ?? 0}</strong></div>
            </div> : <EmptyState icon={UsersRound} title={isLoading ? 'Loading patients' : 'Select a patient'} description="Open a patient record to review its reference and associated cases." />}
          </Panel>
          <Panel title="Cases for patient" action={<Link className="link-button" to="/cases">Case Management <ArrowRight size={14} /></Link>}>
            {selectedPatient ? (casesByPatient.get(selectedPatient.id)?.length ? <div className="patient-associated-cases">
              {(casesByPatient.get(selectedPatient.id) ?? []).map((item) => <div key={item.id}><span><strong>{item.case_ref}</strong><small>{item.modality || 'Modality not specified'}</small></span><Link to="/cases" aria-label={`Open case management for ${item.case_ref}`}><ArrowRight size={15} /></Link></div>)}
            </div> : <EmptyState icon={ArrowRight} title="No cases for this patient" description="Cases linked to this patient will appear here." />) : <EmptyState icon={ArrowRight} title="No patient selected" description="Choose a patient record to review linked cases." />}
          </Panel>
        </div>
      </div>
      {dialog && <PatientFormDialog mode={dialog} patient={dialog === 'edit' ? selectedPatient ?? undefined : undefined} onClose={() => setDialog(null)} onSubmit={submitPatient} />}
    </div>
  )
}
