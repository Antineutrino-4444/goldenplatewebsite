import { useEffect, useState } from 'react'

const livePath = '/api/resources/presentations/live'

async function readLinks(schoolCode, theme, signal) {
  const search = schoolCode ? '?' + new URLSearchParams({ school_code: schoolCode, theme }) : ''
  const response = await fetch(livePath + search, { credentials: 'same-origin', cache: 'no-store', signal })
  if (!response.ok) throw new Error('Couldn’t check live presentation links.')
  return response.json()
}

export function useLiveAssembly(schoolCode, theme, provider) {
  const [providers, setProviders] = useState(null)
  const [records, setRecords] = useState(null)
  const [revision, setRevision] = useState(0)
  const [unavailable, setUnavailable] = useState(false)
  const code = schoolCode.trim()
  const enabled = Boolean(providers?.[provider])
  const initialized = providers !== null

  useEffect(() => {
    const request = new AbortController()
    readLinks('', null, request.signal).then(data => {
      if (!request.signal.aborted) {
        setProviders(data.providers || {})
        setUnavailable(false)
      }
    }).catch(() => {
      if (!request.signal.aborted) {
        setProviders({})
        setUnavailable(true)
      }
    })
    return () => request.abort()
  }, [revision])

  useEffect(() => {
    if (!initialized || !code) return
    const request = new AbortController()
    let timer
    async function check() {
      try {
        const data = await readLinks(code, theme, request.signal)
        if (request.signal.aborted) return
        const link = data.links?.[provider]
        setRecords({ code, theme, provider, revision, link, connections: data.connections || [], schoolName: data.school_name })
        timer = setTimeout(check, 10000)
      } catch {
        // Connect checks the signed-in account's current link again when used.
        if (!request.signal.aborted) setRecords({ code, theme, provider, revision, link: null, failed: true })
      }
    }
    timer = setTimeout(check, 250)
    return () => { request.abort(); clearTimeout(timer) }
  }, [code, theme, initialized, enabled, provider, revision])

  const current = records?.code === code && records.theme === theme && records.provider === provider
  return {
    enabled, loading: !providers || Boolean(provider && code && !current),
    unavailable: unavailable || Boolean(current && records.failed),
    link: current ? records.link : null,
    connections: current ? records.connections || [] : [],
    providers: providers || {},
    schoolName: current ? records.schoolName : '',
    refresh: () => setRevision(previous => previous + 1),
  }
}
