import { useEffect, useState, type FormEvent } from 'react'
import { X } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { CasePayload, CaseRecord, CaseUpdatePayload, PatientRecord } from './types'

type Props = {
  mode: 'create' | 'edit'
  patients: PatientRecord[]
  record?: CaseRecord
  onClose: () => void
  onSubmit: (payload: CasePayload | CaseUpdatePayload) => Promise<void>
}

export default function CaseFormDialog({ mode, patients, record, onClose, onSubmit }: Props) {
  const [caseRef, setCaseRef] = useState(record?.case_ref ?? '')
  const [patientId, setPatientId] = useState(record?.patient_id ?? patients[0]?.id ?? '')
  const [modality, setModality] = useState(record?.modality ?? '')
  const [error, setError] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && !isSaving) onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isSaving, onClose])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    const cleanCaseRef = caseRef.trim()
    const cleanModality = modality.trim()
    if (!cleanCaseRef) {
      setError('Enter a case reference.')
      return
    }
    if (cleanCaseRef.length > 100 || cleanModality.length > 50) {
      setError('Case reference must be at most 100 characters and modality at most 50 characters.')
      return
    }
    if (mode === 'create' && !patientId) {
      setError('Select an existing patient before creating a case.')
      return
    }

    setIsSaving(true)
    try {
      if (mode === 'create') {
        await onSubmit({ patient_id: patientId, case_ref: cleanCaseRef, modality: cleanModality || null })
      } else {
        await onSubmit({ case_ref: cleanCaseRef, modality: cleanModality || null })
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to save this case.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="case-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !isSaving) onClose() }}>
      <section className="case-dialog" role="dialog" aria-modal="true" aria-labelledby="case-dialog-title">
        <div className="case-dialog__heading">
          <div><span className="eyebrow page-eyebrow">CASE MANAGEMENT</span><h2 id="case-dialog-title">{mode === 'create' ? 'Create new case' : 'Edit case'}</h2></div>
          <button className="icon-button" type="button" onClick={onClose} disabled={isSaving} aria-label="Close dialog"><X size={18} /></button>
        </div>
        {mode === 'create' && patients.length === 0 ? (
          <div className="case-dependency-message" role="status">
            <strong>An existing patient is required.</strong>
            <p>No patient records are available for your account, so a case cannot be created yet. Patient creation is not part of this case-management update.</p>
            <Link className="button button--secondary button--small" to="/patients">Open Patient Management</Link>
          </div>
        ) : (
          <form className="case-form" onSubmit={handleSubmit}>
            {mode === 'create' && <label>Patient <select value={patientId} onChange={(event) => setPatientId(event.target.value)} required>
              <option value="" disabled>Select a patient</option>
              {patients.map((patient) => <option key={patient.id} value={patient.id}>{patient.patient_ref}</option>)}
            </select></label>}
            {mode === 'edit' && <div className="case-form__patient"><span>Patient</span><strong>{patients.find((patient) => patient.id === record?.patient_id)?.patient_ref ?? 'Patient reference unavailable'}</strong><small>Patient association is fixed for this case.</small></div>}
            <label>Case reference <input value={caseRef} onChange={(event) => setCaseRef(event.target.value)} maxLength={100} required autoFocus placeholder="Enter case reference" /></label>
            <label>Imaging modality <input value={modality} onChange={(event) => setModality(event.target.value)} maxLength={50} placeholder="Optional" /></label>
            {error && <p className="form-message" role="alert">{error}</p>}
            <div className="case-form__actions">
              <button className="button button--secondary button--small" type="button" onClick={onClose} disabled={isSaving}>Cancel</button>
              <button className="button button--primary button--small" type="submit" disabled={isSaving}>{isSaving ? 'Saving…' : mode === 'create' ? 'Create case' : 'Save changes'}</button>
            </div>
          </form>
        )}
      </section>
    </div>
  )
}
