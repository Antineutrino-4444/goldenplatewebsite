import { useId, useRef, useState } from 'react'
import Link from '@/components/SiteLink.jsx'
import { VIDEO_GUIDES, SCHOOL_GUIDE_PLAYLIST_URL, filterGuides, guideEmbedUrl, guideWatchUrl } from '@/lib/video-guides.js'
import './VideoHelp.css'

function GuidePlayer({ guide, onClose }) {
  return <div className="gp-guide-player">
    <div className="gp-guide-player-heading"><strong>{guide.title}</strong><button type="button" onClick={onClose}>Close video</button></div>
    <iframe src={guideEmbedUrl(guide)} title={`${guide.title} — Golden Plate School Guide`} allow="autoplay; encrypted-media; picture-in-picture; fullscreen" referrerPolicy="strict-origin-when-cross-origin" allowFullScreen />
    <p>Video not playing? <a href={guideWatchUrl(guide)} target="_blank" rel="noopener noreferrer">Watch this guide on YouTube ↗</a></p>
  </div>
}

function GuideList({ guides }) {
  const [selected, setSelected] = useState(null)
  const playButton = useRef(null)
  const playerId = useId()
  return <ul className="gp-guide-video-list">{guides.map((guide) => <li key={guide.number}>
      <div className="gp-guide-video-row"><button type="button" aria-label={`Play ${guide.title} (${guide.duration})`} aria-pressed={selected?.number === guide.number} aria-controls={`${playerId}-${guide.number}`} onClick={(event) => { playButton.current = event.currentTarget; setSelected(guide) }}>
        <span className="gp-guide-video-number">{String(guide.number).padStart(2, '0')}</span><span>{guide.title}</span><span className="gp-guide-video-duration">{guide.duration} <span aria-hidden="true">▷</span></span>
      </button>
      <a className="gp-guide-youtube-link" href={guideWatchUrl(guide)} target="_blank" rel="noopener noreferrer" aria-label={`Watch ${guide.title} on YouTube (opens a new tab)`}>YouTube ↗</a></div>
      <div id={`${playerId}-${guide.number}`}>{selected?.number === guide.number && <GuidePlayer key={selected.id} guide={selected} onClose={() => { setSelected(null); playButton.current?.focus({ preventScroll: true }) }} />}</div>
    </li>)}</ul>
}

export default function VideoHelp({ videos, label = 'Watch a video guide' }) {
  const [open, setOpen] = useState(false)
  const guides = videos.map((number) => VIDEO_GUIDES.find((guide) => guide.number === number)).filter(Boolean)
  return <details className="gp-video-help" onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary>{label}<span className="gp-video-help-count">{guides.length === 1 ? guides[0].duration : `${guides.length} videos`}</span></summary>
    {open && <div className="gp-video-help-body"><GuideList guides={guides} /><Link className="gp-guide-all-videos" to="/getting-started#video-library">Browse all 32 video guides →</Link></div>}
  </details>
}

export function VideoLibrary() {
  const [query, setQuery] = useState('')
  const [group, setGroup] = useState('')
  const searchId = useId()
  const groupId = useId()
  const guides = filterGuides(VIDEO_GUIDES, query, group)
  return <section id="video-library" className="gp-video-library" aria-labelledby="video-library-title">
    <h2 id="video-library-title">The school video guide</h2>
    <p>32 short videos, from your first login to the everyday lunch routine. Choose a topic to watch here, or <a href={SCHOOL_GUIDE_PLAYLIST_URL} target="_blank" rel="noopener noreferrer">open the full playlist on YouTube ↗</a>.</p>
    <div className="gp-video-library-filters">
      <div><label htmlFor={searchId}>Find a video</label><input id={searchId} type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Try rosters, draws, or maps" /></div>
      <div><label htmlFor={groupId}>Topic</label><select id={groupId} value={group} onChange={(event) => setGroup(event.target.value)}><option value="">All topics</option>{[...new Set(VIDEO_GUIDES.map((guide) => guide.group))].map((topic) => <option key={topic}>{topic}</option>)}</select></div>
    </div>
    <p className="gp-video-library-count" role="status">{guides.length} {guides.length === 1 ? 'video' : 'videos'}{query || group ? ' found' : ' in playlist'}</p>
    {guides.length ? <GuideList key={`${query}:${group}`} guides={guides} /> : <p>No videos match. Try another search or <button className="gp-guide-reset" type="button" onClick={() => { setQuery(''); setGroup('') }}>show all videos</button>.</p>}
  </section>
}
