export type CaseRecord = {
  id: string
  owner_id: string
  patient_id: string
  case_ref: string
  modality: string | null
  created_at: string
}

export type PatientRecord = {
  id: string
  owner_id: string
  patient_ref: string
  created_at: string
}

export type CasePayload = {
  patient_id: string
  case_ref: string
  modality: string | null
}

export type CaseUpdatePayload = Omit<CasePayload, 'patient_id'>
