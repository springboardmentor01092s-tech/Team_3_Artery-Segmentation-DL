import { useEffect, useRef, useState } from 'react'
import { Activity, Check, Circle, Clock3, FileImage, Info, Play, SlidersHorizontal, UploadCloud } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import Panel from '../components/Panel'
import WorkspaceNotice from '../components/WorkspaceNotice'
import { apiRequest, apiRequestBlob } from '../auth/api'
import { useCases } from '../features/cases/useCases'

type ImageRecord = {
  id: string
  case_id: string
  original_filename: string
  media_type: string
  size_bytes: number
  created_at: string
}

type PreprocessingMetadata = {
  input_width: number
  input_height: number
  output_width: number
  output_height: number
  output_shape: number[]
  data_type: string
  channel_format: string
  intensity_range: number[]
  output_persisted: boolean
}

type PreprocessingStatus = {
  image_id: string
  status: 'not_started' | 'completed' | 'failed'
  message: string
  attempt_count: number
  updated_at: string | null
  result: PreprocessingMetadata | null
}

const ACCEPTED_EXTENSIONS = new Set(['png', 'jpg', 'jpeg'])
const SELECTED_CASE_SESSION_KEY = 'artery-image-upload-selected-case'

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function describeUploadError(error: unknown) {
  if (error instanceof Error && 'status' in error) {
    if (error.status === 413) return 'The server rejected this file because it exceeds the configured size limit.'
    if (error.status === 415) return error.message
    if (error.status === 404) return 'The selected case is no longer available to your account.'
  }
  return error instanceof Error ? error.message : 'Unable to upload this image. Please try again.'
}

const stages = ['Image upload', 'Preprocessing', 'Artery segmentation', 'Stenosis detection', 'Results generation']

export default function UploadAnalysisPage() {
  const { cases, patients, isLoading: isLoadingCases, hasLoadedData, error: caseError, reload: reloadCases } = useCases()
  const [patientId, setPatientId] = useState('')
  const [caseId, setCaseId] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [fileError, setFileError] = useState('')
  const [uploadError, setUploadError] = useState('')
  const [uploadNotice, setUploadNotice] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState('')
  const [images, setImages] = useState<ImageRecord[]>([])
  const [isLoadingImages, setIsLoadingImages] = useState(false)
  const [imageListError, setImageListError] = useState('')
  const [refreshImages, setRefreshImages] = useState(0)
  const [previewUrls, setPreviewUrls] = useState<Record<string, string>>({})
  const [previewErrors, setPreviewErrors] = useState<Record<string, boolean>>({})
  const [preprocessing, setPreprocessing] = useState<Record<string, PreprocessingStatus & { loading?: boolean }>>({})
  const [preprocessingLoadError, setPreprocessingLoadError] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const selectionRestored = useRef(false)
  const selectedCase = cases.find((item) => item.id === caseId) ?? null
  const selectedPatient = patients.find((item) => item.id === (selectedCase?.patient_id ?? patientId)) ?? null
  const availableCases = patientId ? cases.filter((item) => item.patient_id === patientId) : cases

  useEffect(() => {
    if (!hasLoadedData || selectionRestored.current) return
    selectionRestored.current = true
    let savedCaseId = ''
    try {
      savedCaseId = window.sessionStorage.getItem(SELECTED_CASE_SESSION_KEY) ?? ''
    } catch {
      return
    }
    if (!savedCaseId) return
    const ownedCase = cases.find((item) => item.id === savedCaseId)
    if (!ownedCase) {
      window.sessionStorage.removeItem(SELECTED_CASE_SESSION_KEY)
      return
    }
    setPatientId(ownedCase.patient_id)
    setCaseId(ownedCase.id)
  }, [cases, hasLoadedData])

  useEffect(() => {
    let active = true
    if (!caseId) {
      setImages([])
      setIsLoadingImages(false)
      setImageListError('')
      setPreprocessing({})
      setPreprocessingLoadError('')
      return () => { active = false }
    }
    setIsLoadingImages(true)
    setImageListError('')
    setPreprocessing({})
    setPreprocessingLoadError('')
    apiRequest<ImageRecord[]>(`/cases/${caseId}/images`)
      .then((records) => { if (active) setImages(records) })
      .catch((error: unknown) => { if (active) setImageListError(error instanceof Error ? error.message : 'Unable to load images.') })
      .finally(() => { if (active) setIsLoadingImages(false) })
    apiRequest<PreprocessingStatus[]>(`/cases/${caseId}/preprocessing`)
      .then((records) => {
        if (!active) return
        setPreprocessing(Object.fromEntries(records.map((record) => [record.image_id, record])))
      })
      .catch((error: unknown) => {
        if (active) setPreprocessingLoadError(error instanceof Error ? error.message : 'Unable to load saved preprocessing status.')
      })
    return () => { active = false }
  }, [caseId, refreshImages])

  useEffect(() => {
    let active = true
    const urls: string[] = []
    setPreviewUrls({})
    setPreviewErrors({})
    Promise.all(images.map(async (image) => {
      try {
        const blob = await apiRequestBlob(`/images/${image.id}/content`)
        const url = URL.createObjectURL(blob)
        if (active) {
          urls.push(url)
          setPreviewUrls((current) => ({ ...current, [image.id]: url }))
        } else {
          URL.revokeObjectURL(url)
        }
      } catch {
        if (active) setPreviewErrors((current) => ({ ...current, [image.id]: true }))
      }
    }))
    return () => {
      active = false
      urls.forEach((url) => URL.revokeObjectURL(url))
    }
  }, [images])

  function chooseFiles(selection: FileList | null) {
    if (!selection) return
    const selected = Array.from(selection)
    const valid = selected.filter((file) => ACCEPTED_EXTENSIONS.has(file.name.split('.').pop()?.toLowerCase() ?? ''))
    setFileError(valid.length === selected.length ? '' : 'Only PNG, JPG, and JPEG extensions are accepted. The server also validates the actual image content.')
    setFiles(valid)
    setUploadError('')
    setUploadNotice('')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  async function uploadSelectedFiles() {
    if (!caseId || files.length === 0 || isUploading) return
    setIsUploading(true)
    setUploadError('')
    setUploadNotice('')
    let uploaded = 0
    try {
      for (let index = 0; index < files.length; index += 1) {
        setUploadProgress(`Uploading ${index + 1} of ${files.length}…`)
        const form = new FormData()
        form.append('file', files[index], files[index].name)
        await apiRequest<ImageRecord>(`/cases/${caseId}/images`, { method: 'POST', body: form })
        uploaded += 1
      }
      setFiles([])
      setFileError('')
      setUploadNotice(`${uploaded} image${uploaded === 1 ? '' : 's'} uploaded and saved to this case.`)
    } catch (error) {
      setUploadError(uploaded ? `${uploaded} image${uploaded === 1 ? '' : 's'} uploaded; the next file failed. ${describeUploadError(error)}` : describeUploadError(error))
      if (uploaded) setFiles((current) => current.slice(uploaded))
    } finally {
      setIsUploading(false)
      setUploadProgress('')
      if (uploaded) setRefreshImages((current) => current + 1)
    }
  }

  async function preprocessImage(image: ImageRecord) {
    setPreprocessing((current) => ({
      ...current,
      [image.id]: {
        image_id: image.id,
        status: current[image.id]?.status ?? 'not_started',
        message: current[image.id]?.message ?? 'Preprocessing is running.',
        attempt_count: current[image.id]?.attempt_count ?? 0,
        updated_at: current[image.id]?.updated_at ?? null,
        result: current[image.id]?.result ?? null,
        loading: true,
      },
    }))
    try {
      const result = await apiRequest<PreprocessingStatus>(`/images/${image.id}/preprocess`, { method: 'POST' })
      setPreprocessing((current) => ({ ...current, [image.id]: result }))
    } catch (error) {
      setPreprocessing((current) => ({
        ...current,
        [image.id]: {
          image_id: image.id,
          status: 'failed',
          message: error instanceof Error ? error.message : 'Preprocessing could not be completed.',
          attempt_count: current[image.id]?.attempt_count ?? 0,
          updated_at: current[image.id]?.updated_at ?? null,
          result: null,
        },
      }))
    }
  }

  return (
    <div className="feature-page upload-page">
      <WorkspaceNotice />
      <PageHeader title="Image Upload and Analysis" description="Stage angiography images and review the analysis workflow for a case." />
      <div className="upload-case-row">
        <Panel title="1. Select case" className="upload-case-panel">
          <div className="select-grid">
            <label>Patient reference<select value={patientId} disabled={isLoadingCases || !hasLoadedData || isUploading} onChange={(event) => { setPatientId(event.target.value); setCaseId(''); window.sessionStorage.removeItem(SELECTED_CASE_SESSION_KEY); setFiles([]); setFileError(''); setUploadNotice('') }}>
              <option value="">{patients.length ? 'All patients' : isLoadingCases ? 'Loading patients…' : 'No patients available'}</option>
              {patients.map((patient) => <option key={patient.id} value={patient.id}>{patient.patient_ref}</option>)}
            </select></label>
            <label>Case ID<select value={caseId} disabled={isLoadingCases || availableCases.length === 0 || isUploading} onChange={(event) => { const nextCaseId = event.target.value; setCaseId(nextCaseId); if (nextCaseId) window.sessionStorage.setItem(SELECTED_CASE_SESSION_KEY, nextCaseId); else window.sessionStorage.removeItem(SELECTED_CASE_SESSION_KEY); setFiles([]); setFileError(''); setUploadNotice('') }}>
              <option value="">{isLoadingCases ? 'Loading cases…' : availableCases.length ? 'Select a case' : 'No cases available'}</option>
              {availableCases.map((item) => <option key={item.id} value={item.id}>{item.case_ref}</option>)}
            </select></label>
          </div>
          {caseError && <div className="upload-inline-error" role="alert">{caseError}<button className="button button--secondary button--small" type="button" onClick={() => void reloadCases()}>Retry</button></div>}
        </Panel>
        <Panel title="Case details" className="case-summary-panel">
          {selectedCase ? <>
            <div className="case-summary-empty"><FileImage size={19} /><span>{selectedCase.case_ref}{selectedPatient ? ` · ${selectedPatient.patient_ref}` : ''}</span></div>
            <div className="case-summary-meta"><span>Modality <strong>{selectedCase.modality || 'Not specified'}</strong></span><span>Images <strong>{images.length}</strong></span><span>Analysis <strong className="state-pill state-pill--muted">Unavailable</strong></span></div>
          </> : <div className="case-summary-empty"><FileImage size={19} /><span>Select an existing case to view its details.</span></div>}
        </Panel>
      </div>
      <div className="upload-grid">
        <Panel title="2. Upload images" className="upload-drop-panel">
          <div className="upload-dropzone">
            <span className="upload-dropzone__icon"><UploadCloud size={27} /></span>
            <strong>{selectedCase ? 'Add images to the selected case' : 'Select a case before adding images'}</strong>
            <span>PNG, JPG, and JPEG · Server-enforced size limit (10 MiB default)</span>
            <input ref={fileInputRef} className="upload-file-input" type="file" accept=".png,.jpg,.jpeg,image/png,image/jpeg" multiple disabled={!selectedCase || isUploading} onChange={(event) => chooseFiles(event.target.files)} aria-label="Choose image files" />
            <button className="button button--primary button--small" type="button" disabled={!selectedCase || isUploading} onClick={() => fileInputRef.current?.click()}><UploadCloud size={15} /> Choose files</button>
            {files.length > 0 && <div className="upload-selected-files"><strong>{files.length} file{files.length === 1 ? '' : 's'} selected</strong><ul>{files.map((file, index) => <li key={`${file.name}-${index}`}>{file.name} <span>{formatBytes(file.size)}</span></li>)}</ul></div>}
            {fileError && <p className="upload-client-error" role="alert">{fileError}</p>}
            <button className="button button--secondary button--small upload-submit" type="button" disabled={!selectedCase || files.length === 0 || isUploading} onClick={() => void uploadSelectedFiles()}><UploadCloud size={15} /> {isUploading ? uploadProgress : 'Upload selected images'}</button>
            {uploadNotice && <p className="upload-success" role="status">{uploadNotice}</p>}
            {uploadError && <p className="upload-client-error" role="alert">{uploadError}</p>}
          </div>
          <div className="upload-guidance"><h3>Upload guidance</h3><ul><li>Use supported PNG, JPG, or JPEG files.</li><li>The server validates image content and size.</li><li>Choose an existing case owned by your account.</li><li>Files are stored by the backend and linked to the selected case.</li></ul></div>
        </Panel>
        <Panel title={`Images in selected case${caseId ? ` (${images.length})` : ''}`} className="uploaded-list-panel">
          <div className="uploaded-list-head"><span>Preview</span><span>File name</span><span>Format</span><span>Size</span><span>Status</span><span>Preprocessing</span></div>
          {!caseId ? <div className="uploaded-list-empty"><FileImage size={20} /><span>Select a case</span><small>Choose a case to load its saved image records.</small></div> : isLoadingImages ? <div className="uploaded-list-empty" role="status"><FileImage size={20} /><span>Loading images…</span></div> : imageListError ? <div className="uploaded-list-empty"><FileImage size={20} /><span>Unable to load images</span><small>{imageListError}</small><button className="button button--secondary button--small" type="button" onClick={() => setRefreshImages((current) => current + 1)}>Retry</button></div> : images.length === 0 ? <div className="uploaded-list-empty"><FileImage size={20} /><span>No images uploaded</span><small>There are no saved images associated with this case.</small></div> : <div className="uploaded-image-list" aria-live="polite">
            {images.map((image) => <div className="uploaded-image-row" key={image.id}>
              <div className="uploaded-image-preview">{previewUrls[image.id] ? <a href={previewUrls[image.id]} target="_blank" rel="noreferrer" aria-label={`Open preview of ${image.original_filename}`}><img src={previewUrls[image.id]} alt={`Preview of ${image.original_filename}`} /></a> : <span>{previewErrors[image.id] ? 'Preview unavailable' : 'Loading preview…'}</span>}</div>
              <span className="uploaded-image-name" title={image.original_filename}>{image.original_filename}</span>
              <span>{image.media_type.split('/')[1]?.toUpperCase() ?? image.media_type}</span>
              <span>{formatBytes(image.size_bytes)}</span>
              <span className="state-pill state-pill--muted">Saved</span>
              <div className="uploaded-preprocess-action">
                {preprocessing[image.id]?.status !== 'completed' && <button className="button button--secondary button--small" type="button" disabled={preprocessing[image.id]?.loading} onClick={() => void preprocessImage(image)}>
                  {preprocessing[image.id]?.loading ? 'Processing…' : preprocessing[image.id]?.status === 'failed' ? 'Retry' : 'Preprocess'}
                </button>}
                {preprocessing[image.id]?.status === 'completed' && preprocessing[image.id]?.result && <>
                  <strong className="preprocess-complete" role="status">Completed · {preprocessing[image.id].result?.output_width} × {preprocessing[image.id].result?.output_height}</strong>
                  <small>float32 CHW · metadata saved</small>
                  <small className="preprocess-result-note">{preprocessing[image.id].message} Range {preprocessing[image.id].result?.intensity_range.join('–')}.</small>
                </>}
                {preprocessing[image.id]?.status === 'failed' && <small className="upload-client-error" role="alert">{preprocessing[image.id].message}</small>}
                {preprocessingLoadError && <small className="upload-client-error" role="alert">Saved status unavailable: {preprocessingLoadError}</small>}
              </div>
            </div>)}
          </div>}
        </Panel>
      </div>
      <div className="analysis-grid">
        <Panel title="4. Preprocessing options" className="preprocessing-panel">
          <label className="check-option"><input type="checkbox" disabled /> Noise reduction</label>
          <label className="check-option"><input type="checkbox" disabled /> Contrast enhancement</label>
          <label className="check-option"><input type="checkbox" disabled /> Resize to model input size</label>
          <label className="check-option"><input type="checkbox" disabled /> Normalize intensity</label>
          <label className="check-option check-option--recommended"><input type="checkbox" disabled /> Apply recommended preprocessing</label>
          <p className="muted-hint"><SlidersHorizontal size={14} /> Options will be enabled with a configured processing pipeline.</p>
        </Panel>
        <Panel title="5. Analysis settings" className="analysis-settings-panel">
          <label className="settings-label">Model version<select disabled defaultValue=""><option value="">No model configured</option></select></label>
          <span className="settings-label">Analysis tasks</span>
          <label className="check-option"><input type="checkbox" disabled /> Artery segmentation</label>
          <label className="check-option"><input type="checkbox" disabled /> Stenosis detection</label>
          <button className="button button--primary start-analysis-button" type="button" disabled><Play size={15} /> Start analysis</button>
          <div className="not-configured-note"><Info size={15} /> Analysis unavailable until a real model is integrated.</div>
        </Panel>
        <Panel title="6. Analysis progress" className="progress-panel">
          <div className="progress-state"><span className="state-pill state-pill--muted">Not configured</span></div>
          <ol className="progress-steps">{stages.map((stage, index) => <li key={stage}><span className="progress-step-icon">{index === 0 ? <Clock3 size={14} /> : <Circle size={12} />}</span><span>{stage}</span><small>Waiting</small></li>)}</ol>
        </Panel>
      </div>
      <Panel title="7. Activity log" className="activity-log-panel">
        <div className="log-empty"><Activity size={16} /><span>No processing activity yet.</span></div>
      </Panel>
      <div className="page-bottom-note"><Check size={14} /> Selected images are stored by the backend. Analysis is unavailable; no predictions or measurements are generated.</div>
    </div>
  )
}
