import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, Maximize, Minimize, Settings2 } from 'lucide-react'
import { Button } from '@/components/ui/button.jsx'
import { Dialog, DialogContent } from '@/components/ui/dialog.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.jsx'
import LiveCounterSettings from '@/components/LiveCounterSettings.jsx'
import CounterCelebration from '@/components/CounterCelebration.jsx'
import LiveCounterProgress from '@/components/LiveCounterProgress.jsx'
import useAnimatedCounter from '@/hooks/useAnimatedCounter.js'
import useLiveCounter from '@/hooks/useLiveCounter.js'
import useCounterFullscreen from '@/hooks/useCounterFullscreen.js'
import { formatCounterDate, orderedCounterRanges, rangeLabel } from '@/lib/live-counter.js'

export default function LiveCounterPage() {
  const { user, setUser, checkingAccess, snapshot, error, setError, connected, refresh, switchSchool } = useLiveCounter()
  const [schoolCode, setSchoolCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [selectedRange, setSelectedRange] = useState(null)
  const [selectedMetric, setSelectedMetric] = useState(null)
  const { root, enterButton, exitButton, fullscreen, exitVisible, enter, exit } = useCounterFullscreen()
  const [editing, setEditing] = useState(false)
  const [saved, setSaved] = useState(false)
  const [celebration, setCelebration] = useState(null)
  const availableRanges = orderedCounterRanges(snapshot?.ranges || [], snapshot?.settings.default_range)
  const activeRange = availableRanges.some((range) => range.id === selectedRange)
    ? selectedRange : snapshot?.settings.default_range || 'year'
  const currentRange = availableRanges.find((range) => range.id === activeRange)
  const defaultMetric = snapshot?.settings.default_metric || 'count'
  const metric = selectedMetric || defaultMetric
  const metrics = defaultMetric === 'percentage' ? ['percentage', 'count'] : ['count', 'percentage']
  const milestone = (metric === 'percentage' ? snapshot?.settings.percentage_milestone : snapshot?.settings.milestone) ?? null
  const counterKey = snapshot ? `${snapshot.school.code}:${activeRange}:${metric}` : 'loading'
  const celebrate = useCallback((goal) => setCelebration({ milestone: goal, counterKey, startedAt: Date.now() }), [counterKey])
  const celebratePercentage = useCallback((goal) => celebrate(goal / 10), [celebrate])
  const displayedCount = useAnimatedCounter({ target: currentRange?.clean_count || 0,
    milestone: metric === 'count' ? milestone : null, resetKey: counterKey, onMilestone: celebrate })
  const displayedTotal = useAnimatedCounter({ target: currentRange?.total_records || 0, resetKey: counterKey })
  const displayedPercentage = useAnimatedCounter({ target: Math.round((currentRange?.clean_percentage || 0) * 10),
    milestone: metric === 'percentage' && milestone ? Math.round(milestone * 10) : null,
    resetKey: counterKey, onMilestone: celebratePercentage }) / 10
  useEffect(() => {
    if (!celebration) return
    const timer = setTimeout(() => setCelebration(null), 6500)
    return () => clearTimeout(timer)
  }, [celebration])

  const guestAccess = async (event) => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const response = await fetch('/api/auth/guest', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ school_slug: schoolCode.trim() }),
      })
      const data = await response.json()
      if (!response.ok) { setError(data.error || 'Unable to find this school.'); return }
      setSelectedRange(null)
      setSelectedMetric(null)
      setUser(data.user)
    } catch { setError('Unable to connect. Please try again.') }
    finally { setBusy(false) }
  }

  return <div ref={root} tabIndex={-1} className={fullscreen ? 'fixed inset-0 z-40 h-dvh overflow-y-auto bg-emerald-950 text-white outline-none' : 'min-h-screen bg-[#f8faf7] text-slate-900'}>
    {fullscreen && currentRange ? <main>
      <Button ref={exitButton} variant="ghost" data-edge-visible={exitVisible}
        className={`counter-fullscreen-exit fixed right-4 top-4 z-10 bg-white/10 text-white hover:bg-white/20 hover:text-white ${exitVisible ? 'opacity-100' : 'pointer-events-none opacity-0'}`}
        onClick={exit}>
        <Minimize className="h-4 w-4" />Exit full screen
      </Button>
      <div className="w-full">
        <LiveCounterProgress range={currentRange} displayedCount={displayedCount} displayedTotal={displayedTotal}
          displayedPercentage={displayedPercentage} milestone={milestone} metric={metric} fullscreen
          context={`${snapshot.school.name} · ${rangeLabel(currentRange)}`} />
        {!connected && <p role="status" className="absolute bottom-2 left-0 w-full bg-emerald-950/90 text-center text-sm text-amber-200">Reconnecting… Showing the last successful update.</p>}
      </div>
    </main> : <>
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-5 sm:px-8">
        <a href="/" className="text-2xl font-bold tracking-tight text-amber-600">PLATE</a>
        <Button asChild variant="ghost"><a href="/"><ArrowLeft className="h-4 w-4" />Main portal</a></Button>
      </div>
    </header>
    <main className="mx-auto max-w-6xl px-5 py-10 sm:px-8 sm:py-14">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">Every plate counts</p>
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">Live clean plates</h1>
          <p className="mt-4 text-slate-600">{snapshot?.school.name || user?.school?.name || 'See your school’s progress, one clean plate at a time.'}</p>
        </div>
        {snapshot && <div className="flex flex-wrap items-center gap-3">
          <Button ref={enterButton} variant="outline" onClick={enter}><Maximize className="h-4 w-4" />Full screen</Button>
          <span role="status" className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm ${connected
            ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>
            <span className={`h-2 w-2 rounded-full ${connected ? 'bg-emerald-500' : 'bg-amber-500'}`} />
            {connected ? 'Live · updates every 5 seconds' : 'Reconnecting…'}
          </span>
          {snapshot.can_manage_ranges && <Button variant="outline" onClick={() => { setSaved(false); setEditing(true) }}>
            <Settings2 className="h-4 w-4" />Manage time ranges
          </Button>}
        </div>}
      </div>
      {error && <p role="alert" className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        {error}{snapshot && ' Showing the last successful update. Retrying automatically.'}
      </p>}
      {checkingAccess ? <p className="mt-10 text-slate-500">Checking school access…</p>
        : user?.role === 'inter_school' ? <p className="mt-10 text-slate-600">Sign in with a school account to view the live counter.</p>
          : !user ? <section className="mt-10 max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
            <h2 className="text-xl font-semibold">Choose your school</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-500">Enter a school code to view live totals as a guest.</p>
            <form onSubmit={guestAccess} className="mt-6 space-y-4">
              <div className="space-y-2"><Label htmlFor="live-school-code">School code</Label>
                <Input id="live-school-code" required maxLength={100} placeholder="e.g. SAC" autoComplete="off"
                  value={schoolCode} disabled={busy} onChange={(event) => setSchoolCode(event.target.value)} /></div>
              <Button type="submit" disabled={busy} className="w-full bg-emerald-700 hover:bg-emerald-800">
                {busy ? 'Finding school…' : 'View live counter'}
              </Button>
            </form>
            <a href="/login" className="mt-5 inline-block text-sm font-medium text-emerald-700 underline underline-offset-4">Sign in to manage time ranges</a>
          </section> : !snapshot ? <p className="mt-10 text-slate-500">Loading live totals…</p> : <>
            <div className="mt-10 flex flex-wrap items-center justify-between gap-3 text-sm text-slate-500">
              <p>Students + faculty · {snapshot.public_sessions_only ? 'Public sessions' : 'All recorded sessions'}</p>
              {snapshot.public_sessions_only && <Button variant="ghost" size="sm" onClick={async () => {
                if (await switchSchool()) { setSelectedRange(null); setSelectedMetric(null) }
              }}>Change school</Button>}
            </div>
            {saved && <p role="status" className="mt-3 text-sm text-emerald-700">Time ranges saved.</p>}
            <Tabs value={metric} onValueChange={setSelectedMetric} className="mt-5">
              <TabsList aria-label="Main view">
                {metrics.map((value) => <TabsTrigger key={value} value={value}>{value === 'count' ? 'Count' : 'Percentage'}</TabsTrigger>)}
              </TabsList>
              <TabsContent value={metric}>
                <Tabs value={activeRange} onValueChange={setSelectedRange} className="mt-4 gap-6">
                  <TabsList aria-label="Time range" className="h-auto w-full max-w-full flex-nowrap justify-start gap-1 overflow-x-auto bg-slate-100 p-1.5">
                    {availableRanges.map((range) => <TabsTrigger key={range.id} value={range.id}
                      className="h-auto min-h-10 min-w-max whitespace-nowrap px-4 py-2">
                      {rangeLabel(range)}
                    </TabsTrigger>)}
                  </TabsList>
                  {availableRanges.map((range) => <TabsContent key={range.id} value={range.id} className="space-y-6">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <h2 className="text-lg font-semibold text-slate-700">{rangeLabel(range)}</h2>
                      <p className="text-sm text-slate-500">{formatCounterDate(range.start_date)} – {formatCounterDate(range.end_date)} · {snapshot.settings.timezone}</p>
                    </div>
                    <LiveCounterProgress range={range} displayedCount={displayedCount} displayedTotal={displayedTotal}
                      displayedPercentage={displayedPercentage} milestone={milestone} metric={metric} />
                  </TabsContent>)}
                </Tabs>
              </TabsContent>
            </Tabs>
            <div className="mt-7 flex flex-wrap justify-between gap-2 text-xs leading-relaxed text-slate-500">
              <p>Both dates included. Count-only plates are included in the totals.</p>
              <p>Last updated {new Date(snapshot.updated_at).toLocaleTimeString()}</p>
            </div>
            {snapshot.can_manage_ranges && <Dialog open={editing} onOpenChange={setEditing}>
              <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl" dismissOnOverlayClick={false}>
                {editing && <LiveCounterSettings settings={snapshot.settings} canSetDefault={snapshot.can_set_default}
                  onSaved={() => { setEditing(false); setSaved(true); refresh() }} />}
              </DialogContent>
            </Dialog>}
          </>}
    </main>
    </>}
    {celebration && celebration.counterKey === counterKey && celebration.milestone === milestone && <CounterCelebration key={celebration.startedAt} milestone={celebration.milestone} metric={metric} settings={snapshot.settings} onClose={() => setCelebration(null)} />}
  </div>
}
