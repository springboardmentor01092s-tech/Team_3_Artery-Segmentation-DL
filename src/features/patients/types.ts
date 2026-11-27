import type { CaseRecord } from '../cases/types'

export type PatientRecord = {
  id: string
  owner_id: string
  owner_name: string | null
  patient_ref: string
  created_at: string
}

export type PatientPayload = { patient_ref: string }
export type PatientCaseRecord = CaseRecord
