export const VIEWER_MIN_SCALE = 0.75
export const VIEWER_MAX_SCALE = 3
export const VIEWER_SCALE_STEP = 0.25

export function stepViewerScale(currentScale, direction) {
  const directionStep = Math.sign(direction)
  if (!directionStep) return Math.min(VIEWER_MAX_SCALE, Math.max(VIEWER_MIN_SCALE, currentScale))
  const stepped = currentScale + directionStep * VIEWER_SCALE_STEP
  return Math.min(VIEWER_MAX_SCALE, Math.max(VIEWER_MIN_SCALE, Math.round(stepped * 100) / 100))
}

export function clampViewerPan(offset, geometry) {
  const maxX = Math.max(0, (geometry.imageWidth * geometry.scale - geometry.stageWidth) / 2)
  const maxY = Math.max(0, (geometry.imageHeight * geometry.scale - geometry.stageHeight) / 2)
  return {
    x: maxX === 0 ? 0 : Math.min(maxX, Math.max(-maxX, offset.x)),
    y: maxY === 0 ? 0 : Math.min(maxY, Math.max(-maxY, offset.y)),
  }
}
