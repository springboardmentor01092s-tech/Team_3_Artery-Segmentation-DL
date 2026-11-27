export function jetColor(value: number): number[]
export function blendHeatmapPixel(source: ArrayLike<number>, heatmap: ArrayLike<number>, opacity?: number): number[]
export function createGradcamOverlay(originalUrl: string, heatmapUrl: string, opacity?: number): Promise<Blob>
