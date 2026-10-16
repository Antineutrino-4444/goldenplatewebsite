import { Link, useLocation } from 'react-router-dom'
import { isMapHost } from '@/lib/navigation.js'

export function siteDestination(path) {
  if (isMapHost(window.location.hostname) && path.startsWith('/') && !path.startsWith('//')) {
    const url = new URL(path, window.location.href)
    url.hostname = url.hostname.slice(4)
    return url.href
  }
  return path
}

export function originState(location) {
  return { returnTo: location.pathname + location.search + location.hash, returnKey: location.key }
}

export default function SiteLink({ state, to, ...props }) {
  const location = useLocation()
  return <Link {...props} to={typeof to === 'string' ? siteDestination(to) : to} state={{ ...originState(location), ...state }} />
}
