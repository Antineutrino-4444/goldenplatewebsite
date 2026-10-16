import { useEffect, useState } from 'react'
import Link from '@/components/SiteLink.jsx'
import { parsePodcastTranscript, PODCAST_TRANSCRIPT_URL } from '@/lib/podcast-transcript.js'
import { PublicFooter } from '@/components/LandingPage.jsx'
import { useLocation } from 'react-router-dom'
import './LandingPage.css'

const episode = 'https://open.spotify.com/episode/0e3Fu2pkadTsyrRyeFraXe'

export default function PodcastTranscriptPage() {
  const { hash } = useLocation()
  const [turns, setTurns] = useState(null)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    document.title = 'The Golden Plate · Podcast transcript'
    const controller = new AbortController()
    let active = true
    setFailed(false)
    const timeout = setTimeout(() => controller.abort(), 10000)
    fetch(PODCAST_TRANSCRIPT_URL, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error('Transcript unavailable')
        const parsed = parsePodcastTranscript(await response.text())
        if (!parsed.length) throw new Error('Transcript unavailable')
        if (active) setTurns(parsed)
      })
      .catch(() => { if (active) setFailed(true) })
      .finally(() => clearTimeout(timeout))
    return () => { active = false; controller.abort(); clearTimeout(timeout) }
  }, [attempt])
  useEffect(() => {
    if (turns && /^#podcast-\d{2}-\d{2}$/.test(hash)) document.getElementById(hash.slice(1))?.scrollIntoView()
  }, [turns, hash])
  return <div className="golden-public"><main id="main-content" className="gp-container gp-transcript-page">
    <header className="gp-transcript-intro">
      <p className="gp-section-label">Spoiler Alert · Second Harvest National Youth Council</p>
      <h1>The Golden Plate.<br />The conversation.</h1>
      <p>Jiajun (Leo) Li, Shuoyou (Nick) Wang, and Michael Casey discuss food waste, student leadership, and the website they helped build at St. Andrew’s College.</p>
      <p className="gp-transcript-note">Edited from an Otter.ai transcript for readability. Timestamps are approximate. The edited text has not been independently checked against the recording.</p>
      <div className="gp-platform-links"><a className="gp-text-link" href={episode} target="_blank" rel="noopener noreferrer">Listen on Spotify ↗</a><a className="gp-text-link" href={PODCAST_TRANSCRIPT_URL} download>Download the text transcript</a><Link className="gp-text-link" to="/stories">Watch & listen</Link></div>
    </header>
    <nav className="gp-transcript-chapters" aria-label="Transcript topics"><a href="#podcast-06-41">Student leadership · 06:41</a><a href="#podcast-09-36">Building the website · 09:36</a><a href="#podcast-18-02">Starting at your school · 18:02</a><a href="#podcast-22-44">Website efficiency · 22:44</a></nav>
    {failed ? <div role="alert" className="gp-session-state"><p>The transcript could not be loaded.</p><button className="gp-text-link" onClick={() => setAttempt((value) => value + 1)}>Try again</button></div>
      : !turns ? <p role="status">Loading the transcript…</p>
        : <div className="gp-transcript-turns">{turns.map((turn) => <section id={turn.id} key={turn.id} aria-labelledby={`${turn.id}-speaker`}>
          <h2 id={`${turn.id}-speaker`}><a href={`#${turn.id}`}>{turn.time}</a><span>{turn.speaker}</span></h2>
          <div>{turn.paragraphs.map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div>
        </section>)}</div>}
  </main><PublicFooter /></div>
}
