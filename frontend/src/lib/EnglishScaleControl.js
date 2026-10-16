// Keep the scale in English independently of the basemap's label language.
export default class EnglishScaleControl {
  constructor({ maxWidth = 100 } = {}) {
    this.maxWidth = maxWidth
    this.format = new Intl.NumberFormat('en', { maximumFractionDigits: 3 })
    this.update = this.update.bind(this)
  }

  onAdd(map) {
    this.map = map
    this.container = document.createElement('div')
    this.container.className = 'mapboxgl-ctrl mapboxgl-ctrl-scale'
    this.container.lang = 'en'
    map.on('render', this.update)
    this.update()
    return this.container
  }

  update() {
    const canvas = this.map.getCanvas()
    const x = canvas.clientWidth / 2
    const y = canvas.clientHeight / 2
    const width = Math.min(this.maxWidth, canvas.clientWidth)
    if (!width || !canvas.clientHeight) return
    const meters = this.map.unproject([x - width / 2, y])
      .distanceTo(this.map.unproject([x + width / 2, y]))
    if (!Number.isFinite(meters) || meters <= 0) return
    const magnitude = 10 ** Math.floor(Math.log10(meters))
    const step = [5, 3, 2, 1].find((value) => value <= meters / magnitude)
    const distance = step * magnitude
    const label = distance >= 1000
      ? `${this.format.format(distance / 1000)} km`
      : `${this.format.format(distance)} m`
    const pixelWidth = `${(width * distance / meters).toFixed(2)}px`
    if (this.container.textContent !== label) {
      this.container.textContent = label
      this.container.title = `Map scale: ${label}`
    }
    if (this.container.style.width !== pixelWidth) this.container.style.width = pixelWidth
  }

  onRemove() {
    this.map.off('render', this.update)
    this.container.remove()
    this.map = null
  }
}
