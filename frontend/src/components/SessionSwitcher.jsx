import { Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog.jsx'

export default function SessionSwitcher({ app }) {
  const { sessions, sessionId, showSessionsDialog, setShowSessionsDialog, switchSession,
    canManageDraw, mergeActionLoading, unmergeSession, openMergeDialog,
    setSessionToDelete, setShowDeleteConfirm } = app

  return (
    <Dialog open={showSessionsDialog} onOpenChange={setShowSessionsDialog}>
      <DialogContent className="flex max-h-[85dvh] flex-col overflow-y-hidden sm:max-w-2xl" dismissOnOverlayClick={false}>
        <DialogHeader className="shrink-0">
          <DialogTitle>Switch Session</DialogTitle>
          <DialogDescription>Select a session to switch to or manage its records. Discarded sessions are excluded from live totals.</DialogDescription>
        </DialogHeader>
        <div className="min-h-0 space-y-2 overflow-x-hidden overflow-y-auto p-1">
          {sessions.map((session) => {
            const main = sessions.find((item) => item.session_id === session.main_session_id)
            const hasExtras = !session.main_session_id && sessions.some((item) => item.main_session_id === session.session_id)
            const current = session.session_id === sessionId
            return (
              <div key={session.session_id} className={`grid min-w-0 gap-2 rounded-lg border p-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center ${current ? 'border-amber-200 bg-amber-50/50' : 'border-slate-200'}`}>
                <Button variant="ghost" onClick={() => switchSession(session.session_id)} disabled={current}
                  className="h-auto min-w-0 items-start justify-start whitespace-normal px-2 py-2 text-left disabled:opacity-100">
                  <div className="min-w-0 w-full space-y-2">
                    <div className="font-medium leading-snug [overflow-wrap:anywhere]">{session.session_name}</div>
                    <div className="text-xs text-slate-500">Owner: {session.owner || 'Unknown account'}</div>
                    {(current || session.is_discarded || session.main_session_id || hasExtras) && <div className="flex flex-wrap gap-1">
                      {current && <Badge variant="outline" className="text-amber-700">Current</Badge>}
                      {session.is_discarded && <Badge variant="destructive">Discarded</Badge>}
                      {session.main_session_id && <Badge variant="secondary" className="text-left">Extra{main ? ` of ${main.session_name}` : ''}</Badge>}
                      {hasExtras && <Badge variant="outline">Main</Badge>}
                    </div>}
                    <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs leading-relaxed text-slate-500 sm:text-sm">
                      {session.total_records > 0 ? <>
                        <span>🥇 {session.clean_count} ({session.clean_percentage}% incl. faculty)</span>
                        <span>🍽️ {session.dirty_count} ({session.dirty_percentage}%)</span>
                        <span>🧑‍🏫 {session.faculty_clean_count ?? 0}</span>
                      </> : <span>No records yet</span>}
                    </div>
                  </div>
                </Button>
                <div className="flex shrink-0 items-center justify-end gap-1">
                  {canManageDraw && <Button variant="ghost" size="sm"
                    onClick={() => session.main_session_id ? unmergeSession(session.session_id) : openMergeDialog(session)}
                    disabled={mergeActionLoading || (!session.main_session_id && hasExtras)}
                    className="text-blue-600 hover:bg-blue-50 hover:text-blue-700"
                    title={session.main_session_id ? 'Unmerge from main session' : hasExtras ? 'Remove extras before merging' : 'Merge into another session'}>
                    {session.main_session_id ? 'Unmerge' : 'Merge'}
                  </Button>}
                  {sessionId && <Button variant="ghost" size="icon" onClick={() => {
                    setSessionToDelete(session)
                    setShowDeleteConfirm(true)
                  }} disabled={session.delete_requested} className="text-red-600 hover:bg-red-50 hover:text-red-700"
                    aria-label={`Delete ${session.session_name}`} title={session.delete_requested ? 'Delete request pending' : 'Delete session'}>
                    <Trash2 className="h-4 w-4" />
                  </Button>}
                </div>
              </div>
            )
          })}
        </div>
        <Button onClick={() => setShowSessionsDialog(false)} className="w-full shrink-0">Close</Button>
      </DialogContent>
    </Dialog>
  )
}
