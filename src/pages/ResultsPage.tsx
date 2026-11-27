import { useEffect, useMemo, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import { Download, FileImage, Move, RotateCcw, Ruler, ZoomIn, ZoomOut } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import Panel from '../components/Panel'
import { PercentageNarrowingPanel, PredictedStenosisCandidatesPanel } from '../components/ResultsSummaryPanels'
import AnalysisRunComparison from '../components/AnalysisRunComparison'
import { apiRequest, apiRequestBlob } from '../auth/api'
import type { CaseRecord } from '../features/cases/types'
import {
  caseAnalysisRunsPath,
  getAnalysisImageResources,
  getGradCAMDisplayState,
  getPercentageNarrowingDisplayState,
  toApiRequestPath,
} from '../features/analysis/contracts.mjs'
import { createGradcamOverlay } from '../features/analysis/gradcam-overlay.mjs'
import {
  clampViewerPan,
  stepViewerScale,
  VIEWER_MAX_SCALE,
  VIEWER_MIN_SCALE,
} from '../features/analysis/viewer-controls.mjs'
import type { ViewerOffset } from '../features/analysis/viewer-controls.mjs'

type ResultImageRecord = {
  id: string
  case_id: string
  original_filename: string
}

const LATEST_ANALYSIS_RUN_SESSION_KEY = 'artery-latest-analysis-run'

function getInitialRunId() {
  const urlRunId = new URLSearchParams(window.location.search).get('run_id')?.trim()
  if (urlRunId) return urlRunId
  try {
    return window.sessionStorage.getItem(LATEST_ANALYSIS_RUN_SESSION_KEY) ?? ''
  } catch {
    return ''
  }
}
import type {
  AnalysisImageResource,
  AnalysisResultsResponse,
  AnalysisRunResponse,
} from '../features/analysis/contracts.mjs'

const resultViews: Array<{ key: AnalysisImageResource['key']; label: string }> = [
  { key: 'original_image', label: 'Original image' },
  { key: 'artery_mask.png', label: 'Artery mask' },
  { key: 'stenosis_mask.png', label: 'Stenosis mask' },
  { key: 'candidate_overlay.png', label: 'Candidate overlay' },
  { key: 'gradcam.png', label: 'Grad-CAM visualization' },
]

function readableRunError(error: unknown) {
  if (error instanceof Error && 'status' in error && error.status === 404) {
    return 'This run was not found or is not available to your account.'
  }
  return error instanceof Error ? error.message : 'Unable to load this analysis run.'
}

export default function ResultsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedRunId, setSelectedRunId] = useState(getInitialRunId)
  const [cases, setCases] = useState<CaseRecord[]>([])
  const [selectedCaseId, setSelectedCaseId] = useState('')
  const [images, setImages] = useState<ResultImageRecord[]>([])
  const [selectedImageId, setSelectedImageId] = useState('')
  const [caseRuns, setCaseRuns] = useState<AnalysisRunResponse[]>([])
  const [isLoadingCases, setIsLoadingCases] = useState(true)
  const [isLoadingCaseData, setIsLoadingCaseData] = useState(false)
  const [caseListError, setCaseListError] = useState('')
  const [caseDataError, setCaseDataError] = useState('')
  const [run, setRun] = useState<AnalysisRunResponse | null>(null)
  const [result, setResult] = useState<AnalysisResultsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [resourceUrls, setResourceUrls] = useState<Record<string, string>>({})
  const [resourceErrors, setResourceErrors] = useState<Record<string, string>>({})
  const [gradcamOverlayUrl, setGradcamOverlayUrl] = useState('')
  const [gradcamOverlayError, setGradcamOverlayError] = useState('')
  const [isPreparingGradcamOverlay, setIsPreparingGradcamOverlay] = useState(false)
  const [activeViewKey, setActiveViewKey] = useState<AnalysisImageResource['key']>('original_image')
  const [viewerScale, setViewerScale] = useState(1)
  const [viewerOffset, setViewerOffset] = useState<ViewerOffset>({ x: 0, y: 0 })
  const [panMode, setPanMode] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [viewerImageReady, setViewerImageReady] = useState(false)
  const viewerStageRef = useRef<HTMLDivElement>(null)
  const viewerImageRef = useRef<HTMLImageElement>(null)
  const dragStartRef = useRef<{ pointerId: number; startX: number; startY: number; offset: ViewerOffset } | null>(null)
  const runId = selectedRunId

  function resetViewer(clearImageReady = false) {
    dragStartRef.current = null
    setViewerScale(1)
    setViewerOffset({ x: 0, y: 0 })
    setPanMode(false)
    setIsDragging(false)
    if (clearImageReady) setViewerImageReady(false)
  }

  function clampCurrentPan(offset: ViewerOffset, scale: number) {
    const image = viewerImageRef.current
    const stage = viewerStageRef.current
    if (!image || !stage) return { x: 0, y: 0 }
    return clampViewerPan(offset, {
      imageWidth: image.offsetWidth,
      imageHeight: image.offsetHeight,
      stageWidth: stage.clientWidth,
      stageHeight: stage.clientHeight,
      scale,
    })
  }

  function zoomViewer(direction: -1 | 1) {
    if (!viewerImageReady) return
    const nextScale = stepViewerScale(viewerScale, direction)
    setViewerScale(nextScale)
    setViewerOffset((current) => clampCurrentPan(current, nextScale))
  }

  function changeViewer(viewKey: AnalysisImageResource['key']) {
    if (activeViewKey === viewKey) return
    resetViewer(true)
    setActiveViewKey(viewKey)
  }

  function beginPan(event: ReactPointerEvent<HTMLImageElement>) {
    if (!panMode || viewerScale <= 1 || event.button !== 0) return
    event.preventDefault()
    event.currentTarget.setPointerCapture(event.pointerId)
    dragStartRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      offset: viewerOffset,
    }
    setIsDragging(true)
  }

  function movePan(event: ReactPointerEvent<HTMLImageElement>) {
    const start = dragStartRef.current
    if (!start || start.pointerId !== event.pointerId) return
    event.preventDefault()
    setViewerOffset(clampCurrentPan({
      x: start.offset.x + event.clientX - start.startX,
      y: start.offset.y + event.clientY - start.startY,
    }, viewerScale))
  }

  function endPan(event: ReactPointerEvent<HTMLImageElement>) {
    if (dragStartRef.current?.pointerId !== event.pointerId) return
    dragStartRef.current = null
    setIsDragging(false)
  }

  useEffect(() => {
    const urlRunId = searchParams.get('run_id')?.trim()
    if (urlRunId && urlRunId !== selectedRunId) setSelectedRunId(urlRunId)
  }, [searchParams, selectedRunId])

  useEffect(() => {
    resetViewer(true)
  }, [runId])

  useEffect(() => {
    let active = true
    setIsLoadingCases(true)
    apiRequest<CaseRecord[]>('/cases')
      .then((records) => { if (active) setCases(records) })
      .catch((error: unknown) => { if (active) setCaseListError(readableRunError(error)) })
      .finally(() => { if (active) setIsLoadingCases(false) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    let active = true
    if (!selectedCaseId) {
      setImages([])
      setCaseRuns([])
      setIsLoadingCaseData(false)
      setCaseDataError('')
      return () => { active = false }
    }
    setIsLoadingCaseData(true)
    setCaseDataError('')
    const encodedCaseId = encodeURIComponent(selectedCaseId)
    Promise.all([
      apiRequest<ResultImageRecord[]>(`/cases/${encodedCaseId}/images`),
      apiRequest<AnalysisRunResponse[]>(caseAnalysisRunsPath(selectedCaseId)),
    ])
      .then(([imageRecords, runs]) => {
        if (!active) return
        setImages(imageRecords)
        setCaseRuns(runs)
      })
      .catch((error: unknown) => { if (active) setCaseDataError(readableRunError(error)) })
      .finally(() => { if (active) setIsLoadingCaseData(false) })
    return () => { active = false }
  }, [selectedCaseId])

  useEffect(() => {
    let active = true
    setRun(null)
    setResult(null)
    setLoadError('')
    if (!runId) {
      setIsLoading(false)
      return () => { active = false }
    }
    setIsLoading(true)
    const encodedRunId = encodeURIComponent(runId)
    Promise.all([
      apiRequest<AnalysisRunResponse>(`/analysis-runs/${encodedRunId}`),
      apiRequest<AnalysisResultsResponse>(`/analysis-runs/${encodedRunId}/results`),
    ])
      .then(([runRecord, results]) => {
        if (!active) return
        setRun(runRecord)
        setResult(results)
        setSelectedCaseId(runRecord.case_id)
        setSelectedImageId(runRecord.image_id ?? '')
        if (runRecord.status === 'completed') {
          try {
            window.sessionStorage.setItem(LATEST_ANALYSIS_RUN_SESSION_KEY, runRecord.id)
          } catch {
            // URL-based selection remains available when session storage is unavailable.
          }
        }
      })
      .catch((error: unknown) => {
        if (active) setLoadError(readableRunError(error))
      })
      .finally(() => { if (active) setIsLoading(false) })
    return () => { active = false }
  }, [runId])

  const resources = useMemo(() => result
    ? getAnalysisImageResources(result).filter((resource) => resource.key !== 'combined_visualization.png' && resource.key !== 'candidates.json')
    : [], [result])
  const gradcamState = result ? getGradCAMDisplayState(result, resources) : { status: 'not_ready' as const }
  const gradcamResourceAvailable = gradcamState.status === 'available'
  const gradcamUnavailableReason = gradcamState.status === 'unavailable' ? gradcamState.reason : ''

  useEffect(() => {
    let active = true
    const createdUrls: string[] = []
    setResourceUrls({})
    setResourceErrors({})
    if (!result || result.status !== 'completed') {
      return () => { active = false }
    }
    Promise.all(resources.map(async (resource) => {
      const path = toApiRequestPath(resource.url, window.location.origin)
      if (!path) {
        if (active) setResourceErrors((current) => ({ ...current, [resource.key]: 'The backend returned an invalid artifact URL.' }))
        return
      }
      try {
        const blob = await apiRequestBlob(path)
        const objectUrl = URL.createObjectURL(blob)
        if (active) {
          createdUrls.push(objectUrl)
          setResourceUrls((current) => ({ ...current, [resource.key]: objectUrl }))
        } else {
          URL.revokeObjectURL(objectUrl)
        }
      } catch (error) {
        if (active) setResourceErrors((current) => ({
          ...current,
          [resource.key]: error instanceof Error ? error.message : 'This artifact could not be retrieved.',
        }))
      }
    }))
    return () => {
      active = false
      createdUrls.forEach((url) => URL.revokeObjectURL(url))
    }
  }, [resources, result])

  useEffect(() => {
    let active = true
    let overlayUrl = ''
    const originalUrl = resourceUrls.original_image
    const rawHeatmapUrl = resourceUrls['gradcam.png']
    setGradcamOverlayUrl('')
    setGradcamOverlayError('')
    if (!gradcamResourceAvailable || !originalUrl || !rawHeatmapUrl) {
      setIsPreparingGradcamOverlay(false)
      return () => { active = false }
    }
    setIsPreparingGradcamOverlay(true)
    createGradcamOverlay(originalUrl, rawHeatmapUrl, 0.45)
      .then((blob) => {
        if (!active) return
        overlayUrl = URL.createObjectURL(blob)
        setGradcamOverlayUrl(overlayUrl)
      })
      .catch((error: unknown) => {
        if (active) setGradcamOverlayError(error instanceof Error ? error.message : 'Colored overlay could not be prepared.')
      })
      .finally(() => { if (active) setIsPreparingGradcamOverlay(false) })
    return () => {
      active = false
      if (overlayUrl) URL.revokeObjectURL(overlayUrl)
    }
  }, [gradcamResourceAvailable, resourceUrls.original_image, resourceUrls['gradcam.png']])

  const completed = result?.status === 'completed'
  const activeView = resultViews.find((view) => view.key === activeViewKey) ?? resultViews[0]
  const activeResourceUrl = activeView ? resourceUrls[activeView.key] : undefined
  const activeResourceExists = activeView ? resources.some((resource) => resource.key === activeView.key) : false
  const activeDisplayUrl = activeView?.key === 'gradcam.png' ? gradcamOverlayUrl || activeResourceUrl : activeResourceUrl
  const candidates = completed ? result.metadata?.candidates ?? [] : []
  const percentageNarrowingState = result ? getPercentageNarrowingDisplayState(result) : { status: 'not_ready' as const }
  const visibleRuns = caseRuns.filter((item) => !selectedImageId || item.image_id === selectedImageId)

  function selectCase(caseId: string) {
    resetViewer(true)
    setSelectedCaseId(caseId)
    setSelectedImageId('')
    setSelectedRunId('')
    setRun(null)
    setResult(null)
    setLoadError('')
    setSearchParams({}, { replace: false })
  }

  function selectImage(imageId: string) {
    resetViewer(true)
    setSelectedImageId(imageId)
    setSelectedRunId('')
    setRun(null)
    setResult(null)
    setLoadError('')
    setSearchParams({}, { replace: false })
  }

  function selectRun(runIdValue: string) {
    resetViewer(true)
    setSelectedRunId(runIdValue)
    setRun(null)
    setResult(null)
    setLoadError('')
    setSearchParams(runIdValue ? { run_id: runIdValue } : {}, { replace: false })
  }

  return (
    <div className="feature-page results-page">
      <Panel title="Select analysis" className="results-select-panel">
        <div className="result-selectors">
          <label>Case<select value={selectedCaseId} disabled={isLoadingCases} onChange={(event) => selectCase(event.target.value)}><option value="">{isLoadingCases ? 'Loading cases…' : cases.length ? 'Select a case' : 'No cases available'}</option>{cases.map((record) => <option key={record.id} value={record.id}>{record.case_ref}</option>)}</select></label>
          <label>Image<select value={selectedImageId} disabled={!selectedCaseId || isLoadingCaseData} onChange={(event) => selectImage(event.target.value)}><option value="">{!selectedCaseId ? 'Select a case first' : isLoadingCaseData ? 'Loading images…' : images.length ? 'All images in case' : 'No images available'}</option>{images.map((image) => <option key={image.id} value={image.id}>{image.original_filename}</option>)}</select></label>
          <label>Analysis run<select value={selectedRunId} disabled={!selectedCaseId || isLoadingCaseData} onChange={(event) => selectRun(event.target.value)}><option value="">{!selectedCaseId ? 'Select a case first' : isLoadingCaseData ? 'Loading runs…' : visibleRuns.length ? 'Select a run' : 'No runs for this selection'}</option>{visibleRuns.map((item) => <option key={item.id} value={item.id}>{new Date(item.created_at).toLocaleString()} · {item.status}</option>)}{run && !visibleRuns.some((item) => item.id === run.id) && run.case_id === selectedCaseId && <option value={run.id}>{new Date(run.created_at).toLocaleString()} · {run.status}</option>}</select></label>
        </div>
      </Panel>

      {caseListError && <div className="analysis-result-message analysis-result-message--error" role="alert">Unable to load cases: {caseListError}</div>}
      {caseDataError && <div className="analysis-result-message analysis-result-message--error" role="alert">Unable to load images and runs for this case: {caseDataError}</div>}
      {!runId ? <div className="analysis-result-message" role="status"><FileImage size={18} /> {selectedCaseId ? 'Select an image and an existing analysis run to view its results.' : 'No analysis run is selected. Choose a case, image, and saved run, or start analysis from an uploaded image.'}</div> : isLoading ? <div className="analysis-result-message" role="status">Loading saved analysis results…</div> : loadError ? <div className="analysis-result-message analysis-result-message--error" role="alert">{loadError}</div> : result && result.status !== 'completed' ? <div className="analysis-result-message analysis-result-message--error" role="status"><strong>Analysis {result.status}</strong><span>{result.detail || run?.failure_message || 'This run did not return completed results.'}</span></div> : null}

      <div className="results-workspace">
        <Panel title="Image viewer" className="image-viewer-panel results-viewer-panel">
          <div className="viewer-tabs" role="tablist" aria-label="Returned analysis artifacts">
            {resultViews.map((view) => <button key={view.key} className={`viewer-tab ${activeView?.key === view.key ? 'viewer-tab--active' : ''}`} type="button" role="tab" aria-selected={activeView?.key === view.key} disabled={!completed} onClick={() => changeViewer(view.key)}>{view.label}</button>)}
          </div>
          <div className="viewer-tab-actions">
            {activeView?.key === 'gradcam.png' && (gradcamOverlayUrl
              ? <a className="viewer-download-action" href={gradcamOverlayUrl} download="gradcam_overlay.png"><Download size={14} /> Download Grad-CAM PNG</a>
              : <span role="status">{gradcamOverlayError ? 'Colored Grad-CAM overlay unavailable.' : gradcamResourceAvailable ? 'Preparing Grad-CAM download…' : completed ? `Grad-CAM unavailable — ${gradcamUnavailableReason}` : 'Select a completed run to access this artifact.'}</span>)}
            {activeView?.key === 'candidate_overlay.png' && (resourceUrls['candidate_overlay.png']
              ? <a className="viewer-download-action" href={resourceUrls['candidate_overlay.png']} download="candidate_overlay.png"><Download size={14} /> Download candidate overlay</a>
              : <span role="status">{resourceErrors['candidate_overlay.png'] || (completed ? 'Candidate overlay unavailable for this run.' : 'Select a completed run to access this artifact.')}</span>)}
          </div>
          <div ref={viewerStageRef} className={`viewer-stage${panMode && viewerScale > 1 ? ' viewer-stage--pan-ready' : ''}${isDragging ? ' viewer-stage--panning' : ''}`} aria-busy={isLoading}>
            {activeDisplayUrl && activeView && !(activeView.key === 'gradcam.png' && isPreparingGradcamOverlay) ? <img ref={viewerImageRef} key={`${activeView.key}-${activeView.key === 'gradcam.png' && gradcamOverlayUrl ? 'overlay' : 'raw'}`} className="results-viewer-image" src={activeDisplayUrl} alt={activeView.label} draggable={false} onLoad={() => setViewerImageReady(true)} onDragStart={(event) => event.preventDefault()} onPointerDown={beginPan} onPointerMove={movePan} onPointerUp={endPan} onPointerCancel={endPan} onLostPointerCapture={endPan} style={{ transform: `translate3d(${viewerOffset.x}px, ${viewerOffset.y}px, 0) scale(${viewerScale})` }} /> : loadError ? <div className="viewer-placeholder"><span><FileImage size={27} /></span><strong>Results unavailable</strong><p>{loadError}</p></div> : !runId ? <div className="viewer-placeholder"><span><FileImage size={27} /></span><strong>No run selected</strong><p>Start analysis from a saved image to view actual returned output.</p></div> : isLoading ? <div className="viewer-placeholder" role="status"><span><FileImage size={27} /></span><strong>Loading results…</strong></div> : !completed ? <div className="viewer-placeholder"><span><FileImage size={27} /></span><strong>Completed output unavailable</strong><p>The selected run did not complete successfully.</p></div> : activeView?.key === 'gradcam.png' && !gradcamResourceAvailable ? <div className="viewer-placeholder" role="status"><span><FileImage size={27} /></span><strong>Grad-CAM unavailable</strong><p>{gradcamUnavailableReason}</p></div> : activeView?.key === 'gradcam.png' && isPreparingGradcamOverlay ? <div className="viewer-placeholder" role="status"><span><FileImage size={27} /></span><strong>Preparing colored Grad-CAM overlay…</strong></div> : activeView && resourceErrors[activeView.key] ? <div className="viewer-placeholder"><span><FileImage size={27} /></span><strong>Artifact unavailable</strong><p>{resourceErrors[activeView.key]}</p></div> : activeView && activeResourceExists ? <div className="viewer-placeholder" role="status"><span><FileImage size={27} /></span><strong>Loading {activeView.label.toLowerCase()}…</strong></div> : activeView && completed ? <div className="viewer-placeholder" role="status"><span><FileImage size={27} /></span><strong>Artifact not returned</strong><p>The selected run did not return a {activeView.label.toLowerCase()} image.</p></div> : <div className="viewer-placeholder"><span><FileImage size={27} /></span><strong>Loading results…</strong></div>}
          </div>
          <div className="viewer-toolbar" aria-label="Image viewer controls">
            <button type="button" disabled={!viewerImageReady || viewerScale >= VIEWER_MAX_SCALE} title={`Zoom in${viewerImageReady ? ` (${Math.round(stepViewerScale(viewerScale, 1) * 100)}%)` : ''}`} aria-label="Zoom in" onClick={() => zoomViewer(1)}><ZoomIn size={16} /></button>
            <button type="button" disabled={!viewerImageReady || viewerScale <= VIEWER_MIN_SCALE} title="Zoom out" aria-label="Zoom out" onClick={() => zoomViewer(-1)}><ZoomOut size={16} /></button>
            <button type="button" disabled={!viewerImageReady || viewerScale <= 1} className={panMode ? 'viewer-tool--active' : ''} aria-pressed={panMode} title={viewerScale <= 1 ? 'Zoom in before panning' : 'Toggle drag-to-pan'} aria-label="Pan" onClick={() => setPanMode((current) => !current)}><Move size={16} /></button>
            <button type="button" disabled={!viewerImageReady || (viewerScale === 1 && viewerOffset.x === 0 && viewerOffset.y === 0 && !panMode)} title="Reset zoom and position" aria-label="Reset view" onClick={() => resetViewer()}><RotateCcw size={16} /></button>
            <button type="button" disabled title="Calibrated physical measurement is unavailable" aria-label="Measure (calibrated physical measurement unavailable)"><Ruler size={16} /></button>
          </div>
        </Panel>
        <div className="result-side-stack results-summary-stack">
          <PredictedStenosisCandidatesPanel className="results-candidates-panel" candidates={candidates} completed={completed} />
          <PercentageNarrowingPanel
            className="results-narrowing-panel"
            state={percentageNarrowingState}
            severityAssessment={completed ? result?.metadata?.severity_assessment : undefined}
            candidates={candidates}
          />
        </div>
      </div>
      <div className="results-comparison-wrap"><AnalysisRunComparison runs={visibleRuns} /></div>
    </div>
  )
}
