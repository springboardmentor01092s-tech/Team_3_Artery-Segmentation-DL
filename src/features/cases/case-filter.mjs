export function filterCases(cases, patientsById, query, modalityFilter) {
  const normalizedQuery = query.trim().toLocaleLowerCase()
  return cases.filter((record) => {
    const patientReference = patientsById.get(record.patient_id)?.patient_ref ?? ''
    const matchesSearch = !normalizedQuery || `${record.case_ref} ${patientReference}`.toLocaleLowerCase().includes(normalizedQuery)
    const matchesModality = modalityFilter === 'all' || record.modality === modalityFilter
    return matchesSearch && matchesModality
  })
}
