import { useEffect, useMemo, useRef, useState } from 'react'
import { Instagram } from 'lucide-react'
import { makeSchoolPost, postPlatforms, postTemplates, schoolPostDestination } from '@/lib/school-posts.js'
import { createSchoolPostImage } from '@/lib/school-post-image.js'
import './SocialPostTemplates.css'

const reel = 'https://www.instagram.com/reel/DBgb3-MRESr/'
const fieldInfo = {
  school: { label: 'School name', placeholder: 'Your school' },
  winner: { label: 'Winner', placeholder: 'Name or team' },
  reward: { label: 'Reward', placeholder: 'They pick lunch.' },
  date: { label: 'Lunch date', placeholder: 'Friday, May 7' },
  place: { label: 'Where to meet', placeholder: 'The dish return' },
  count: { label: 'Clean plates', placeholder: 'Enter a count' },
}

function canSharePostImage(file) {
  try {
    return typeof navigator.share === 'function' && navigator.canShare?.({ files: [file] }) === true
  } catch {
    return false
  }
}

function usePostImage(caption, template, enabled) {
  const input = useMemo(() => enabled ? { caption, template } : null, [caption, template, enabled])
  const [result, setResult] = useState(null)

  useEffect(() => {
    if (!input) return
    let active = true
    let url
    // Prepare the file while editing so Share can call the OS directly from the click.
    const timer = window.setTimeout(async () => {
      try {
        const file = await createSchoolPostImage(input)
        if (!active) return
        url = URL.createObjectURL(file)
        setResult({ input, file, url, canShare: canSharePostImage(file) })
      } catch (error) {
        if (active) setResult({ input, error: error.message || 'Couldn’t prepare this image. You can still copy the caption.' })
      }
    }, 150)
    return () => {
      active = false
      window.clearTimeout(timer)
      if (url) URL.revokeObjectURL(url)
    }
  }, [input])

  return input && result?.input === input ? result : null
}

function WinnerReel({ compact }) {
  const [playing, setPlaying] = useState(false)
  const playButton = useRef(null)
  const player = useRef(null)

  return <figure className={compact && !playing ? 'gp-post-reel gp-post-reel-compact' : 'gp-post-reel'}>
    {playing ? (
      <iframe ref={player} title="Golden Plate winners choose Friday lunch on Instagram" src={reel + 'embed/'}
        allow="autoplay; encrypted-media; fullscreen; picture-in-picture" allowFullScreen />
    ) : (
      <button type="button" className="gp-post-poster" onClick={() => {
        setPlaying(true)
        requestAnimationFrame(() => player.current?.focus({ preventScroll: true }))
      }} ref={playButton}>
        <img src="/images/initiative/golden-plate-winner.webp" alt="" width="707" height="631" loading="lazy" />
        <span><Instagram size={16} aria-hidden="true" /> Preview the reel</span>
      </button>
    )}
    <figcaption>Golden Plate winners at St. Andrew’s chose grilled cheese for Friday lunch.</figcaption>
    <div className="gp-post-reel-links">
      <a className="gp-text-link" href={reel} target="_blank" rel="noopener noreferrer">Watch on Instagram</a>
      {playing && <button type="button" className="gp-text-link" onClick={() => {
        setPlaying(false)
        requestAnimationFrame(() => playButton.current?.focus())
      }}>Close preview</button>}
    </div>
  </figure>
}

export default function SocialPostTemplates() {
  const [template, setTemplate] = useState('winner')
  const [platform, setPlatform] = useState('instagram')
  const [details, setDetails] = useState({})
  const [edits, setEdits] = useState({})
  const [feedback, setFeedback] = useState('')
  const [showPlatformLink, setShowPlatformLink] = useState(false)
  const [sharing, setSharing] = useState(false)
  const captionField = useRef(null)
  const editKey = template + '.' + platform
  const generated = makeSchoolPost(template, platform, details)
  const edited = edits[editKey]
  const caption = edited?.text ?? generated
  const site = postPlatforms[platform]
  const destination = schoolPostDestination(platform, caption)
  const invalidCount = template === 'results' && details.count?.trim() && !/^\d+$/.test(details.count.trim())
  const available = Boolean(caption.trim()) && !invalidCount
  const image = usePostImage(caption, template, !site.composer && available)

  function clearNotice() {
    setFeedback('')
    setShowPlatformLink(false)
  }

  function useGeneratedText() {
    setEdits(previous => {
      const next = { ...previous }
      delete next[editKey]
      return next
    })
    clearNotice()
  }

  async function copyCaption(openPlatform = false) {
    setShowPlatformLink(openPlatform)
    try {
      await navigator.clipboard.writeText(caption)
      setFeedback('Caption copied.')
    } catch {
      captionField.current?.focus()
      captionField.current?.select()
      setFeedback('Caption selected. Use your device’s Copy command.')
      return
    }
    // Keep the editor open. The ordinary link also works when a browser blocks pop-ups.
    if (openPlatform) window.open(destination, '_blank', 'noopener,noreferrer')
  }

  async function sharePost() {
    if (!image?.canShare || sharing) return
    clearNotice()
    setSharing(true)
    try {
      await navigator.share({ files: [image.file] })
    } catch (error) {
      if (error?.name !== 'AbortError') setFeedback('Couldn’t open the share menu. Download the post image to use it in ' + site.name + '.')
    } finally {
      setSharing(false)
    }
  }

  return <section id="instagram" className="gp-posts gp-container" aria-labelledby="school-posts-title">
    <h2 id="school-posts-title">School Post Templates</h2>
    <div className="gp-post-workspace">
      <div className="gp-post-editor">
        <div className="gp-post-fields">
          <div className="gp-post-field">
            <label htmlFor="school-post-template">Template</label>
            <select id="school-post-template" value={template} onChange={event => { setTemplate(event.target.value); clearNotice() }}>
              {Object.entries(postTemplates).map(([value, option]) => <option key={value} value={value}>{option.label}</option>)}
            </select>
          </div>
          <div className="gp-post-field">
            <label htmlFor="school-post-platform">Platform</label>
            <select id="school-post-platform" value={platform} onChange={event => { setPlatform(event.target.value); clearNotice() }}>
              {Object.entries(postPlatforms).map(([value, option]) => <option key={value} value={value}>{option.name}</option>)}
            </select>
          </div>
          {postTemplates[template].fields.map(field => <div key={field} className="gp-post-field">
            <label htmlFor={'school-post-' + field}>{fieldInfo[field].label}</label>
            <input id={'school-post-' + field} value={details[field] || ''} placeholder={fieldInfo[field].placeholder}
              inputMode={field === 'count' ? 'numeric' : undefined}
              aria-invalid={field === 'count' && invalidCount ? true : undefined}
              aria-describedby={field === 'count' && invalidCount ? 'school-post-count-error' : undefined}
              onChange={event => {
                const value = event.target.value
                setDetails(previous => ({ ...previous, [field]: value }))
                clearNotice()
              }} />
            {field === 'count' && invalidCount && <small id="school-post-count-error">Enter a whole number of plates.</small>}
          </div>)}
        </div>
        <div className="gp-post-caption">
          <label htmlFor="school-post-caption">Caption</label>
          <textarea id="school-post-caption" ref={captionField} rows={4} value={caption} onChange={event => {
            const text = event.target.value
            setEdits(previous => ({ ...previous, [editKey]: { text, source: previous[editKey]?.source ?? generated } }))
            clearNotice()
          }} />
        </div>
        {edited && <div className="gp-post-reset">
          {edited.source !== generated && <span>The template details have changed.</span>}
          <button type="button" className="gp-text-link" onClick={useGeneratedText}>Replace with template text</button>
        </div>}
      </div>
      {!site.composer && <figure className="gp-post-image">
        <figcaption>Post image preview</figcaption>
        <div className="gp-post-image-frame">
          {image?.url
            ? <img src={image.url} alt="Post image preview" />
            : <p>{image?.error || (available ? 'Preparing image…' : 'Enter a valid caption to preview the image.')}</p>}
        </div>
      </figure>}
      <div className="gp-post-publish">
        {!site.composer && image?.url && <p className="gp-post-instructions">Your caption is on the image. {image.canShare
          ? `Choose ${site.name} in your device’s share menu.`
          : `Add the downloaded image to a new ${site.name} post.`}</p>}
        <div className="gp-post-actions">
          {site.composer && (available
            ? <a className="gp-button" href={destination} target="_blank" rel="noopener noreferrer">Open draft in {site.name}</a>
            : <button type="button" className="gp-button" disabled>Open draft in {site.name}</button>)}
          {image?.canShare && <button type="button" className="gp-button" onClick={sharePost} disabled={sharing}>Share post</button>}
          {image?.url && <a className={image.canShare ? 'gp-text-link' : 'gp-button'} href={image.url} download={image.file.name}
            onClick={() => setShowPlatformLink(true)}>Download post image</a>}
          {!site.composer && <button type="button" className="gp-text-link" disabled={!available} onClick={() => copyCaption(true)}>Copy and open {site.name}</button>}
          <button type="button" className="gp-text-link" onClick={() => copyCaption()} disabled={!available}>Copy caption</button>
        </div>
        <div className="gp-post-feedback" role="status">
          {feedback}
          {showPlatformLink && <> <a href={destination} target="_blank" rel="noopener noreferrer">Open {site.name}</a></>}
        </div>
      </div>
      {template === 'winner' && <WinnerReel compact={!site.composer} />}
    </div>
  </section>
}
