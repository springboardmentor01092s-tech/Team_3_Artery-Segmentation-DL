import { useCallback, useEffect, useState } from 'react'
import { apiRequest } from '../../auth/api'
import type { PatientCaseRecord, PatientPayload, PatientRecord } from './types'

export function usePatients() {
  const [patients, setPatients] = useState<PatientRecord[]>([])
  const [cases, setCases] = useState<PatientCaseRecord[]>([])
  const [selectedPatient, setSelectedPatient] = useState<PatientRecord | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [hasLoadedData, setHasLoadedData] = useState(false)
  const [error, setError] = useState('')

  const reload = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const [patientRows, caseRows] = await Promise.all([
        apiRequest<PatientRecord[]>('/patients'),
        apiRequest<PatientCaseRecord[]>('/cases'),
      ])
      setPatients(patientRows)
      setCases(caseRows)
      setHasLoadedData(true)
      setSelectedPatient((current) => current ? patientRows.find((row) => row.id === current.id) ?? null : null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load patient records. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => { void reload() }, [reload])

  const openPatient = useCallback(async (patientId: string) => {
    setError('')
    setSelectedPatient(null)
    try {
      const patient = await apiRequest<PatientRecord>(`/patients/${patientId}`)
      setSelectedPatient(patient)
      return patient
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to open this patient record.')
      return null
    }
  }, [])

  const createPatient = useCallback(async (payload: PatientPayload) => {
    const patient = await apiRequest<PatientRecord>('/patients', { method: 'POST', body: JSON.stringify(payload) })
    await reload()
    setSelectedPatient(patient)
    return patient
  }, [reload])

  const updatePatient = useCallback(async (patientId: string, payload: PatientPayload) => {
    const patient = await apiRequest<PatientRecord>(`/patients/${patientId}`, { method: 'PATCH', body: JSON.stringify(payload) })
    setPatients((current) => current.map((item) => item.id === patient.id ? patient : item))
    setSelectedPatient(patient)
    return patient
  }, [])

  return { patients, cases, selectedPatient, isLoading, hasLoadedData, error, setError, reload, openPatient, createPatient, updatePatient }
}
