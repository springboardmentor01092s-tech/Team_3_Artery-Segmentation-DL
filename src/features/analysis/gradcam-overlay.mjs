const clampByte = (value) => Math.max(0, Math.min(255, Math.round(value)))

/** Return the standard triangular JET-style RGB color for one normalized value. */
export function jetColor(value) {
  const normalized = Math.max(0, Math.min(1, Number(value)))
  const channel = (center) => Math.max(0, Math.min(1, 1.5 - Math.abs(4 * normalized - center)))
  return [channel(3), channel(2), channel(1)].map((value) => clampByte(value * 255))
}

/** Blend one JET color over an RGB source pixel using the heatmap opacity. */
export function blendHeatmapPixel(source, heatmap, opacity = 0.45) {
  const alpha = Math.max(0, Math.min(1, Number(opacity)))
  return source.slice(0, 3).map((channel, index) => clampByte(channel * (1 - alpha) + heatmap[index] * alpha))
}

function loadBitmap(url) {
  return fetch(url).then((response) => {
    if (!response.ok) throw new Error('Could not read a Grad-CAM display image.')
    return response.blob()
  }).then((blob) => createImageBitmap(blob))
}

function canvasToPng(canvas) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob)
      else reject(new Error('The colored Grad-CAM overlay could not be encoded.'))
    }, 'image/png')
  })
}

/** Create a display-only JET overlay; source artifacts are read and never modified. */
export async function createGradcamOverlay(originalUrl, heatmapUrl, opacity = 0.45) {
  const [original, heatmap] = await Promise.all([loadBitmap(originalUrl), loadBitmap(heatmapUrl)])
  try {
    const width = original.width
    const height = original.height
    if (!width || !height || !heatmap.width || !heatmap.height) {
      throw new Error('The source image or Grad-CAM map has invalid dimensions.')
    }

    const sourceCanvas = document.createElement('canvas')
    const heatmapCanvas = document.createElement('canvas')
    const outputCanvas = document.createElement('canvas')
    for (const canvas of [sourceCanvas, heatmapCanvas, outputCanvas]) {
      canvas.width = width
      canvas.height = height
    }

    const sourceContext = sourceCanvas.getContext('2d', { willReadFrequently: true })
    const heatmapContext = heatmapCanvas.getContext('2d', { willReadFrequently: true })
    const outputContext = outputCanvas.getContext('2d')
    if (!sourceContext || !heatmapContext || !outputContext) {
      throw new Error('Canvas rendering is unavailable in this browser.')
    }

    sourceContext.drawImage(original, 0, 0, width, height)
    heatmapContext.imageSmoothingEnabled = true
    heatmapContext.imageSmoothingQuality = 'high'
    heatmapContext.drawImage(heatmap, 0, 0, width, height)

    const sourcePixels = sourceContext.getImageData(0, 0, width, height)
    const heatmapPixels = heatmapContext.getImageData(0, 0, width, height)
    const output = outputContext.createImageData(width, height)
    for (let offset = 0; offset < sourcePixels.data.length; offset += 4) {
      const [red, green, blue] = jetColor(heatmapPixels.data[offset] / 255)
      const blended = blendHeatmapPixel(sourcePixels.data.subarray(offset, offset + 3), [red, green, blue], opacity)
      output.data[offset] = blended[0]
      output.data[offset + 1] = blended[1]
      output.data[offset + 2] = blended[2]
      output.data[offset + 3] = sourcePixels.data[offset + 3]
    }
    outputContext.putImageData(output, 0, 0)
    return await canvasToPng(outputCanvas)
  } finally {
    original.close()
    heatmap.close()
  }
}
