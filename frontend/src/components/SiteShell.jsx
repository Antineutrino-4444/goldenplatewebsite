import { useEffect, useLayoutEffect, useRef } from 'react'
import { useLocation, useNavigationType } from 'react-router-dom'
import PublicHeader from '@/components/PublicHeader.jsx'

const scrollPositions = new Map()

export function RouteContent({ children }) {
  const location = useLocation()
  const navigation = useNavigationType()
  const root = useRef(null)
  const previousPath = useRef(null)
  useLayoutEffect(() => {
    const changedPage = previousPath.current !== location.pathname
    previousPath.current = location.pathname
    const privatePage = location.pathname.startsWith('/portal') || location.pathname === '/interschool'
    if (privatePage) return
    const restoreKey = location.state?.restoreKey || (navigation === 'POP' ? location.key : null)
    const top = scrollPositions.get(restoreKey) || 0
    window.scrollTo({ top, behavior: 'instant' })
    if (location.hash) {
      try { document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView() } catch { /* Ignore malformed fragments. */ }
    }
    const remember = () => scrollPositions.set(location.key, window.scrollY)
    window.addEventListener('scroll', remember, { passive: true })
    if (changedPage && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      const animation = root.current?.animate?.([{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 220, easing: 'ease-out' })
      return () => { window.removeEventListener('scroll', remember); animation?.cancel() }
    }
    return () => window.removeEventListener('scroll', remember)
  }, [location.key, location.pathname, location.hash, location.state?.restoreKey, navigation])
  return <div ref={root} className="site-route">{children}</div>
}

export default function SiteShell({ children }) {
  const { pathname } = useLocation()
  useEffect(() => {
    const previous = window.history.scrollRestoration
    window.history.scrollRestoration = 'manual'
    return () => { window.history.scrollRestoration = previous }
  }, [])
  const privatePage = pathname.startsWith('/portal') || pathname === '/interschool'
  return <div className="site-shell">{!privatePage && <PublicHeader />}{children}</div>
}
