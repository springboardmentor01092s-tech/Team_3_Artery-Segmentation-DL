import type { CaseRecord, PatientRecord } from './types'

export declare function filterCases(
  cases: CaseRecord[],
  patientsById: ReadonlyMap<string, PatientRecord>,
  query: string,
  modalityFilter: string,
): CaseRecord[]
