export function buildAnalysisRunRequest(caseId, imageId) {
  return {
    path: `/cases/${encodeURIComponent(caseId)}/analysis-runs`,
    init: {
      method: 'POST',
      body: JSON.stringify({ image_id: imageId }),
    },
  }
}

export function caseAnalysisRunsPath(caseId) {
  return `/cases/${encodeURIComponent(caseId)}/analysis-runs`
}

export function getAnalysisImageResources(result) {
  if (result.status !== 'completed') return []
  const resources = []
  if (result.source_image_url) {
    resources.push({ key: 'original_image', label: 'Original image', url: result.source_image_url, kind: 'image' })
  }
  const artifactLabels = {
    'artery_mask.png': { label: 'Artery mask', kind: 'image' },
    'stenosis_mask.png': { label: 'Stenosis mask', kind: 'image' },
    'candidate_overlay.png': { label: 'Candidate localization overlay', kind: 'image' },
    'combined_visualization.png': { label: 'Combined visualization', kind: 'image' },
    'gradcam.png': { label: 'Grad-CAM model explanation — not a confirmed stenosis boundary.', kind: 'image' },
    'candidates.json': { label: 'Candidate metadata JSON', kind: 'json' },
  }
  for (const [key, url] of Object.entries(result.artifacts ?? {})) {
    const artifact = artifactLabels[key]
    if (artifact && typeof url === 'string' && url) {
      resources.push({ key, ...artifact, url })
    }
  }
  return resources
}

export function getGradCAMDisplayState(result, resources) {
  if (result.status !== 'completed') return { status: 'not_ready' }
  const hasArtifact = resources.some((resource) => resource.key === 'gradcam.png')
  if (result.metadata?.models?.gradcam_available === true && hasArtifact) {
    return { status: 'available' }
  }
  const reason = result.metadata?.models?.gradcam_unavailable_reason
  return {
    status: 'unavailable',
    reason: typeof reason === 'string' && reason ? reason : 'No Grad-CAM artifact was returned for this run.',
  }
}

export function getPercentageNarrowingDisplayState(result) {
  if (result.status !== 'completed') return { status: 'not_ready' }
  const metadata = result.metadata?.percentage_narrowing
  if (!metadata) return { status: 'not_calculated' }
  if (!Array.isArray(metadata.measurements) || !['available', 'partial', 'unavailable'].includes(metadata.status)) {
    return { status: 'invalid', reason: 'The saved run contains invalid percentage-narrowing metadata.' }
  }
  return { status: metadata.status, metadata }
}

/** Convert only same-origin API URLs to paths accepted by the authenticated request helpers. */
export function toApiRequestPath(resourceUrl, origin) {
  try {
    const resolved = new URL(resourceUrl, origin)
    if (resolved.origin !== origin || !resolved.pathname.startsWith('/api/v1/')) return null
    return `${resolved.pathname.slice('/api/v1'.length)}${resolved.search}`
  } catch {
    return null
  }
}
