import { useEffect, useMemo, useRef, useState } from 'react'
import Panel from './Panel'
import { apiRequest, apiRequestBlob } from '../auth/api'
import type { AnalysisResultsResponse, AnalysisRunResponse } from '../features/analysis/contracts.mjs'
import { createGradcamOverlay } from '../features/analysis/gradcam-overlay.mjs'
import { toApiRequestPath } from '../features/analysis/contracts.mjs'
import {
  getComparisonDifferences,
  getComparisonRunOptions,
  getRunComparisonSummary,
  validateComparisonSelection,
} from '../features/analysis/run-comparison.mjs'

type ComparisonArtifactName = 'stenosis_mask.png' | 'candidate_overlay.png' | 'gradcam.png'
type ComparisonRunData = {
  run: AnalysisRunResponse
  result: AnalysisResultsResponse
  artifacts: Partial<Record<ComparisonArtifactName, string>>
  artifactErrors: Partial<Record<ComparisonArtifactName, string>>
}

const ARTIFACTS: Array<{ key: ComparisonArtifactName; label: string }> = [
  { key: 'stenosis_mask.png', label: 'Stenosis mask' },
  { key: 'candidate_overlay.png', label: 'Candidate localization overlay' },
  { key: 'gradcam.png', label: 'Grad-CAM visualization' },
]

function revokeAll(urls: Set<string>) {
  urls.forEach((url) => URL.revokeObjectURL(url))
  urls.clear()
}

async function fetchProtectedArtifact(url: string | undefined, origin: string, createUrl: (blob: Blob) => string) {
  if (!url) return undefined
  const path = toApiRequestPath(url, origin)
  if (!path) throw new Error('The backend returned an invalid artifact URL.')
  return createUrl(await apiRequestBlob(path))
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : 'The selected runs could not be loaded.'
}

export default function AnalysisRunComparison({ runs }: { runs: AnalysisRunResponse[] }) {
  const [runAId, setRunAId] = useState('')
  const [runBId, setRunBId] = useState('')
  const [comparison, setComparison] = useState<[ComparisonRunData, ComparisonRunData] | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const requestId = useRef(0)
  const objectUrls = useRef(new Set<string>())
  const runA = runs.find((run) => run.id === runAId)
  const runB = runs.find((run) => run.id === runBId)
  const validSelection = validateComparisonSelection(runA, runB)
  const runBOptions = useMemo(() => getComparisonRunOptions(runs, runAId), [runs, runAId])

  useEffect(() => () => {
    requestId.current += 1
    revokeAll(objectUrls.current)
  }, [])

  function changeRunA(value: string) {
    requestId.current += 1
    revokeAll(objectUrls.current)
    setRunAId(value)
    setRunBId('')
    setComparison(null)
    setError('')
    setMessage('')
  }

  function changeRunB(value: string) {
    requestId.current += 1
    revokeAll(objectUrls.current)
    setRunBId(value)
    setComparison(null)
    setError('')
    setMessage('')
  }

  async function compareRuns() {
    const selection = validateComparisonSelection(runA, runB)
    if (!selection.valid || !runA || !runB) {
      setError(selection.reason)
      return
    }
    const currentRequest = ++requestId.current
    revokeAll(objectUrls.current)
    const localUrls = new Set<string>()
    const createUrl = (blob: Blob) => {
      const url = URL.createObjectURL(blob)
      localUrls.add(url)
      return url
    }
    setIsLoading(true)
    setError('')
    setMessage('')
    setComparison(null)
    try {
      const [resultA, resultB] = await Promise.all([
        apiRequest<AnalysisResultsResponse>(`/analysis-runs/${encodeURIComponent(runA.id)}/results`),
        apiRequest<AnalysisResultsResponse>(`/analysis-runs/${encodeURIComponent(runB.id)}/results`),
      ])
      if (resultA.image_id !== runA.image_id || resultB.image_id !== runB.image_id || resultA.image_id !== resultB.image_id) {
        throw new Error('The saved results do not match the selected runs’ source image IDs.')
      }

      const loadArtifacts = async (run: AnalysisRunResponse, result: AnalysisResultsResponse): Promise<ComparisonRunData> => {
        const artifacts: ComparisonRunData['artifacts'] = {}
        const artifactErrors: ComparisonRunData['artifactErrors'] = {}
        if (result.status !== 'completed') return { run, result, artifacts, artifactErrors }
        for (const { key } of ARTIFACTS) {
          try {
            const artifactUrl = await fetchProtectedArtifact(result.artifacts?.[key], window.location.origin, createUrl)
            if (artifactUrl) artifacts[key] = artifactUrl
          } catch (artifactError) {
            artifactErrors[key] = formatError(artifactError)
          }
        }
        if (artifacts['gradcam.png']) {
          let sourceUrl: string | undefined
          try {
            sourceUrl = await fetchProtectedArtifact(result.source_image_url ?? undefined, window.location.origin, createUrl)
            if (sourceUrl) {
              const coloredOverlay = await createGradcamOverlay(sourceUrl, artifacts['gradcam.png']!, 0.45)
              const rawUrl = artifacts['gradcam.png']
              artifacts['gradcam.png'] = createUrl(coloredOverlay)
              if (rawUrl) {
                URL.revokeObjectURL(rawUrl)
                localUrls.delete(rawUrl)
              }
            } else {
              artifactErrors['gradcam.png'] = 'Original image unavailable; colored Grad-CAM overlay could not be prepared.'
            }
          } catch (overlayError) {
            artifactErrors['gradcam.png'] = `Colored Grad-CAM overlay unavailable: ${formatError(overlayError)}`
          } finally {
            if (sourceUrl) {
              URL.revokeObjectURL(sourceUrl)
              localUrls.delete(sourceUrl)
            }
          }
        }
        return { run, result, artifacts, artifactErrors }
      }

      const [dataA, dataB] = await Promise.all([loadArtifacts(runA, resultA), loadArtifacts(runB, resultB)])
      if (currentRequest !== requestId.current) {
        revokeAll(localUrls)
        return
      }
      localUrls.forEach((url) => objectUrls.current.add(url))
      setComparison([dataA, dataB])
      if (resultA.status !== 'completed' || resultB.status !== 'completed') {
        setMessage('One or both runs did not complete. Only fields and artifacts saved for each run are shown.')
      }
    } catch (compareError) {
      revokeAll(localUrls)
      if (currentRequest === requestId.current) setError(formatError(compareError))
    } finally {
      if (currentRequest === requestId.current) setIsLoading(false)
    }
  }

  const hasComparablePair = runs.some((candidate) => getComparisonRunOptions(runs, candidate.id).length > 0)

  return (
    <Panel title="Compare analysis runs" className="compare-panel">
      <div className="compare-selectors">
        <label>Run A<select value={runAId} disabled={isLoading || !runs.length} onChange={(event) => changeRunA(event.target.value)}>
          <option value="">{runs.length ? 'Select Run A' : 'No saved runs available'}</option>
          {runs.filter((item) => item.image_id).map((item) => <option key={item.id} value={item.id}>{new Date(item.created_at).toLocaleString()} · {item.status}</option>)}
        </select></label>
        <label>Run B<select value={runBId} disabled={isLoading || !runAId || !runBOptions.length} onChange={(event) => changeRunB(event.target.value)}>
          <option value="">{runAId ? runBOptions.length ? 'Select Run B' : 'No other run for this image' : 'Select Run A first'}</option>
          {runBOptions.map((item) => <option key={item.id} value={item.id}>{new Date(item.created_at).toLocaleString()} · {item.status}</option>)}
        </select></label>
      </div>
      <button className="button button--secondary export-button" type="button" disabled={isLoading || !validSelection.valid} onClick={() => void compareRuns()}>
        {isLoading ? 'Loading comparison…' : 'Compare runs'}
      </button>
      {!hasComparablePair && <p className="compare-status" role="status">At least two saved runs for the same source image are required. Start another analysis run on that image to compare it.</p>}
      {hasComparablePair && !validSelection.valid && <p className="compare-status" role="status">{validSelection.reason}</p>}
      {error && <p className="compare-status compare-status--error" role="alert">{error}</p>}
      {message && <p className="compare-status" role="status">{message}</p>}
      {comparison && <ComparisonDetails data={comparison} />}
      {comparison && <p className="compare-disclaimer">Comparison is a review of saved model outputs only. Candidate regions across runs are not matched to the same lesion; narrowing and severity are experimental.</p>}
    </Panel>
  )
}

function ComparisonDetails({ data }: { data: [ComparisonRunData, ComparisonRunData] }) {
  const [dataA, dataB] = data
  const summaryA = getRunComparisonSummary(dataA.run, dataA.result)
  const summaryB = getRunComparisonSummary(dataB.run, dataB.result)
  const differences = getComparisonDifferences(summaryA, summaryB)
  const rows: Array<{ label: string; valueA: string; valueB: string; difference?: string }> = [
    { label: 'Run status', valueA: summaryA.status, valueB: summaryB.status },
    { label: 'Analysis date/time', valueA: summaryA.date, valueB: summaryB.date },
    { label: 'Analysis duration', valueA: summaryA.duration, valueB: summaryB.duration, difference: differences.duration },
    { label: 'Predicted candidate-region count', valueA: summaryA.candidateCount === null ? 'Not available' : String(summaryA.candidateCount), valueB: summaryB.candidateCount === null ? 'Not available' : String(summaryB.candidateCount), difference: differences.candidateCount },
    { label: 'Saved estimated narrowing', valueA: summaryA.narrowing, valueB: summaryB.narrowing },
    { label: 'Saved experimental severity', valueA: summaryA.severity, valueB: summaryB.severity },
    { label: 'Model and threshold metadata', valueA: summaryA.models, valueB: summaryB.models },
  ]
  return <div className="compare-results">
    <div className="compare-values-grid">
      {data.map((item, index) => <section className="compare-run-summary" key={item.run.id}>
        <h3>Run {index === 0 ? 'A' : 'B'}</h3>
        <p className="compare-run-id">{item.run.id}</p>
        <dl>{rows.map((row) => <div key={row.label}><dt>{row.label}</dt><dd>{index === 0 ? row.valueA : row.valueB}</dd>{row.difference && <small>{row.difference}</small>}</div>)}</dl>
      </section>)}
    </div>
    <h3 className="compare-artifacts-heading">Available visual artifacts</h3>
    <div className="compare-artifact-list">{ARTIFACTS.map(({ key, label }) => <section className="compare-artifact-row" key={key}>
      <h4>{label}</h4>
      {data.map((item, index) => <figure key={item.run.id}>
        <figcaption>Run {index === 0 ? 'A' : 'B'}</figcaption>
        {item.artifacts[key] ? <img src={item.artifacts[key]} alt={`${label}, Run ${index === 0 ? 'A' : 'B'}`} /> : <span className="compare-artifact-missing">{item.artifactErrors[key] || 'Not available'}</span>}
      </figure>)}
    </section>)}</div>
  </div>
}
