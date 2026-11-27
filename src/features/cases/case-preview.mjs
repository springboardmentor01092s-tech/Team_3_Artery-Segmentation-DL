export function getCasePreviewImages(images) {
  return images.slice(0, 6)
}

export function caseImageContentPath(imageId) {
  return `/images/${encodeURIComponent(imageId)}/content`
}
