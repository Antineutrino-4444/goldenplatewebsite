import { useId, useState } from 'react'
import { CheckCircle, Clock, History, ListOrdered, RefreshCcw, ShieldCheck, Trophy, Users, Wand2 } from 'lucide-react'
import { HelpTip } from '@/components/HelpTip.jsx'
import { SearchableNameInput } from '@/components/SearchableNameInput.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'

const formatTickets = (value) => Number(value ?? 0).toFixed(2)

export function DrawOptions({ label, comment, onCommentChange, onReset, resetDisabled, children }) {
  const commentId = useId()
  return (
    <details className="rounded-lg border bg-white p-4">
      <summary className="cursor-pointer text-sm font-semibold">{label} draw options</summary>
      <div className="mt-3 space-y-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor={commentId} className="text-xs text-gray-600">Action comment (optional)</Label>
          <Input id={commentId} value={comment} onChange={(event) => onCommentChange(event.target.value)}
            placeholder="Add context for this draw action" />
          <p className="text-xs text-gray-500">The note is saved in the draw history when you start, finalize, reset, or override.</p>
        </div>
        <Button onClick={onReset} variant="outline" disabled={resetDisabled}>
          <RefreshCcw className="h-4 w-4" /> Reset Draw
        </Button>
        {children}
      </div>
    </details>
  )
}

export function FacultyOverride({ candidates, disabled, onOverride }) {
  const [input, setInput] = useState('')
  const [selected, setSelected] = useState(null)
  const canSubmit = !disabled && candidates.some((candidate) => candidate.record_id === selected)

  const override = async () => {
    if (canSubmit && await onOverride(selected)) {
      setInput('')
      setSelected(null)
    }
  }

  return (
    <div className="flex w-full flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
      <div className="w-full sm:max-w-xs">
        <SearchableNameInput value={input} names={candidates} placeholder="Search faculty by name or ID"
          onChange={(value, meta) => {
            setInput(value)
            if (meta?.source !== 'selection') setSelected(null)
          }}
          onSelectName={(candidate) => setSelected(candidate.record_id)}
          onKeyPress={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              override()
            }
          }} />
      </div>
      <Button variant="outline" onClick={override} disabled={!canSubmit}>
        <ShieldCheck className="h-4 w-4" /> Override Winner
      </Button>
    </div>
  )
}

function CandidateList({ candidates, winner, selectable, selectedCandidate, onSelectCandidate }) {
  return (
    <ol className="mt-3 max-h-48 space-y-1 overflow-y-auto pr-1">
      {candidates.map((candidate, index) => {
        const selected = selectable && candidate.key === selectedCandidate?.key
        const isWinner = candidate.key
          ? candidate.key === winner?.key
          : Boolean(candidate.teacher_id && candidate.teacher_id === winner?.teacher_id)
        const row = (
          <>
            <Badge variant="outline">#{index + 1}</Badge>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium">{candidate.display_name}</span>
              <span className="text-xs text-gray-500">
                {formatTickets(candidate.tickets)} tickets • {formatTickets(candidate.probability)}% chance
              </span>
              {candidate.next_ticket_gain != null && (
                <span className="block text-xs font-medium text-emerald-700">
                  Next clean plate: +{Number(candidate.next_ticket_gain).toLocaleString()} tickets
                </span>
              )}
            </span>
            {isWinner && <Badge variant="outline">Winner</Badge>}
          </>
        )
        return (
          <li key={candidate.key ?? candidate.teacher_id ?? index}>
            {selectable ? (
              <button type="button" aria-pressed={selected} onClick={() => onSelectCandidate(candidate.key)}
                className={`flex w-full items-center gap-2 rounded-md border px-2 py-1.5 text-left ${selected ? 'border-emerald-500 bg-emerald-50' : 'hover:bg-gray-50'}`}>
                {row}
              </button>
            ) : (
              <div className="flex items-center gap-2 rounded-md border px-2 py-1.5">{row}</div>
            )}
          </li>
        )
      })}
    </ol>
  )
}

export default function DrawColumn({
  title, participantLabel, summary, winner, history, blockedReason,
  finalizeDisabled, onStart, onFinalize, selectedCandidate, onSelectCandidate, options,
}) {
  const candidates = summary?.candidates ?? []
  const topCandidates = summary?.top_candidates ?? candidates.slice(0, 3)
  const eligibleLabel = participantLabel === 'Student' ? 'Eligible Students' : 'Eligible Faculty'
  const selectable = Boolean(onSelectCandidate)

  return (
    <section aria-label={title} className={`grid min-w-0 gap-3 rounded-xl border bg-gray-50 p-4 md:grid-rows-subgrid ${options ? 'md:row-span-8' : 'md:row-span-7'}`}>
      <h3 className="text-lg font-semibold">{title}</h3>
      <dl className="grid grid-cols-3 gap-2">
        {[
          ['Tickets', formatTickets(summary?.total_tickets)],
          ['Eligible', summary?.eligible_count ?? 0],
          ['Status', winner?.finalized ? 'Finalized' : winner ? 'Pending' : 'No winner'],
        ].map(([label, value]) => (
          <div key={label} className="min-w-0 rounded-md border bg-white p-2 sm:p-3">
            <dt className="text-xs text-gray-500">{label}</dt>
            <dd className="mt-1 break-words text-sm font-semibold sm:text-base">{value}</dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={onStart} disabled={Boolean(blockedReason)} aria-label={`Start ${participantLabel} Draw`}
          className="bg-emerald-600 hover:bg-emerald-700">
          <Wand2 className="h-4 w-4" /> Start Draw
        </Button>
        <HelpTip topic={`starting the ${participantLabel.toLowerCase()} draw`}>
          {blockedReason || 'Start Draw selects a winner. Choose Finalize Winner to confirm the result.'}
        </HelpTip>
        <Button onClick={onFinalize} variant="outline" disabled={finalizeDisabled} aria-label={`Finalize ${participantLabel} Winner`}>
          <CheckCircle className="h-4 w-4" /> Finalize Winner
        </Button>
      </div>
      <div className="rounded-lg border bg-white p-4">
        <h4 className="flex items-center gap-2 text-sm font-semibold text-gray-700">
          <Trophy className="h-4 w-4" /> Current Winner
        </h4>
        {winner ? (
          <div className="mt-3 space-y-2 text-xs text-gray-500">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-lg font-semibold text-gray-900">{winner.display_name}</span>
              <Badge variant={winner.finalized ? 'default' : 'outline'}>
                {winner.finalized ? 'Finalized' : 'Awaiting Finalization'}
              </Badge>
            </div>
            {winner.student_identifier && <div>Student ID {winner.student_identifier}</div>}
            {(winner.grade || winner.house || winner.clan) && (
              <div className="flex flex-wrap gap-2">
                {winner.grade && <span>Grade {winner.grade}</span>}
                {winner.house && <span>House · {winner.house}</span>}
                {winner.clan && <span>Clan · {winner.clan}</span>}
              </div>
            )}
            {winner.selectedAt && (
              <div className="flex items-center gap-1">
                <Clock className="h-3 w-3" /> Selected {new Date(winner.selectedAt).toLocaleString()}
              </div>
            )}
            {winner.tickets != null && (
              <div>{formatTickets(winner.tickets)} tickets at selection • {formatTickets(winner.probability)}% chance</div>
            )}
            <div>{winner.overridden ? 'Manual override' : 'Random draw'}</div>
          </div>
        ) : (
          <p className="mt-3 text-sm text-gray-500">No winner selected yet.</p>
        )}
      </div>
      <div className="rounded-lg border bg-white p-4">
        <h4 className="flex items-center gap-2 text-sm font-semibold text-gray-700">
          <ListOrdered className="h-4 w-4" /> Top 3 Candidates
        </h4>
        {topCandidates.length ? (
          <CandidateList candidates={topCandidates} winner={winner} selectable={selectable}
            selectedCandidate={selectedCandidate} onSelectCandidate={onSelectCandidate} />
        ) : <p className="mt-3 text-sm text-gray-500">No eligible candidates yet.</p>}
      </div>
      <div className="rounded-lg border bg-white p-4">
        <h4 className="flex items-center gap-2 text-sm font-semibold text-gray-700">
          <Users className="h-4 w-4" /> {eligibleLabel}
        </h4>
        {candidates.length ? (
          <CandidateList candidates={candidates} winner={winner} selectable={selectable}
            selectedCandidate={selectedCandidate} onSelectCandidate={onSelectCandidate} />
        ) : <p className="mt-3 text-sm text-gray-500">No eligible candidates yet.</p>}
        {selectedCandidate && (
          <div className="mt-3 rounded-md bg-gray-50 p-3 text-sm">
            <div className="font-medium">{selectedCandidate.display_name}</div>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-600">
              {selectedCandidate.student_identifier && <span>Student ID {selectedCandidate.student_identifier}</span>}
              {selectedCandidate.grade && <span>Grade {selectedCandidate.grade}</span>}
              {selectedCandidate.advisor && <span>Advisor · {selectedCandidate.advisor}</span>}
              {selectedCandidate.house && <span>House · {selectedCandidate.house}</span>}
              {selectedCandidate.clan && <span>Clan · {selectedCandidate.clan}</span>}
            </div>
          </div>
        )}
      </div>
      <div className="rounded-lg border bg-white p-4">
        <h4 className="flex items-center gap-2 text-sm font-semibold text-gray-700">
          <History className="h-4 w-4" /> Draw History
        </h4>
        {history.length ? (
          <ol className="mt-3 max-h-48 space-y-2 overflow-y-auto pr-1 text-xs text-gray-600">
            {history.slice().reverse().map((entry, index) => (
              <li key={`${entry.timestamp}-${index}`} className="rounded border p-2">
                <div className="font-semibold uppercase">{entry.event_type.replace(/^faculty_/, '').replace(/_/g, ' ')}</div>
                {entry.timestamp && <div>{new Date(entry.timestamp).toLocaleString()}</div>}
                {(entry.faculty_name || entry.student_name) && <div>{entry.faculty_name || entry.student_name}</div>}
                {entry.tickets != null && <div>{formatTickets(entry.tickets)} tickets</div>}
                {entry.probability != null && <div>{formatTickets(entry.probability)}% chance</div>}
                {entry.pool_size != null && <div>Eligible pool · {entry.pool_size}</div>}
                {entry.created_by && <div>By {entry.created_by}</div>}
                {entry.comment && <div className="text-gray-700">{entry.comment}</div>}
              </li>
            ))}
          </ol>
        ) : (
          <p className="mt-3 text-sm text-gray-500">No draw activity recorded yet.</p>
        )}
      </div>
      {options}
    </section>
  )
}
