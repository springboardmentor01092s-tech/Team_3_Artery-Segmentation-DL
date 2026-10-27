import { useEffect, useState, type FormEvent } from 'react'
import { X } from 'lucide-react'
import type { PatientPayload, PatientRecord } from './types'

type Props = {
  mode: 'create' | 'edit'
  patient?: PatientRecord
  onClose: () => void
  onSubmit: (payload: PatientPayload) => Promise<void>
}

export default function PatientFormDialog({ mode, patient, onClose, onSubmit }: Props) {
  const [patientRef, setPatientRef] = useState(patient?.patient_ref ?? '')
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
    const patient_ref = patientRef.trim()
    if (!patient_ref) {
      setError('Enter a patient reference.')
      return
    }
    if (patient_ref.length > 100) {
      setError('Patient reference must be at most 100 characters.')
      return
    }
    setIsSaving(true)
    try {
      await onSubmit({ patient_ref })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to save this patient record.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="case-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !isSaving) onClose() }}>
      <section className="case-dialog" role="dialog" aria-modal="true" aria-labelledby="patient-dialog-title">
        <div className="case-dialog__heading">
          <div><span className="eyebrow page-eyebrow">PATIENT MANAGEMENT</span><h2 id="patient-dialog-title">{mode === 'create' ? 'Add new patient' : 'Edit patient reference'}</h2></div>
          <button className="icon-button" type="button" onClick={onClose} disabled={isSaving} aria-label="Close dialog"><X size={18} /></button>
        </div>
        <form className="case-form" onSubmit={handleSubmit}>
          <label>Patient reference <input value={patientRef} onChange={(event) => setPatientRef(event.target.value)} maxLength={100} required autoFocus placeholder="Enter patient reference" /></label>
          <p className="patient-form-note">Use the existing patient reference field. No demographic or clinical details are collected here.</p>
          {error && <p className="form-message" role="alert">{error}</p>}
          <div className="case-form__actions">
            <button className="button button--secondary button--small" type="button" onClick={onClose} disabled={isSaving}>Cancel</button>
            <button className="button button--primary button--small" type="submit" disabled={isSaving}>{isSaving ? 'Saving…' : mode === 'create' ? 'Create patient' : 'Save changes'}</button>
          </div>
        </form>
      </section>
    </div>
  )
}
