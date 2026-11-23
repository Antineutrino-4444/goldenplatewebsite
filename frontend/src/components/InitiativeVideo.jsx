import { useEffect, useRef, useState } from 'react'
import { Play } from 'lucide-react'

export const introductionUrl = 'https://www.youtube.com/watch?v=vQN0X-7xXVo'

export default function InitiativeVideo() {
  const [playing, setPlaying] = useState(false)
  const player = useRef(null)
  useEffect(() => {
    if (playing) player.current?.focus({ preventScroll: true })
  }, [playing])
  return <div className="gp-video-player">
    {playing ? <iframe
      ref={player}
      src="https://www.youtube-nocookie.com/embed/vQN0X-7xXVo?autoplay=1"
      title="Golden Plate introduction video"
      allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
      referrerPolicy="strict-origin-when-cross-origin"
      allowFullScreen
    /> : <button type="button" onClick={() => setPlaying(true)} aria-label="Play the Golden Plate introduction">
      <img src="/images/initiative/golden-plate-team.webp" alt="" loading="lazy" width="1123" height="702" />
      <span className="gp-video-play"><Play size={19} fill="currentColor" aria-hidden="true" />Play the introduction</span>
    </button>}
  </div>
}
