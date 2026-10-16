import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'
import SiteLink, { originState, siteDestination } from '@/components/SiteLink.jsx'
import { isMapHost, sitePageLabel, siteReturnPath } from '@/lib/navigation.js'
import ThemeToggle from '@/components/ThemeToggle.jsx'
import './LandingPage.css'

export function PlateMark() {
  return <span className="plate-mark" aria-hidden="true"><span /><i /></span>
}

export default function PublicHeader() {
  const location = useLocation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [compact, setCompact] = useState(() => window.matchMedia('(max-width: 950px)').matches)
  const menuButton = useRef(null)
  useEffect(() => {
    const media = window.matchMedia('(max-width: 950px)')
    const resize = () => { setCompact(media.matches); if (!media.matches) setOpen(false) }
    media.addEventListener('change', resize)
    return () => media.removeEventListener('change', resize)
  }, [])
  useEffect(() => {
    if (!open) return
    const onEscape = (event) => {
      if (event.key === 'Escape') { setOpen(false); menuButton.current?.focus() }
    }
    window.addEventListener('keydown', onEscape)
    return () => window.removeEventListener('keydown', onEscape)
  }, [open])
  const close = () => setOpen(false)
  const from = siteReturnPath(location.state?.returnTo)
  const returnTo = from === location.pathname + location.search + location.hash ? '/' : from
  const navState = originState(location)
  const returnToSource = (event) => {
    close()
    if (location.state?.returnKey && window.history.state?.idx > 0
      && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
      event.preventDefault()
      navigate(-1)
    }
  }
  return <header className="public-header">
    <a className="public-skip" href="#main-content">Skip to content</a>
    <div className="public-header-inner">
      <SiteLink className="public-brand" to="/" onClick={close}><PlateMark /><span>golden plate<span className="brand-caption">Student-led food waste prevention</span></span></SiteLink>
      <div className="public-header-actions"><ThemeToggle /><button ref={menuButton} className="public-menu-toggle" aria-label={open ? 'Close navigation' : 'Open navigation'} aria-expanded={open} aria-controls="public-navigation" onClick={() => setOpen(!open)}><span className="public-menu-icon" aria-hidden="true"><span /><span /><span /></span></button></div>
      <nav id="public-navigation" className={open ? 'public-nav is-open' : 'public-nav'} aria-label="Main navigation" inert={compact && !open ? true : undefined}>
        <NavLink to={siteDestination('/about')} state={navState} onClick={close}>Our story</NavLink>
        <NavLink to={siteDestination('/how-it-works')} state={navState} onClick={close}>How it works</NavLink>
        <NavLink to={siteDestination('/getting-started')} state={navState} onClick={close}>Get started</NavLink>
        <NavLink to={siteDestination('/stories')} state={navState} onClick={close}>Watch & listen</NavLink>
        <NavLink to={siteDestination('/map')} state={navState} onClick={close}>School map</NavLink>
        <NavLink to={siteDestination('/live-counter/community')} state={navState} onClick={close}>Live counter</NavLink>
        <NavLink className="public-login-link" to={siteDestination('/login')} state={navState} onClick={close}>Log in <ArrowUpRight size={15} /></NavLink>
        <SiteLink className="gp-button gp-button-small" to="/register" onClick={close}>Register a school <ArrowUpRight size={15} /></SiteLink>
      </nav>
    </div>
    {(location.pathname !== '/' || isMapHost(window.location.hostname)) && <div className="public-return-row"><Link to={siteDestination(returnTo)} state={{ restoreKey: location.state?.returnKey }} onClick={returnToSource}>← Back to {sitePageLabel(returnTo)}</Link></div>}
  </header>
}
