export function readReportSelection(storage, key) {
  try {
    const saved = JSON.parse(storage.getItem(key) ?? 'null')
    if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return { patientId: '', caseId: '', imageId: '', runId: '' }
    return Object.fromEntries(['patientId', 'caseId', 'imageId', 'runId'].map((field) => [field, typeof saved[field] === 'string' ? saved[field] : '']))
  } catch {
    return { patientId: '', caseId: '', imageId: '', runId: '' }
  }
}

export function validateReportBaseSelection(selection, patients, cases) {
  const patient = patients.find((record) => record.id === selection.patientId)
  if (!patient) return { patientId: '', caseId: '', imageId: '', runId: '' }
  const caseRecord = cases.find((record) => record.id === selection.caseId && record.patient_id === patient.id)
  if (!caseRecord) return { patientId: patient.id, caseId: '', imageId: '', runId: '' }
  return { patientId: patient.id, caseId: caseRecord.id, imageId: selection.imageId, runId: selection.runId }
}

export function validateReportCaseSelection(selection, images, runs) {
  const image = images.find((record) => record.id === selection.imageId && record.case_id === selection.caseId)
  const run = runs.find((record) => record.id === selection.runId && record.case_id === selection.caseId)
  const selectedImage = image ?? (run?.image_id ? images.find((record) => record.id === run.image_id && record.case_id === selection.caseId) : null)
  const selectedRun = run && selectedImage && run.image_id === selectedImage.id ? run : null
  return {
    patientId: selection.patientId,
    caseId: selection.caseId,
    imageId: selectedImage?.id ?? '',
    runId: selectedRun?.id ?? '',
  }
}

export function saveReportSelection(storage, key, selection) {
  const safe = Object.fromEntries(['patientId', 'caseId', 'imageId', 'runId'].map((field) => [field, selection[field] || '']))
  try {
    if (Object.values(safe).every((value) => !value)) storage.removeItem(key)
    else storage.setItem(key, JSON.stringify(safe))
  } catch {
    // Storage can be disabled or full; the current page selection remains usable.
  }
}

export function readSessionReportSelection(key) {
  try {
    return readReportSelection(globalThis.sessionStorage, key)
  } catch {
    return { patientId: '', caseId: '', imageId: '', runId: '' }
  }
}

export function saveSessionReportSelection(key, selection) {
  try {
    saveReportSelection(globalThis.sessionStorage, key, selection)
  } catch {
    // Keep the current in-memory selection when session storage is unavailable.
  }
}
