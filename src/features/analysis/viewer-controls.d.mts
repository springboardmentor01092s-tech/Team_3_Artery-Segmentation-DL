export const VIEWER_MIN_SCALE: number
export const VIEWER_MAX_SCALE: number
export const VIEWER_SCALE_STEP: number

export type ViewerOffset = { x: number; y: number }
export type ViewerPanGeometry = {
  imageWidth: number
  imageHeight: number
  stageWidth: number
  stageHeight: number
  scale: number
}

export declare function stepViewerScale(currentScale: number, direction: number): number
export declare function clampViewerPan(offset: ViewerOffset, geometry: ViewerPanGeometry): ViewerOffset
