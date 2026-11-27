import { useEffect, useMemo, useState } from 'react'
import { FileText } from 'lucide-react'
import Panel from '../components/Panel'
import { apiRequest, apiRequestBlob } from '../auth/api'
import type { CaseRecord } from '../features/cases/types'
import type { PatientRecord } from '../features/patients/types'
import type { AnalysisResultsResponse, AnalysisRunResponse } from '../features/analysis/contracts.mjs'
import { createGradcamOverlay } from '../features/analysis/gradcam-overlay.mjs'
import { buildReportViewModel } from '../features/reports/report-data.mjs'
import { blobToJpegAsset, createReportPdf } from '../features/reports/pdf-report.mjs'
import type { ReportJpegAsset } from '../features/reports/pdf-report.mjs'
import { toApiRequestPath } from '../features/analysis/contracts.mjs'
import { useNotifications } from '../features/notifications/NotificationProvider'
import { buildReportCsv, buildReportJson, dispatchReportDownload } from '../features/reports/report-exports.mjs'
import { useAuth } from '../auth/AuthProvider'
import { readSessionReportSelection, saveSessionReportSelection, validateReportBaseSelection, validateReportCaseSelection } from '../features/reports/report-selection.mjs'

const reportFormats = ['PDF', 'JSON', 'CSV'] as const
type ReportFormat = typeof reportFormats[number]
type ReportRun = AnalysisRunResponse & { completed_at?: string | null }
type CaseImage = { id: string; case_id: string; original_filename: string; created_at?: string }

function readableError(error: unknown) {
  return error instanceof Error ? error.message : 'Unable to load report data.'
}

async function fetchProtectedArtifact(url: string) {
  const path = toApiRequestPath(url, window.location.origin)
  if (!path) throw new Error('The backend returned an invalid artifact URL.')
  return apiRequestBlob(path)
}

function safeFilePart(value: string) {
  return value.normalize('NFKD').replace(/[^a-zA-Z0-9_-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60) || 'analysis'
}

function dispatchBrowserDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.append(anchor)
  try {
    anchor.click()
  } finally {
    anchor.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
}

export default function ReportsPage() {
  const { user } = useAuth()
  const { addReportDownload } = useNotifications()
  const selectionKey = `artery-analysis:reports-selection:${user?.id ?? 'signed-in'}`
  const [initialSelection] = useState(() => readSessionReportSelection(selectionKey))
  const [selectedFormat, setSelectedFormat] = useState<ReportFormat>('PDF')
  const [patients, setPatients] = useState<PatientRecord[]>([])
  const [cases, setCases] = useState<CaseRecord[]>([])
  const [images, setImages] = useState<CaseImage[]>([])
  const [runs, setRuns] = useState<ReportRun[]>([])
  const [selectedPatientId, setSelectedPatientId] = useState(initialSelection.patientId)
  const [selectedCaseId, setSelectedCaseId] = useState(initialSelection.caseId)
  const [selectedImageId, setSelectedImageId] = useState(initialSelection.imageId)
  const [selectedRunId, setSelectedRunId] = useState(initialSelection.runId)
  const [results, setResults] = useState<AnalysisResultsResponse | null>(null)
  const [isLoadingRecords, setIsLoadingRecords] = useState(true)
  const [isLoadingRuns, setIsLoadingRuns] = useState(false)
  const [isLoadingResults, setIsLoadingResults] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [reportMessage, setReportMessage] = useState('')
  const [notes, setNotes] = useState('')

  useEffect(() => {
    let active = true
    Promise.all([apiRequest<PatientRecord[]>('/patients'), apiRequest<CaseRecord[]>('/cases')])
      .then(([patientRows, caseRows]) => {
        if (!active) return
        setPatients(patientRows)
        setCases(caseRows)
      })
      .catch((error: unknown) => { if (active) setLoadError(readableError(error)) })
      .finally(() => { if (active) setIsLoadingRecords(false) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (isLoadingRecords || loadError) return
    const validated = validateReportBaseSelection(
      { patientId: selectedPatientId, caseId: selectedCaseId, imageId: selectedImageId, runId: selectedRunId },
      patients,
      cases,
    )
    if (validated.patientId !== selectedPatientId) setSelectedPatientId(validated.patientId)
    if (validated.caseId !== selectedCaseId) setSelectedCaseId(validated.caseId)
    if (validated.imageId !== selectedImageId) setSelectedImageId(validated.imageId)
    if (validated.runId !== selectedRunId) setSelectedRunId(validated.runId)
  }, [isLoadingRecords, loadError, patients, cases, selectedPatientId, selectedCaseId, selectedImageId, selectedRunId])

  useEffect(() => {
    saveSessionReportSelection(selectionKey, {
      patientId: selectedPatientId,
      caseId: selectedCaseId,
      imageId: selectedImageId,
      runId: selectedRunId,
    })
  }, [selectionKey, selectedPatientId, selectedCaseId, selectedImageId, selectedRunId])

  useEffect(() => {
    let active = true
    setRuns([])
    setImages([])
    setResults(null)
    setReportMessage('')
    setLoadError('')
    if (!selectedCaseId) {
      setIsLoadingRuns(false)
      return () => { active = false }
    }
    setIsLoadingRuns(true)
    const casePath = encodeURIComponent(selectedCaseId)
    Promise.all([
      apiRequest<CaseImage[]>(`/cases/${casePath}/images`),
      apiRequest<ReportRun[]>(`/cases/${casePath}/analysis-runs`),
    ])
      .then(([imageRows, runRows]) => {
        if (!active) return
        setImages(imageRows)
        setRuns(runRows)
        const validated = validateReportCaseSelection(
          { patientId: selectedPatientId, caseId: selectedCaseId, imageId: selectedImageId, runId: selectedRunId },
          imageRows,
          runRows,
        )
        setSelectedImageId(validated.imageId)
        setSelectedRunId(validated.runId)
      })
      .catch((error: unknown) => { if (active) setLoadError(readableError(error)) })
      .finally(() => { if (active) setIsLoadingRuns(false) })
    return () => { active = false }
  }, [selectedCaseId])

  useEffect(() => {
    setNotes('')
  }, [selectedPatientId, selectedCaseId, selectedRunId])

  const selectedPatient = patients.find((patient) => patient.id === selectedPatientId) ?? null
  const availableCases = useMemo(
    () => cases.filter((caseRecord) => caseRecord.patient_id === selectedPatientId),
    [cases, selectedPatientId],
  )
  const selectedCase = cases.find((caseRecord) => caseRecord.id === selectedCaseId) ?? null
  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? null

  useEffect(() => {
    let active = true
    setResults(null)
    setLoadError('')
    setReportMessage('')
    if (!selectedRunId) {
      setIsLoadingResults(false)
      return () => { active = false }
    }
    if (!selectedRun) {
      setIsLoadingResults(false)
      return () => { active = false }
    }
    setIsLoadingResults(true)
    apiRequest<AnalysisResultsResponse>(`/analysis-runs/${encodeURIComponent(selectedRunId)}/results`)
      .then((response) => {
        if (!active) return
        if (!selectedRun || response.run_id !== selectedRun.id || (response.status === 'completed' && response.image_id !== selectedRun.image_id)) {
          setLoadError('The selected run and returned source image do not match. No report was generated.')
          return
        }
        if (selectedRun.image_id && !images.some((image) => image.id === selectedRun.image_id && image.case_id === selectedRun.case_id)) {
          setLoadError('The selected run source image is not available in this case.')
          return
        }
        setResults(response)
      })
      .catch((error: unknown) => { if (active) setLoadError(readableError(error)) })
      .finally(() => { if (active) setIsLoadingResults(false) })
    return () => { active = false }
  }, [selectedRunId, selectedRun, images])

  const report = useMemo(() => buildReportViewModel({
    patient: selectedPatient,
    caseRecord: selectedCase,
    run: selectedRun,
    results,
  }), [selectedPatient, selectedCase, selectedRun, results])

  async function generatePdf() {
    if (!selectedRun || !results || !report.runId || isGenerating) return
    setIsGenerating(true)
    setReportMessage('')
    const temporaryUrls: string[] = []
    const assets: { gradcam?: ReportJpegAsset; localization?: ReportJpegAsset } = {}
    let gradcamReady = false
    let localizationReady = false
    try {
      if (report.gradcamAvailable && report.gradcamUrl && results.source_image_url) {
        try {
          const [sourceBlob, heatmapBlob] = await Promise.all([
            fetchProtectedArtifact(results.source_image_url),
            fetchProtectedArtifact(report.gradcamUrl),
          ])
          const sourceUrl = URL.createObjectURL(sourceBlob)
          const heatmapUrl = URL.createObjectURL(heatmapBlob)
          temporaryUrls.push(sourceUrl, heatmapUrl)
          const overlay = await createGradcamOverlay(sourceUrl, heatmapUrl)
          assets.gradcam = await blobToJpegAsset(overlay)
          gradcamReady = true
        } catch {
          gradcamReady = false
        }
      }
      if (report.localizationAvailable && report.localizationUrl) {
        try {
          assets.localization = await blobToJpegAsset(await fetchProtectedArtifact(report.localizationUrl))
          localizationReady = true
        } catch {
          localizationReady = false
        }
      }
      const pdfBytes = createReportPdf({
        ...report,
        notes,
        gradcamAvailable: gradcamReady,
        localizationAvailable: localizationReady,
      }, assets)
      const copy = pdfBytes.slice().buffer as ArrayBuffer
      const pdfBlob = new Blob([copy], { type: 'application/pdf' })
      const filename = `artery-analysis-${safeFilePart(report.caseId)}-${selectedRun.id.slice(0, 8)}.pdf`
      dispatchReportDownload({
        format: 'PDF', filename, blob: pdfBlob,
        download: dispatchBrowserDownload,
        notify: ({ format, filename: downloadedFilename }) => addReportDownload(format, downloadedFilename),
      })
      setReportMessage(gradcamReady && localizationReady
        ? 'PDF downloaded with both run visualizations.'
        : 'PDF downloaded. Unavailable visualization artifacts are identified in the report.')
    } catch (error) {
      setReportMessage(error instanceof Error ? error.message : 'The report PDF could not be generated.')
    } finally {
      for (const url of temporaryUrls) URL.revokeObjectURL(url)
      setIsGenerating(false)
    }
  }

  function generateJson() {
    if (!selectedRun || !results || !canGenerate) return
    setReportMessage('')
    try {
      const data = buildReportJson(report, { notes })
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' })
      const filename = `artery-analysis-${safeFilePart(report.caseId)}-${selectedRun.id.slice(0, 8)}.json`
      dispatchReportDownload({
        format: 'JSON', filename, blob,
        download: dispatchBrowserDownload,
        notify: ({ format, filename: downloadedFilename }) => addReportDownload(format, downloadedFilename),
      })
      setReportMessage('JSON report download started.')
    } catch (error) {
      setReportMessage(error instanceof Error ? error.message : 'The JSON report could not be generated.')
    }
  }

  function generateCsv() {
    if (!selectedRun || !results || !canGenerate) return
    setReportMessage('')
    try {
      const blob = new Blob([buildReportCsv(report)], { type: 'text/csv;charset=utf-8' })
      const filename = `artery-analysis-${safeFilePart(report.caseId)}-${selectedRun.id.slice(0, 8)}.csv`
      dispatchReportDownload({
        format: 'CSV', filename, blob,
        download: dispatchBrowserDownload,
        notify: ({ format, filename: downloadedFilename }) => addReportDownload(format, downloadedFilename),
      })
      setReportMessage('CSV report download started.')
    } catch (error) {
      setReportMessage(error instanceof Error ? error.message : 'The CSV report could not be generated.')
    }
  }

  function generateReport() {
    if (!canGenerate) return
    if (selectedFormat === 'PDF') {
      void generatePdf()
    } else if (selectedFormat === 'JSON') {
      generateJson()
    } else {
      generateCsv()
    }
  }

  const canGenerate = Boolean(selectedRun && results && !isLoadingResults && !loadError && !isGenerating)

  return (
    <div className="feature-page reports-page">
      <Panel title="Select Analysis Run" className="reports-selection-panel">
        <div className="report-selectors">
          <label>Patient reference<select value={selectedPatientId} disabled={isLoadingRecords} onChange={(event) => { setSelectedPatientId(event.target.value); setSelectedCaseId(''); setSelectedImageId(''); setSelectedRunId('') }}>
            <option value="">{isLoadingRecords ? 'Loading patients…' : patients.length ? 'Select a patient' : 'No patients available'}</option>
            {patients.map((patient) => <option key={patient.id} value={patient.id}>{patient.patient_ref}</option>)}
          </select></label>
          <label>Case ID<select value={selectedCaseId} disabled={!selectedPatientId || isLoadingRecords || !availableCases.length} onChange={(event) => { setSelectedCaseId(event.target.value); setSelectedImageId(''); setSelectedRunId('') }}>
            <option value="">{!selectedPatientId ? 'Select a patient first' : availableCases.length ? 'Select a case' : 'No cases for this patient'}</option>
            {availableCases.map((caseRecord) => <option key={caseRecord.id} value={caseRecord.id}>{caseRecord.case_ref}</option>)}
          </select></label>
          <label>Image<select value={selectedImageId} disabled={!selectedCaseId || isLoadingRuns || !images.length} onChange={(event) => { setSelectedImageId(event.target.value); setSelectedRunId('') }}>
            <option value="">{isLoadingRuns ? 'Loading images…' : !selectedCaseId ? 'Select a case first' : images.length ? 'Select an image' : 'No images available'}</option>
            {images.filter((image) => image.case_id === selectedCaseId).map((image) => <option key={image.id} value={image.id}>{image.original_filename}</option>)}
          </select></label>
          <label>Analysis run<select value={selectedRunId} disabled={!selectedImageId || isLoadingRuns || !runs.some((run) => run.image_id === selectedImageId)} onChange={(event) => setSelectedRunId(event.target.value)}>
            <option value="">{isLoadingRuns ? 'Loading analysis runs…' : !selectedImageId ? 'Select an image first' : runs.some((run) => run.image_id === selectedImageId) ? 'Select an analysis run' : 'No runs for this image'}</option>
            {runs.filter((run) => run.image_id === selectedImageId).map((run) => <option key={run.id} value={run.id}>{new Date(run.created_at).toLocaleString()} · {run.status}</option>)}
          </select></label>
        </div>
      </Panel>
      <Panel title="Download Report" className="reports-download-panel">
        <fieldset className="report-format-fieldset">
          <legend>Select report type</legend>
          <div className="report-format-options" role="radiogroup" aria-label="Select report type">
            {reportFormats.map((format) => <label className={`report-format-option${selectedFormat === format ? ' report-format-option--selected' : ''}`} key={format}>
              <input type="radio" name="report-format" value={format} checked={selectedFormat === format} disabled={isGenerating} onChange={() => setSelectedFormat(format)} />
              <span>{format}</span>
            </label>)}
          </div>
        </fieldset>
        <label className="report-notes-field">Report notes (optional)
          <textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Add notes for this report (optional)..." aria-label="Report notes (optional)" />
        </label>
        {!canGenerate && !loadError && !isLoadingRecords && !isLoadingRuns && !isLoadingResults && <p className="report-validation-note" role="status">Select a valid saved analysis run to enable report generation.</p>}
        <button className="button button--primary generate-report-button" type="button" disabled={!canGenerate} onClick={generateReport}><FileText size={17} /> {isGenerating ? `Generating ${selectedFormat}…` : 'Generate report'}</button>
        {(loadError || reportMessage) && <div className={`analysis-result-message reports-feedback ${loadError ? 'analysis-result-message--error' : ''}`} role={loadError ? 'alert' : 'status'}>{loadError || reportMessage}</div>}
      </Panel>
    </div>
  )
}
