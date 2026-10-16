export function hasGeographicCoordinates(point) {
  return Number.isFinite(point?.latitude) && Number.isFinite(point?.longitude)
    && Math.abs(point.latitude) <= 90 && Math.abs(point.longitude) <= 180
}

export function wrapLongitude(longitude) {
  return ((longitude + 180) % 360 + 360) % 360 - 180
}

export function formatCoordinates(point) {
  if (!hasGeographicCoordinates(point)) return 'No location set yet'
  return `${Math.abs(point.latitude).toFixed(5)}° ${point.latitude < 0 ? 'S' : 'N'}, ${Math.abs(point.longitude).toFixed(5)}° ${point.longitude < 0 ? 'W' : 'E'}`
}
