const PAGE_WIDTH = 595.28
const PAGE_HEIGHT = 841.89
const LEFT = 43
const RIGHT = 552
const CONTENT_WIDTH = RIGHT - LEFT
const encoder = new TextEncoder()

function ascii(value) {
  return String(value ?? 'Unavailable')
    .replace(/[×]/g, 'x')
    .replace(/[·•]/g, '-')
    .replace(/[–—]/g, '-')
    .replace(/[^\x20-\x7e]/g, ' ')
}

function escapePdf(value) {
  return ascii(value).replaceAll('\\', '\\\\').replaceAll('(', '\\(').replaceAll(')', '\\)')
}

function rgb(hex) {
  const value = hex.replace('#', '')
  return [0, 2, 4].map((offset) => Number.parseInt(value.slice(offset, offset + 2), 16) / 255)
}

function fillColor(hex) {
  return `${rgb(hex).map((value) => value.toFixed(3)).join(' ')} rg`
}

function strokeColor(hex) {
  return `${rgb(hex).map((value) => value.toFixed(3)).join(' ')} RG`
}

function textOp(x, y, value, size = 8, font = 'F1', color = '#314154') {
  return `BT /${font} ${size} Tf ${fillColor(color)} 1 0 0 1 ${x.toFixed(2)} ${y.toFixed(2)} Tm (${escapePdf(value)}) Tj ET\n`
}

function rectOp(x, y, width, height, fill, stroke = '#d4e0ea') {
  return `q ${fillColor(fill)} ${strokeColor(stroke)} 0.55 w ${x} ${y} ${width} ${height} re B Q\n`
}

function lineOp(x1, y1, x2, y2, color = '#2f7fc0', width = 0.8) {
  return `q ${strokeColor(color)} ${width} w ${x1} ${y1} m ${x2} ${y2} l S Q\n`
}

function fitText(value, maxWidth, size) {
  let output = ascii(value)
  const maxCharacters = Math.max(1, Math.floor(maxWidth / (size * 0.53)))
  if (output.length > maxCharacters) output = `${output.slice(0, Math.max(1, maxCharacters - 3))}...`
  return output
}

function drawHeader(ops, continuation = false) {
  ops.push(textOp(LEFT + 5, 798, 'CoronAI', 9, 'F2', '#173d63'))
  ops.push(textOp(LEFT + 5, 786, 'AI-ASSISTED IMAGING REVIEW', 6.8, 'F1', '#536e8a'))
  ops.push(textOp(444, 798, continuation ? 'REPORT CONTINUED' : 'ANALYSIS REPORT', 7.2, 'F2', '#173d63'))
  ops.push(lineOp(LEFT, 777, RIGHT, 777))
}

function drawMetadata(ops, report) {
  const labels = ['PATIENT / SUBJECT ID', 'CASE ID', 'IMAGE ID', 'ANALYSIS DATE']
  const values = [report.patientId, report.caseId, report.imageId, report.analysisDate]
  const columnWidth = CONTENT_WIDTH / 4
  const bottom = 635
  const labelHeight = 19
  const valueHeight = 29
  for (let index = 0; index < 4; index += 1) {
    const x = LEFT + index * columnWidth
    ops.push(rectOp(x, bottom + valueHeight, columnWidth, labelHeight, '#edf3f8'))
    ops.push(rectOp(x, bottom, columnWidth, valueHeight, '#f8fafc'))
    ops.push(textOp(x + 7, bottom + valueHeight + 6.5, labels[index], 5.7, 'F2', '#6b8098'))
    ops.push(textOp(x + 7, bottom + 10.5, fitText(values[index], columnWidth - 13, 7.2), 7.2, 'F2', '#263b50'))
  }
}

function drawOverview(ops, report, top = 604) {
  ops.push(textOp(LEFT + 12, top, '1. Analysis overview', 11.2, 'F2', '#183e63'))
  const x = LEFT
  const y = 518
  const columnWidth = CONTENT_WIDTH / 4
  const labels = ['PREDICTED CANDIDATES', 'ESTIMATED NARROWING', 'SEVERITY LABEL', 'RUN STATUS']
  const values = [report.predictedCandidates, report.estimatedNarrowing, report.severity, report.runStatus]
  for (let index = 0; index < 4; index += 1) {
    const cellX = x + index * columnWidth
    ops.push(rectOp(cellX, y + 51, columnWidth, 20, '#edf3f8'))
    ops.push(rectOp(cellX, y, columnWidth, 51, '#f1f6fa'))
    ops.push(textOp(cellX + 7, y + 58, labels[index], 5.4, 'F2', '#6b8098'))
    const color = index === 2 && report.severity !== 'Unavailable' && !report.severity.startsWith('See ')
      ? '#159b91'
      : '#163d62'
    const size = values[index].length > 20 ? 8 : values[index].length > 12 ? 10 : 14
    ops.push(textOp(cellX + 7, y + 20, fitText(values[index], columnWidth - 13, size), size, 'F2', color))
  }
}

const candidateColumns = [
  { title: 'CANDIDATE', width: 75 },
  { title: 'LOCATION', width: 175 },
  { title: 'NARROWING', width: 77 },
  { title: 'SEVERITY', width: 68 },
  { title: 'STATUS', width: CONTENT_WIDTH - 75 - 175 - 77 - 68 },
]

function drawCandidateTable(ops, rows, startIndex, endIndex, top, continued = false) {
  const sectionTitle = continued ? '2. Candidate-level findings (continued)' : '2. Candidate-level findings'
  ops.push(textOp(LEFT + 12, top, sectionTitle, 11.2, 'F2', '#183e63'))
  let y = top - 38
  let x = LEFT
  for (const column of candidateColumns) {
    ops.push(rectOp(x, y, column.width, 19, '#edf3f8'))
    ops.push(textOp(x + 5, y + 6.5, column.title, 5.5, 'F2', '#6b8098'))
    x += column.width
  }
  const items = rows.length ? rows.slice(startIndex, endIndex) : [{
    candidate: 'Unavailable', location: 'No candidate records returned', narrowing: 'Unavailable', severity: 'Unavailable', status: 'Unavailable',
  }]
  y -= 23
  for (const row of items) {
    x = LEFT
    const values = [row.candidate, row.location, row.narrowing, row.severity, row.status]
    for (let index = 0; index < candidateColumns.length; index += 1) {
      const column = candidateColumns[index]
      ops.push(rectOp(x, y, column.width, 23, '#ffffff'))
      ops.push(textOp(x + 5, y + 8.2, fitText(values[index], column.width - 10, 6.4), 6.4, index === 0 ? 'F2' : 'F1', '#34475a'))
      x += column.width
    }
    y -= 23
  }
  return y
}

function drawImage(ops, asset, x, y, width, height, name, paintPanel = true) {
  if (paintPanel) ops.push(rectOp(x, y, width, height, '#f6f9fc'))
  if (!asset?.jpeg?.length || !asset.width || !asset.height) {
    ops.push(textOp(x + width / 2 - 25, y + height / 2 - 2, 'Unavailable', 8, 'F2', '#78899b'))
    return
  }
  const scale = Math.min(width / asset.width, height / asset.height)
  const drawWidth = asset.width * scale
  const drawHeight = asset.height * scale
  const drawX = x + (width - drawWidth) / 2
  const drawY = y + (height - drawHeight) / 2
  ops.push(`q ${drawWidth.toFixed(2)} 0 0 ${drawHeight.toFixed(2)} ${drawX.toFixed(2)} ${drawY.toFixed(2)} cm /${name} Do Q\n`)
}

function wrapNoteLines(notes, maxCharacters = 130) {
  if (typeof notes !== 'string' || !notes.trim()) return []
  const lines = []
  for (const paragraph of notes.replace(/\r\n?/g, '\n').split('\n')) {
    if (!paragraph) {
      lines.push('')
      continue
    }
    let line = ''
    for (const word of paragraph.split(/\s+/)) {
      if (!line) line = word
      else if (`${line} ${word}`.length <= maxCharacters) line += ` ${word}`
      else {
        lines.push(line)
        line = word
      }
      while (line.length > maxCharacters) {
        lines.push(line.slice(0, maxCharacters))
        line = line.slice(maxCharacters)
      }
    }
    if (line) lines.push(line)
  }
  return lines
}

function reportSupplement(report) {
  const noteLines = wrapNoteLines(report.notes)
  const height = 17 + noteLines.length * 8
  return { noteLines, height }
}

function drawSupplement(ops, report, startY, { noteStart = 0, noteLimit = Infinity, continued = false } = {}) {
  const { noteLines } = reportSupplement(report)
  let y = startY
  if (!continued) {
    ops.push(textOp(LEFT + 12, y, '4. Report Notes', 9, 'F2', '#183e63'))
    y -= 15
  } else {
    ops.push(textOp(LEFT + 12, y, '4. Report Notes (continued)', 9, 'F2', '#183e63'))
    y -= 17
  }
  const end = Math.min(noteLines.length, noteStart + noteLimit)
  for (let index = noteStart; index < end; index += 1) {
    ops.push(textOp(LEFT + 13, y, fitText(noteLines[index] || ' ', CONTENT_WIDTH - 18, 6.2), 6.2, 'F1', '#53677d'))
    y -= 8
  }
  return end
}

function drawVisualizations(ops, report, assets, top, afterCaptions) {
  ops.push(textOp(LEFT + 12, top, '3. AI visualizations', 11.2, 'F2', '#183e63'))
  const panelTop = top - 18
  const panelHeight = Math.max(122, Math.min(190, panelTop - 106))
  const panelY = panelTop - panelHeight
  const gap = 18
  const panelWidth = (CONTENT_WIDTH - gap) / 2
  const leftX = LEFT + 30
  const rightX = leftX + panelWidth + gap
  ops.push(rectOp(leftX, panelY, panelWidth, panelHeight, '#f6f9fc'))
  ops.push(rectOp(rightX, panelY, panelWidth, panelHeight, '#f6f9fc'))
  ops.push(textOp(leftX + 4, panelY - 13, 'Grad-CAM overlay', 7, 'F2', '#173d63'))
  ops.push(textOp(leftX + 4, panelY - 24, 'Model explanation blended with the original angiography image.', 5.8, 'F1', '#708196'))
  ops.push(textOp(rightX + 4, panelY - 13, 'Stenosis candidate bounding box', 7, 'F2', '#173d63'))
  ops.push(textOp(rightX + 4, panelY - 24, 'Predicted localization only; not a confirmed stenosis.', 5.8, 'F1', '#708196'))
  if (!report.gradcamAvailable) ops.push(textOp(leftX + 4, panelY - 36, 'Grad-CAM artifact unavailable for this run.', 5.5, 'F1', '#8592a1'))
  if (!report.localizationAvailable) ops.push(textOp(rightX + 4, panelY - 36, 'Localization artifact unavailable for this run.', 5.5, 'F1', '#8592a1'))
  afterCaptions?.(panelY - 44)
  drawImage(ops, assets.gradcam, leftX, panelY, panelWidth, panelHeight, 'Im1', false)
  drawImage(ops, assets.localization, rightX, panelY, panelWidth, panelHeight, 'Im2', false)
  return panelY - 44
}

function drawFooter(ops, pageIndex, pageCount) {
  ops.push(lineOp(LEFT, 47, RIGHT, 47, '#d7e2ec', 0.6))
  ops.push(textOp(LEFT + 1, 34, 'AI-ASSISTED IMAGING REVIEW - NOT A STANDALONE CLINICAL DIAGNOSIS', 5.6, 'F1', '#8796a7'))
  ops.push(textOp(RIGHT - 36, 34, `Page ${pageIndex + 1} of ${pageCount}`, 5.6, 'F1', '#8796a7'))
}

function lastCandidateSupplementStart(candidateRows, candidatePageCount) {
  const pageIndex = candidatePageCount - 1
  const titleTop = pageIndex === 0 ? 495 : 750
  const first = pageIndex * 8
  const count = candidateRows.length ? Math.min(8, candidateRows.length - first) : 1
  const tableBottom = titleTop - 61 - 23 * count
  const visualsTop = Math.min(tableBottom - 22, 447)
  const panelTop = visualsTop - 18
  const panelHeight = Math.max(122, Math.min(190, panelTop - 106))
  return panelTop - panelHeight - 44
}

function createPageOps(report, assets, candidateRange, pageIndex, pageCount, candidatePageCount, includeSupplement) {
  const ops = []
  drawHeader(ops, pageIndex > 0)
  if (pageIndex === 0) {
    ops.push(textOp(LEFT + 13, 744, 'Coronary Angiography', 20, 'F2', '#173d63'))
    ops.push(textOp(LEFT + 13, 720, 'Analysis Report', 20, 'F2', '#173d63'))
    ops.push(textOp(LEFT + 13, 703, 'AI-assisted segmentation, stenosis candidate review and experimental narrowing estimate.', 7.8, 'F1', '#6b8098'))
    drawMetadata(ops, report)
    drawOverview(ops, report)
  }

  const continued = pageIndex > 0
  const titleTop = pageIndex === 0 ? 495 : 750
  const tableBottom = drawCandidateTable(ops, report.candidateRows, candidateRange[0], candidateRange[1], titleTop, continued)
  const hasMoreCandidates = candidateRange[1] < report.candidateRows.length
  if (hasMoreCandidates) {
    ops.push(textOp(LEFT + 12, Math.max(110, tableBottom - 10), 'Additional candidate findings continue on the next page.', 6.2, 'F1', '#77889a'))
    drawFooter(ops, pageIndex, pageCount)
  } else {
    const visualsTop = Math.min(tableBottom - 22, 447)
    drawFooter(ops, pageIndex, pageCount)
    drawVisualizations(ops, report, assets, visualsTop, (startY) => {
      if (includeSupplement) drawSupplement(ops, report, startY)
    })
  }
  return ops.join('')
}

function createSupplementPageOps(report, pageIndex, pageCount, noteStart, firstSupplementPage) {
  const ops = []
  drawHeader(ops, true)
  const nextNoteLine = drawSupplement(ops, report, 744, {
    noteStart,
    noteLimit: firstSupplementPage ? 70 : 78,
    continued: !firstSupplementPage,
  })
  drawFooter(ops, pageIndex, pageCount)
  return { content: ops.join(''), nextNoteLine }
}

function bytesFrom(value) {
  return value instanceof Uint8Array ? value : new Uint8Array(value ?? [])
}

function concat(chunks) {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0)
  const result = new Uint8Array(length)
  let offset = 0
  for (const chunk of chunks) {
    result.set(chunk, offset)
    offset += chunk.length
  }
  return result
}

function objectBytes(id, body) {
  return concat([encoder.encode(`${id} 0 obj\n`), body, encoder.encode('\nendobj\n')])
}

function streamObject(id, dictionary, stream) {
  const data = encoder.encode(stream)
  return objectBytes(id, encoder.encode(`<< ${dictionary} /Length ${data.length} >>\nstream\n${stream}endstream`))
}

function imageObject(id, asset) {
  const bytes = bytesFrom(asset.jpeg)
  const head = encoder.encode(`${id} 0 obj\n<< /Type /XObject /Subtype /Image /Width ${asset.width} /Height ${asset.height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${bytes.length} >>\nstream\n`)
  return concat([head, bytes, encoder.encode('\nendstream\nendobj\n')])
}

function buildPdf(objects, catalogId, pagesId) {
  const fileChunks = [encoder.encode('%PDF-1.4\n%ArteryAnalysis\n')]
  const offsets = [0]
  let fileLength = fileChunks[0].length
  objects.forEach((object, index) => {
    offsets.push(fileLength)
    fileChunks.push(object)
    fileLength += object.length
  })
  const xrefOffset = fileLength
  const xref = [`xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`]
  for (let index = 1; index < offsets.length; index += 1) xref.push(`${String(offsets[index]).padStart(10, '0')} 00000 n \n`)
  const trailer = `trailer\n<< /Size ${objects.length + 1} /Root ${catalogId} 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`
  fileChunks.push(encoder.encode(xref.join('') + trailer))
  return concat(fileChunks)
}

export function createReportPdf(report, assets = {}) {
  const candidateRows = Array.isArray(report.candidateRows) ? report.candidateRows : []
  const perPage = 8
  const candidatePageCount = Math.max(1, Math.ceil(Math.max(1, candidateRows.length) / perPage))
  const supplement = reportSupplement(report)
  const hasNotes = supplement.noteLines.length > 0
  const fitsOnFinalCandidatePage = hasNotes
    && supplement.height <= lastCandidateSupplementStart(candidateRows, candidatePageCount) - 55
  const supplementPageCount = !hasNotes || fitsOnFinalCandidatePage
    ? 0
    : 1 + Math.ceil(Math.max(0, supplement.noteLines.length - 70) / 78)
  const pageCount = candidatePageCount + supplementPageCount
  const regularFontId = 3 + pageCount * 2
  const boldFontId = regularFontId + 1
  let nextId = boldFontId + 1
  const pageDefinitions = []
  const contentObjects = []
  const imageDefinitions = []

  if (assets.gradcam?.jpeg?.length && assets.gradcam.width && assets.gradcam.height) {
    imageDefinitions.push({ key: 'Im1', id: nextId++, asset: assets.gradcam })
  }
  if (assets.localization?.jpeg?.length && assets.localization.width && assets.localization.height) {
    imageDefinitions.push({ key: 'Im2', id: nextId++, asset: assets.localization })
  }

  for (let pageIndex = 0; pageIndex < pageCount; pageIndex += 1) {
    if (pageIndex >= candidatePageCount) {
      const supplementPageIndex = pageIndex - candidatePageCount
      const noteStart = supplementPageIndex === 0 ? 0 : 70 + (supplementPageIndex - 1) * 78
      const supplemental = createSupplementPageOps(report, pageIndex, pageCount, noteStart, supplementPageIndex === 0)
      const pageId = 3 + pageIndex * 2
      const contentId = pageId + 1
      pageDefinitions.push({ id: pageId, bytes: objectBytes(pageId, encoder.encode(
        `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${PAGE_WIDTH} ${PAGE_HEIGHT}] /Resources << /Font << /F1 ${regularFontId} 0 R /F2 ${boldFontId} 0 R >> >> /Contents ${contentId} 0 R >>`,
      )) })
      contentObjects.push(streamObject(contentId, '', supplemental.content))
      continue
    }
    const start = pageIndex * perPage
    const end = Math.min(candidateRows.length, start + perPage)
    const hasMore = end < candidateRows.length
    const includeSupplement = hasNotes && pageIndex === candidatePageCount - 1 && fitsOnFinalCandidatePage
    const pageOps = createPageOps(report, assets, [start, end], pageIndex, pageCount, candidatePageCount, includeSupplement)
      .replaceAll('/Im1 Do', imageDefinitions.some((item) => item.key === 'Im1') ? '/Im1 Do' : '')
      .replaceAll('/Im2 Do', imageDefinitions.some((item) => item.key === 'Im2') ? '/Im2 Do' : '')
    const pageId = 3 + pageIndex * 2
    const contentId = pageId + 1
    const xObjects = imageDefinitions.length
      ? `/XObject << ${imageDefinitions.map((item) => `/${item.key} ${item.id} 0 R`).join(' ')} >>`
      : ''
    pageDefinitions.push({ id: pageId, bytes: objectBytes(pageId, encoder.encode(
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${PAGE_WIDTH} ${PAGE_HEIGHT}] /Resources << /Font << /F1 ${regularFontId} 0 R /F2 ${boldFontId} 0 R >> ${xObjects} >> /Contents ${contentId} 0 R >>`,
    )) })
    contentObjects.push(streamObject(contentId, '', pageOps))
    if (hasMore && pageIndex === candidatePageCount - 1) throw new Error('Report pagination did not include every candidate.')
  }

  const kids = pageDefinitions.map((item) => `${item.id} 0 R`).join(' ')
  const objectMap = new Map([
    [1, objectBytes(1, encoder.encode('<< /Type /Catalog /Pages 2 0 R >>'))],
    [2, objectBytes(2, encoder.encode(`<< /Type /Pages /Kids [${kids}] /Count ${pageCount} >>`))],
  ])
  for (const definition of pageDefinitions) objectMap.set(definition.id, definition.bytes)
  for (let pageIndex = 0; pageIndex < pageCount; pageIndex += 1) objectMap.set(4 + pageIndex * 2, contentObjects[pageIndex])
  objectMap.set(regularFontId, objectBytes(regularFontId, encoder.encode('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')))
  objectMap.set(boldFontId, objectBytes(boldFontId, encoder.encode('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>')))
  for (const definition of imageDefinitions) objectMap.set(definition.id, imageObject(definition.id, definition.asset))
  const objects = Array.from({ length: Math.max(...objectMap.keys()) }, (_, index) => {
    const object = objectMap.get(index + 1)
    if (!object) throw new Error(`PDF object ${index + 1} is missing.`)
    return object
  })
  return buildPdf(objects, 1, 2)
}

export async function blobToJpegAsset(blob, quality = 0.9) {
  const bitmap = await createImageBitmap(blob)
  try {
    const canvas = document.createElement('canvas')
    canvas.width = bitmap.width
    canvas.height = bitmap.height
    const context = canvas.getContext('2d')
    if (!context) throw new Error('Image conversion is unavailable in this browser.')
    context.drawImage(bitmap, 0, 0)
    const jpeg = await new Promise((resolve, reject) => {
      canvas.toBlob((encoded) => encoded ? resolve(encoded) : reject(new Error('Could not encode the report image.')), 'image/jpeg', quality)
    })
    return { jpeg: new Uint8Array(await jpeg.arrayBuffer()), width: bitmap.width, height: bitmap.height }
  } finally {
    bitmap.close()
  }
}

