const size = 1080
const inset = 76
const textWidth = size - 2 * inset
const paper = '#f8f7f0'
const ink = '#183b2f'
const gold = '#b7914b'
const sans = '"Avenir Next", "Segoe UI", Arial, sans-serif'
const serif = 'Georgia, "Times New Roman", serif'
const headings = { winner: 'Winner announcement', launch: 'Lunch invitation', results: 'Lunch results' }
const tooLong = 'Shorten the caption to fit the image, or copy the full caption.'
const graphemes = typeof Intl.Segmenter === 'function' ? new Intl.Segmenter(undefined, { granularity: 'grapheme' }) : null

function wrapCaption(context, caption) {
  const lines = []
  for (const paragraph of caption.replace(/\r\n?/g, '\n').split('\n')) {
    let line = ''
    // Keep spaces within lines and honor explicit paragraph breaks.
    for (const word of paragraph.match(/\S+\s*|\s+/gu) || []) {
      if (context.measureText((line + word).trimEnd()).width <= textWidth) {
        line += word
        continue
      }
      if (line) lines.push(line.trimEnd())
      line = word
      if (context.measureText(word.trimEnd()).width <= textWidth) continue

      // A URL, hashtag or unspaced script can be wider than a whole line.
      line = ''
      for (const part of graphemes ? graphemes.segment(word) : word) {
        const character = graphemes ? part.segment : part
        if (line && context.measureText(line + character).width > textWidth) {
          lines.push(line)
          line = ''
        }
        line += character
      }
    }
    lines.push(line.trimEnd())
  }
  return lines
}

function drawCaption(context, caption) {
  const top = 235
  const bottom = 915
  for (let fontSize = 58; fontSize >= 34; fontSize -= 3) {
    context.font = `400 ${fontSize}px ${sans}`
    const lines = wrapCaption(context, caption)
    const leading = Math.ceil(fontSize * 1.28)
    const height = lines.reduce((total, line) => total + (line ? leading : leading / 2), 0)
    if (height > bottom - top || lines.some(line => context.measureText(line).width > textWidth)) continue
    let y = top + Math.min(82, (bottom - top - height) / 3)
    for (const line of lines) {
      if (line) context.fillText(line, inset, y)
      y += line ? leading : leading / 2
    }
    return
  }
  throw new Error(tooLong)
}

function drawSignature(context) {
  context.strokeStyle = '#cccfc2'
  context.lineWidth = 2
  context.beginPath()
  context.moveTo(inset, 945)
  context.lineTo(size - inset, 945)
  context.stroke()

  const x = inset + 26
  const y = 998
  context.strokeStyle = gold
  for (const radius of [24, 17]) {
    context.beginPath()
    context.arc(x, y, radius, 0, Math.PI * 2)
    context.stroke()
  }
  context.fillStyle = '#2e6245'
  context.beginPath()
  context.moveTo(x + 12, y - 10)
  context.quadraticCurveTo(x + 8, y - 28, x + 29, y - 30)
  context.quadraticCurveTo(x + 30, y - 12, x + 12, y - 10)
  context.fill()
  context.fillStyle = ink
  context.textBaseline = 'middle'
  context.font = `36px ${serif}`
  context.fillText('golden plate', inset + 67, y)
  context.fillStyle = '#555f55'
  context.font = `28px ${sans}`
  context.textAlign = 'right'
  context.fillText('goldenplate.ca', size - inset, y)
}

export async function createSchoolPostImage({ caption, template }) {
  if (!caption.trim()) throw new Error('Enter a caption to create the post image.')
  if (caption.length > 6000) throw new Error(tooLong)
  if (!Object.hasOwn(headings, template)) throw new Error('Choose a post template.')
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const context = canvas.getContext('2d')
  if (!context) throw new Error('Your browser could not create the post image. You can still copy the caption.')

  context.fillStyle = paper
  context.fillRect(0, 0, size, size)
  context.fillStyle = ink
  context.textBaseline = 'top'
  context.font = `76px ${serif}`
  context.fillText(headings[template], inset, 79)
  context.fillStyle = gold
  context.fillRect(inset, 197, textWidth, 3)
  context.fillStyle = ink
  drawCaption(context, caption)
  drawSignature(context)

  const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'))
  if (!blob) throw new Error('Your browser could not save the post image. You can still copy the caption.')
  return new File([blob], `golden-plate-${template}.png`, { type: 'image/png' })
}
