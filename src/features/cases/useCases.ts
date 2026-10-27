import { useCallback, useEffect, useState } from 'react'
import { apiRequest } from '../../auth/api'
import type { CasePayload, CaseRecord, CaseUpdatePayload, PatientRecord } from './types'

export function useCases() {
  const [cases, setCases] = useState<CaseRecord[]>([])
  const [patients, setPatients] = useState<PatientRecord[]>([])
  const [selectedCase, setSelectedCase] = useState<CaseRecord | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [hasLoadedData, setHasLoadedData] = useState(false)
  const [error, setError] = useState('')

  const reload = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const [caseRows, patientRows] = await Promise.all([
        apiRequest<CaseRecord[]>('/cases'),
        apiRequest<PatientRecord[]>('/patients'),
      ])
      setCases(caseRows)
      setPatients(patientRows)
      setHasLoadedData(true)
      setSelectedCase((current) => current ? caseRows.find((row) => row.id === current.id) ?? null : null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load cases. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => { void reload() }, [reload])

  const openCase = useCallback(async (caseId: string) => {
    setError('')
    setSelectedCase(null)
    try {
      const record = await apiRequest<CaseRecord>(`/cases/${caseId}`)
      setSelectedCase(record)
      return record
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to open this case.')
      return null
    }
  }, [])

  const createCase = useCallback(async (payload: CasePayload) => {
    const record = await apiRequest<CaseRecord>('/cases', { method: 'POST', body: JSON.stringify(payload) })
    await reload()
    setSelectedCase(record)
    return record
  }, [reload])

  const updateCase = useCallback(async (caseId: string, payload: CaseUpdatePayload) => {
    const record = await apiRequest<CaseRecord>(`/cases/${caseId}`, { method: 'PATCH', body: JSON.stringify(payload) })
    setCases((current) => current.map((item) => item.id === record.id ? record : item))
    setSelectedCase(record)
    return record
  }, [])

  return { cases, patients, selectedCase, setSelectedCase, isLoading, hasLoadedData, error, setError, reload, openCase, createCase, updateCase }
}
