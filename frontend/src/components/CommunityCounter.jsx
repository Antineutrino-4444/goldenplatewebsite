import { Maximize, Minimize } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { PlateMark } from '@/components/PublicHeader.jsx'
import SiteLink from '@/components/SiteLink.jsx'
import usePublicCounter from '@/hooks/usePublicCounter.js'
import useCounterFullscreen from '@/hooks/useCounterFullscreen.js'
import useAnimatedCounter from '@/hooks/useAnimatedCounter.js'
import { communityBarLayout, communityRulerLabels } from '@/lib/counter-animation.js'
import { observeCounterVisibility } from '@/lib/counter-visibility.js'

export default function CommunityCounter({ compact = false }) {
  const { snapshot, connected, error } = usePublicCounter()
  const { root, enterButton, exitButton, fullscreen, exitVisible, enter, exit } = useCounterFullscreen()
  const [seen, setSeen] = useState(false)
  const barElement = useRef(null)
  const [rulerWidth, setRulerWidth] = useState(320)
  const counterReady = Boolean(snapshot)
  const [tipVisible, setTipVisible] = useState(false)
  const tipTimer = useRef(null)
  useEffect(() => () => clearTimeout(tipTimer.current), [])
  const revealTip = () => {
    if (!compact) return
    clearTimeout(tipTimer.current)
    setTipVisible(true)
    tipTimer.current = setTimeout(() => setTipVisible(false), 3000)
  }
  const hideTipOnMouseLeave = (event) => {
    if (event.pointerType !== 'mouse') return
    clearTimeout(tipTimer.current)
    setTipVisible(false)
  }
  useEffect(() => {
    if (!counterReady || !barElement.current || !root.current) return
    const disconnect = observeCounterVisibility(root.current, setSeen, { enterElement: barElement.current })
    setRulerWidth(barElement.current.getBoundingClientRect().width)
    const sizing = new ResizeObserver(() => setRulerWidth(barElement.current.getBoundingClientRect().width))
    sizing.observe(barElement.current)
    return () => { disconnect(); sizing.disconnect() }
  }, [counterReady, root])
  const displayedCount = useAnimatedCounter({ target: seen ? snapshot?.clean_count || 0 : 0, milestone: null,
    resetKey: snapshot && seen ? 'community' : 'loading' })
  const bar = communityBarLayout(displayedCount)
  const ruler = communityRulerLabels(bar.ticks, rulerWidth)
  useEffect(() => {
    if (!compact) document.title = 'Community live counter · Golden Plate'
  }, [compact])
  return <div ref={root} tabIndex={-1} className={`${compact ? 'gp-mini-counter' : 'gp-community-counter'}${fullscreen ? ' gp-community-counter-fullscreen' : ''}`}>
    {!compact && !fullscreen && <div className="gp-counter-page-heading"><p className="gp-section-label">PLATE · Community live counter</p><h1>Every clean plate adds up.</h1><p>All-time clean plates recorded by students and faculty across every school. Discarded sessions are excluded.</p></div>}
    {fullscreen && <button ref={exitButton} className="gp-counter-exit" data-edge-visible={exitVisible} onClick={exit}><Minimize size={18} />Exit full screen</button>}
    <div className="gp-counter-numbers" aria-label="Community totals">
      <div><span className="gp-counter-value"><span aria-hidden="true">{snapshot ? displayedCount.toLocaleString() : '—'}</span><span className="sr-only">{snapshot ? snapshot.clean_count.toLocaleString() : 'Loading'}</span></span><span className="gp-counter-unit">clean plates</span></div>
    </div>
    {snapshot && <div ref={barElement} className="gp-community-bar" data-counter-visible={seen}>
      <div className="gp-community-bar-control" role="meter" aria-label="Clean plates on an adaptive scale"
        tabIndex={compact ? 0 : undefined} onClick={revealTip} onPointerLeave={hideTipOnMouseLeave}
        aria-valuemin={0} aria-valuemax={bar.scale} aria-valuenow={displayedCount}
        aria-valuetext={`${displayedCount.toLocaleString()} clean plates on a logarithmic scale. The scale expands as the community total grows.`}>
        <div className="gp-community-bar-track"><span className="gp-community-bar-fill" style={{ width: `${bar.width}%` }} /></div>
        {compact && <span className={`gp-community-bar-tip${tipVisible ? ' is-visible' : ''}`} aria-hidden="true"
          style={{ left: `clamp(16px, ${bar.width}%, calc(100% - 16px))` }}><PlateMark /></span>}
      </div>
      <div className="gp-community-bar-ticks" style={{ height: ruler.height }} aria-hidden="true">{ruler.ticks.map((tick) => <span key={tick.endpoint ? 'limit' : tick.value}
        data-scale-mark={tick.value} title={tick.value.toLocaleString()}
        style={{ left: `${tick.position}%` }}><span style={{ left: tick.offset }}>{tick.text}</span></span>)}</div>
      <p className="gp-community-bar-caption">Logarithmic scale · expands as the total grows</p>
    </div>}
    <p className="gp-counter-connection" role="status">{connected ? 'Live · updates every 5 seconds' : snapshot ? 'Reconnecting… Showing the last successful totals.' : error ? 'Unable to load totals. Retrying automatically…' : 'Connecting to the live counter…'}</p>
    {!fullscreen && <div className="gp-counter-controls">{compact
      ? <SiteLink className="gp-text-link" to="/live-counter/community">Open the full counter →</SiteLink>
      : <><button ref={enterButton} className="gp-button" onClick={enter} disabled={!snapshot}><Maximize size={17} />Full screen</button><SiteLink className="gp-text-link" to="/live-counter">View your school’s counter →</SiteLink></>}
    </div>}
  </div>
}
