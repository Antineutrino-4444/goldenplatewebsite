import { Badge } from '@/components/ui/badge.jsx'

// Shared by the school dashboard, public preview, and read-only guest page.
export default function SessionMetrics({ sessionName, sessionOwner, sessionDashboardStats, isSessionDiscarded = false, status = 'active', updatedAt }) {
  return (
  <div className="session-metrics grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm sm:col-span-2 lg:col-span-3">
      <div className="text-sm text-gray-500">Session</div>
      <div className="text-2xl font-semibold text-gray-900">{sessionName || 'Untitled session'}</div>
      {sessionOwner && <div className="mt-1 text-sm text-gray-600">Owner: {sessionOwner}</div>}
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-gray-500">
        <Badge variant={isSessionDiscarded ? 'destructive' : 'outline'}>
          {isSessionDiscarded ? 'Discarded' : status === 'archived' ? 'Archived' : 'Active'}
        </Badge>
        {updatedAt && (
          <span>Updated {new Date(updatedAt).toLocaleString()}</span>
        )}
      </div>
    </div>
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="text-sm text-gray-500">Total records</div>
      <div className="text-2xl font-semibold text-gray-900">
        {sessionDashboardStats.totalRecorded.toLocaleString()}
      </div>
      <div className="mt-1 text-xs text-gray-500">
        Includes faculty clean plates
      </div>
    </div>
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="text-sm text-gray-500">Clean plates</div>
      <div className="text-2xl font-semibold text-emerald-700">
        {sessionDashboardStats.cleanCount.toLocaleString()}
      </div>
      <div className="mt-1 text-xs text-gray-500">
        Clean rate {sessionDashboardStats.cleanPercentage.toFixed(1)}% • Includes faculty clean
      </div>
    </div>
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="text-sm text-gray-500">Dirty plates</div>
      <div className="text-2xl font-semibold text-orange-700">
        {sessionDashboardStats.combinedDirty.toLocaleString()}
      </div>
      <div className="mt-1 text-xs text-gray-500">
        Dirty rate {sessionDashboardStats.dirtyPercentage.toFixed(1)}% • Standard dirty {sessionDashboardStats.dirtyCount.toLocaleString()}
      </div>
    </div>
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="text-sm text-gray-500">Very dirty plates</div>
      <div className="text-2xl font-semibold text-red-700">
        {sessionDashboardStats.redCount.toLocaleString()}
      </div>
    </div>
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="text-sm text-gray-500">Faculty clean plates</div>
      <div className="text-2xl font-semibold text-gray-900">
        {sessionDashboardStats.facultyCount.toLocaleString()}
      </div>
    </div>
  </div>
  )
}
