import { Activity } from 'lucide-react'
import EmptyState from './EmptyState'
import Panel from './Panel'
import type {
  AnalysisCandidate,
  PercentageNarrowingDisplayState,
  PercentageNarrowingMeasurement,
  SeverityAssessmentResult,
} from '../features/analysis/contracts.mjs'

export function PredictedStenosisCandidatesPanel({ candidates, completed, className = '' }: {
  candidates: AnalysisCandidate[]
  completed: boolean
  className?: string
}) {
  return (
    <Panel title="Predicted stenosis candidates" className={className}>
      {candidates.length ? <div className="candidate-list">
        {candidates.map((candidate) => <article className="candidate-item" key={candidate.candidate_id}>
          <strong>{candidate.label}</strong>
          <span>Bounding box (original image): {candidate.bbox.join(', ')}</span>
          <span>Centroid (original image): {candidate.centroid.map((value) => Number(value).toFixed(1)).join(', ')}</span>
          <span>Area: {candidate.area_pixels} pixels on {candidate.measurement_grid}</span>
        </article>)}
      </div> : <EmptyState icon={Activity} title={completed ? 'No predicted candidates returned' : 'No candidates available'} description={completed ? 'The backend returned no candidate regions for this run.' : 'Candidate metadata appears only for a completed run.'} />}
    </Panel>
  )
}

function getDisplayValue(measurement: PercentageNarrowingMeasurement) {
  const value = measurement.estimated_narrowing_percent
  if (
    measurement.status === 'available'
    && typeof value === 'number'
    && Number.isFinite(value)
    && value >= 0
    && value <= 100
  ) {
    return { available: true, value: `${value.toFixed(1)}%`, numericValue: value }
  }
  return { available: false, value: 'Unavailable', numericValue: null }
}

function getMeasurementUnavailableExplanation(reason?: string) {
  if (reason === 'candidate_predicted_mask_width_not_smaller_than_reference') {
    return 'The predicted stenosis-mask width was not smaller than the reference artery-mask width. No narrowing estimate or severity was assigned.'
  }
  return undefined
}

export function PercentageNarrowingPanel({ state, severityAssessment, candidates, className = '' }: {
  state: PercentageNarrowingDisplayState
  severityAssessment?: SeverityAssessmentResult
  candidates: AnalysisCandidate[]
  className?: string
}) {
  const measurements = 'metadata' in state ? state.metadata.measurements : []
  const values = candidates.map((candidate) => {
    const measurementMatches = measurements.filter((item) => item.candidate_id === candidate.candidate_id)
    const measurement = measurementMatches.length === 1 ? measurementMatches[0] : undefined
    const narrowing = measurement ? getDisplayValue(measurement) : { available: false, value: 'Unavailable', numericValue: null }
    const severityMatches = severityAssessment?.measurements.filter((item) => item.candidate_id === candidate.candidate_id) ?? []
    const severity = narrowing.available
      && measurementMatches.length === 1
      && severityMatches.length === 1
      && severityMatches[0].status === 'available'
      && severityMatches[0].source_narrowing_percent === narrowing.numericValue
      ? severityMatches[0].severity
      : undefined
    const allowedSeverities = ['Normal', 'Mild', 'Moderate', 'Critical']
    return {
      candidateId: candidate.candidate_id,
      narrowing: narrowing.value,
      severity: severity && allowedSeverities.includes(severity) ? severity : 'Unavailable',
      unavailableExplanation: measurement && !narrowing.available
        ? getMeasurementUnavailableExplanation(measurement.unavailable_reason)
        : undefined,
    }
  })

  return (
    <Panel title="Experimental percentage narrowing" className={className}>
      {values.length ? <div className="percentage-narrowing-values" role="status">
        {values.map((item) => <div className="percentage-narrowing-result" key={item.candidateId}>
          <strong className="percentage-narrowing-candidate">Predicted stenosis candidate {item.candidateId}</strong>
          <p className="percentage-narrowing-value"><span>Estimated narrowing:</span> <strong>{item.narrowing}</strong></p>
          <p className="percentage-narrowing-value"><span>Severity:</span> <strong>{item.severity}</strong></p>
          {item.unavailableExplanation && <small className="percentage-narrowing-diagnostic">{item.unavailableExplanation}</small>}
        </div>)}
      </div> : <EmptyState icon={Activity} title="No predicted candidates" description="Candidate-specific narrowing and severity estimates are unavailable for this run." />}
    </Panel>
  )
}
