export const MAP_VIEW_KEY = 'goldenplate.map-view.v1'
export const MAP_VIEW_EVENT = 'goldenplate-map-view-changed'

export function readMapView(storage) {
  try { return storage?.getItem(MAP_VIEW_KEY) === 'flat' ? 'flat' : 'globe' } catch { return 'globe' }
}

export function projectionFor(view) {
  return { name: view === 'flat' ? 'mercator' : 'globe' }
}

// Fit the shortest arc, including schools on opposite sides of the date line.
export function schoolBounds(points) {
  if (!points.length) return null
  const longitudes = points.map((point) => ((point.longitude % 360) + 360) % 360).sort((a, b) => a - b)
  let gap = -1
  let start = 0
  for (let index = 0; index < longitudes.length; index += 1) {
    const next = index === longitudes.length - 1 ? longitudes[0] + 360 : longitudes[index + 1]
    if (next - longitudes[index] > gap) { gap = next - longitudes[index]; start = (index + 1) % longitudes.length }
  }
  let west = longitudes[start]
  let east = longitudes[(start + longitudes.length - 1) % longitudes.length]
  if (east < west) east += 360
  if (west > 180) { west -= 360; east -= 360 }
  return [[west, Math.min(...points.map((point) => point.latitude))],
    [east, Math.max(...points.map((point) => point.latitude))]]
}
