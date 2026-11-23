// Capture on the original hit target so a tap on a school pin still clicks it.
export function connectGlobeDragging(svg, pan) {
  let pointer = null
  let suppressClick = false

  function start(event) {
    if (pointer || !event.isPrimary || event.button !== 0) return
    suppressClick = false
    pointer = { id: event.pointerId, x: event.clientX, y: event.clientY, target: event.target }
    event.target.setPointerCapture(event.pointerId)
  }

  function move(event) {
    if (pointer?.id !== event.pointerId) return
    const dx = event.clientX - pointer.x
    const dy = event.clientY - pointer.y
    if (!suppressClick && Math.hypot(dx, dy) < 5) return
    suppressClick = true
    svg.dataset.dragging = 'true'
    pointer.x = event.clientX
    pointer.y = event.clientY
    if (dx || dy) pan(dx, dy)
  }

  function end(event) {
    if (pointer?.id !== event.pointerId) return
    if (event.type === 'pointerup') move(event)
    pointer = null
    delete svg.dataset.dragging
  }

  function checkClick(event) {
    if (suppressClick && event.detail > 0) {
      event.stopPropagation()
      event.preventDefault()
      suppressClick = false
    }
  }

  svg.addEventListener('pointerdown', start)
  svg.addEventListener('pointermove', move)
  svg.addEventListener('pointerup', end)
  svg.addEventListener('pointercancel', end)
  svg.addEventListener('lostpointercapture', end)
  svg.addEventListener('click', checkClick, true)
  return () => {
    svg.removeEventListener('pointerdown', start)
    svg.removeEventListener('pointermove', move)
    svg.removeEventListener('pointerup', end)
    svg.removeEventListener('pointercancel', end)
    svg.removeEventListener('lostpointercapture', end)
    svg.removeEventListener('click', checkClick, true)
    if (pointer?.target.hasPointerCapture(pointer.id)) pointer.target.releasePointerCapture(pointer.id)
    delete svg.dataset.dragging
  }
}
