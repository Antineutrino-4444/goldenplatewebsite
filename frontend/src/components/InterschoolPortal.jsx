import VideoHelp from '@/components/VideoHelp.jsx'
import React from 'react'
import PortalHeader from '@/components/PortalHeader.jsx'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Button } from '@/components/ui/button.jsx'
import { CardContent } from '@/components/ui/card.jsx'
import { CheckCircle, ChevronDown, Copy, KeyRound, ListOrdered, RefreshCcw, School, ShieldCheck, Trash2, UserPlus, XCircle } from 'lucide-react'

function PortalSection({ id, title, description, icon: Icon, count, children }) {
  return (
    <details id={id} className="group min-w-0 rounded-xl border bg-card text-card-foreground shadow-sm">
      <summary className="flex cursor-pointer list-none items-start justify-between gap-4 rounded-xl p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-600 sm:p-6 [&::-webkit-details-marker]:hidden">
        <div className="min-w-0 space-y-1.5">
          <h2 className="flex flex-wrap items-center gap-2 font-semibold">
            <Icon className="h-5 w-5 text-amber-600" aria-hidden="true" />
            {title}
            {count !== undefined && <Badge variant="outline">{count}</Badge>}
          </h2>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
        <ChevronDown className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden="true" />
      </summary>
      <div className="pb-6">{children}</div>
    </details>
  )
}

function InterschoolPortal({ app }) {
  const {
    issueSchoolInvite,
    schoolInviteLoading,
    latestSchoolInvites,
    copySchoolInvite,
    interschoolSchools,
    interschoolInvites,
    interschoolOverviewLoading,
    refreshInterschoolOverview,
    interschoolRegistrationRequests,
    approveSchoolRegistration,
    rejectSchoolRegistration,
    deleteSchool
  } = app

  const formatDateTime = (value) => {
    if (!value) return null
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return null
    return date.toLocaleString()
  }

  const getInviteStatusClasses = (status) => {
    const normalized = (status || '').toLowerCase()
    if (normalized === 'unused') {
      return 'bg-emerald-50 text-emerald-700 border-emerald-200'
    }
    if (normalized === 'used') {
      return 'bg-slate-100 text-slate-700 border-slate-200'
    }
    if (normalized === 'revoked') {
      return 'bg-red-50 text-red-700 border-red-200'
    }
    return 'bg-gray-50 text-gray-600 border-gray-200'
  }

  const getRequestStatusClasses = (status) => {
    const normalized = (status || '').toLowerCase()
    if (normalized === 'pending') {
      return 'bg-amber-50 text-amber-700 border-amber-200'
    }
    if (normalized === 'approved') {
      return 'bg-emerald-50 text-emerald-700 border-emerald-200'
    }
    if (normalized === 'rejected') {
      return 'bg-red-50 text-red-700 border-red-200'
    }
    return 'bg-gray-50 text-gray-600 border-gray-200'
  }

  const handleRejectRegistration = async (requestId) => {
    const reason = window.prompt('Enter rejection reason (optional):')
    if (reason === null) return // User cancelled
    await rejectSchoolRegistration(requestId, reason)
  }

  const pendingRegistrationRequests = interschoolRegistrationRequests.filter(r => r.status === 'pending')
  const rejectedRegistrationRequests = interschoolRegistrationRequests.filter(r => r.status === 'rejected')
  const approvedRegistrationRequests = interschoolRegistrationRequests.filter(r => r.status === 'approved')

  const toTitle = (value) => {
    if (!value) return ''
    return value
      .toString()
      .split('_')
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ')
  }

  const renderRegistrationRequests = (requests, emptyMessage) => (
    requests.length === 0 ? (
      <p className="text-sm text-gray-500">
        {interschoolOverviewLoading ? 'Loading school registration requests…' : emptyMessage}
      </p>
    ) : (
      <div className="space-y-3">
        {requests.map((request) => {
          const requestedLabel = formatDateTime(request.requested_at)
          const reviewedLabel = formatDateTime(request.reviewed_at)
          const statusClasses = getRequestStatusClasses(request.status)
          return (
            <div
              key={request.id}
              className="flex min-w-0 flex-wrap items-start justify-between gap-3 [&>div]:min-w-0 rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
            >
              <div className="space-y-1">
                <div className="font-semibold text-gray-900">{request.school_name}</div>
                <div className="text-sm text-gray-600">
                  Contact: {request.email}
                </div>
                <div className="text-sm text-gray-600">
                  Admin: {request.admin_display_name} (@{request.admin_username})
                </div>
                {request.school_slug && (
                  <div className="text-xs text-gray-500">School Code: {request.school_slug}</div>
                )}
                {requestedLabel && (
                  <div className="text-xs text-gray-400">Requested {requestedLabel}</div>
                )}
                {reviewedLabel && (
                  <div className="text-xs text-gray-400">Reviewed {reviewedLabel}</div>
                )}
                {request.rejection_reason && (
                  <div className="text-xs text-red-600">Reason: {request.rejection_reason}</div>
                )}
              </div>
              <div className="flex flex-col items-start gap-2 sm:items-end">
                <Badge variant="outline" className={`text-xs uppercase tracking-wide ${statusClasses}`}>
                  {toTitle(request.status) || 'Unknown'}
                </Badge>
                {request.status === 'pending' && (
                  <div className="flex flex-wrap gap-2">
                    <Button
                      onClick={() => approveSchoolRegistration(request.id)}
                      variant="default"
                      size="sm"
                      className="bg-green-600 hover:bg-green-700"
                    >
                      <CheckCircle className="h-4 w-4 mr-1" />
                      Approve
                    </Button>
                    <Button
                      onClick={() => handleRejectRegistration(request.id)}
                      variant="outline"
                      size="sm"
                    >
                      <XCircle className="h-4 w-4 mr-1" />
                      Reject
                    </Button>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    )
  )

  return (
    <div className="min-h-screen min-w-0 bg-gray-50 [overflow-wrap:anywhere]">
      <PortalHeader app={app} interschool />

      <main className="max-w-5xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-8 space-y-4 sm:space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-xl font-semibold text-gray-900">Inter-School Administration</h1>
          <Button onClick={refreshInterschoolOverview} variant="outline" size="sm" disabled={interschoolOverviewLoading}>
            <RefreshCcw className={`mr-2 h-4 w-4 ${interschoolOverviewLoading ? 'animate-spin' : ''}`} />
            {interschoolOverviewLoading ? 'Refreshing…' : 'Refresh'}
          </Button>
        </div>
        <VideoHelp videos={[29, 30, 31]} label="Video guides for partner schools" />
        <PortalSection id="pending-registrations" title="Pending School Registration Requests" description="Review schools awaiting approval." icon={UserPlus} count={pendingRegistrationRequests.length}>
          <CardContent>
            {renderRegistrationRequests(pendingRegistrationRequests, 'No pending school registration requests.')}
          </CardContent>
        </PortalSection>

        <PortalSection id="overview" title="Inter-School Overview" description="Review school registrations, issue invites, and manage partner schools." icon={ShieldCheck}>
          <CardContent>
            <div className="space-y-2 text-sm text-gray-600">
              <p>
                Issue single-use school invites and track which have been redeemed.
              </p>
              <ul className="list-disc list-inside space-y-1">
                <li>Generate an invite for a new school.</li>
                <li>Share the invite with the school's lead administrator.</li>
                <li>Review invite use and registered schools.</li>
              </ul>
            </div>
          </CardContent>
        </PortalSection>

        <PortalSection id="generate-invite" title="Generate School Invite" description="Create a one-time invite for a new school and its lead administrator." icon={UserPlus}>
          <CardContent>
            <Alert className="mb-4 border-amber-200 bg-amber-50 text-amber-800">
              <ShieldCheck className="h-4 w-4" />
              <AlertDescription className="text-amber-800">
                Copy an invite from Recent invites or the Invite Codes Ledger.
              </AlertDescription>
            </Alert>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                onClick={issueSchoolInvite}
                className="bg-amber-600 hover:bg-amber-700"
                disabled={schoolInviteLoading}
              >
                <UserPlus className="h-4 w-4 mr-2" />
                {schoolInviteLoading ? 'Generating…' : 'Generate Invite'}
              </Button>
              <span className="text-sm text-gray-500">
                Each invite can be used once.
              </span>
            </div>
            <div className="mt-6">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
                <h4 className="text-sm font-semibold text-gray-700 flex flex-wrap items-center gap-2">
                  <ListOrdered className="h-4 w-4" />
                  Recent invites
                </h4>
                {latestSchoolInvites.length > 0 && (
                  <Badge variant="outline" className="text-xs uppercase tracking-wide">
                    {latestSchoolInvites.length} stored
                  </Badge>
                )}
              </div>
              {latestSchoolInvites.length === 0 ? (
                <p className="text-sm text-gray-500">
                  No invites generated since signing in.
                </p>
              ) : (
                <div className="space-y-3">
                  {latestSchoolInvites.map((invite) => (
                    <div
                      key={`${invite.code}-${invite.schoolId}`}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-100 bg-white p-3 shadow-sm"
                    >
                      <div>
                        <div className="font-mono text-sm text-gray-900">{invite.code}</div>
                        <div className="text-xs text-gray-600">New school (awaiting registration)</div>
                        {invite.issuedAt && (
                          <div className="text-xs text-gray-400">
                            {new Date(invite.issuedAt).toLocaleString()}
                          </div>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" variant="outline" onClick={() => copySchoolInvite(invite, 'code')}>
                          <Copy className="h-3 w-3 mr-1" />
                          Copy
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => copySchoolInvite(invite, 'details')}>
                          <Copy className="h-3 w-3 mr-1" />
                          Details
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </PortalSection>

        <PortalSection id="school-directory" title="School Directory" description="View registered schools and their accounts." icon={School} count={interschoolSchools.length}>
          <CardContent>
            {interschoolSchools.length === 0 ? (
              <p className="text-sm text-gray-500">
                {interschoolOverviewLoading ? 'Loading schools…' : 'No partner schools registered yet.'}
              </p>
            ) : (
              <div className="space-y-3">
                {interschoolSchools.map((school) => {
                  const createdLabel = formatDateTime(school.created_at)
                  const isSystemSchool = school.id === 'default-school' || school.id === 'a11'
                  const handleDeleteSchool = () => {
                    if (window.confirm(`Are you sure you want to delete "${school.name}"? This will also delete all users associated with this school. This action cannot be undone.`)) {
                      deleteSchool(school.id)
                    }
                  }
                  return (
                    <div
                      key={school.id}
                      className="flex min-w-0 flex-wrap items-start justify-between gap-3 [&>div]:min-w-0 rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
                    >
                      <div className="space-y-1">
                        <div className="font-semibold text-gray-900">{school.name}</div>
                        {school.slug && (
                          <div className="text-xs text-gray-500">Code: {school.slug}</div>
                        )}
                        {createdLabel && (
                          <div className="text-xs text-gray-400">Created {createdLabel}</div>
                        )}
                      </div>
                      <div className="flex flex-col items-start gap-2 sm:items-end">
                        <Badge variant="outline" className="text-xs uppercase tracking-wide">
                          {toTitle(school.status) || 'Unknown'}
                        </Badge>
                        <div className="text-xs text-gray-500">Users: {school.user_count ?? 0}</div>
                        {school.updated_at && (
                          <div className="text-xs text-gray-400">Updated {formatDateTime(school.updated_at)}</div>
                        )}
                        {!isSystemSchool && (
                          <Button
                            onClick={handleDeleteSchool}
                            variant="outline"
                            size="sm"
                            className="text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
                          >
                            <Trash2 className="h-4 w-4 mr-1" />
                            Delete
                          </Button>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </PortalSection>

        <PortalSection id="invite-ledger" title="Invite Codes Ledger" description="Track issued school invites and their redemption status." icon={KeyRound} count={interschoolInvites.length}>
          <CardContent>
            {interschoolInvites.length === 0 ? (
              <p className="text-sm text-gray-500">
                {interschoolOverviewLoading ? 'Loading school invites…' : 'No school invites have been issued yet.'}
              </p>
            ) : (
              <div className="space-y-3">
                {interschoolInvites.map((invite) => {
                  const inviteSchool = interschoolSchools.find((school) => school.id === invite.school_id)
                  const inviteKey = invite.id || invite.code
                  const issuedLabel = formatDateTime(invite.issued_at)
                  const usedLabel = formatDateTime(invite.used_at)
                  const statusClasses = getInviteStatusClasses(invite.status)
                  return (
                    <div
                      key={inviteKey}
                      className="flex min-w-0 flex-wrap items-start justify-between gap-3 [&>div]:min-w-0 rounded-lg border border-amber-100 bg-white p-4 shadow-sm"
                    >
                      <div className="space-y-1">
                        <div className="font-mono text-sm text-gray-900">{invite.code}</div>
                        <div className="text-xs text-gray-600">School: {inviteSchool?.name || 'New school (awaiting registration)'}</div>
                        {issuedLabel && (
                          <div className="text-xs text-gray-400">Issued {issuedLabel}</div>
                        )}
                        {invite.issued_by?.display_name && (
                          <div className="text-xs text-gray-500">
                            Issued by {invite.issued_by.display_name} ({invite.issued_by.username})
                          </div>
                        )}
                        {usedLabel && (
                          <div className="text-xs text-gray-400">Redeemed {usedLabel}</div>
                        )}
                        {invite.used_by?.display_name && (
                          <div className="text-xs text-gray-500">
                            Used by {invite.used_by.display_name} ({invite.used_by.username})
                          </div>
                        )}
                      </div>
                      <div className="flex flex-col items-start gap-2 sm:items-end">
                        <Badge variant="outline" className={`text-xs uppercase tracking-wide ${statusClasses}`}>
                          {toTitle(invite.status) || 'Unknown'}
                        </Badge>
                        <div className="flex flex-wrap gap-2">
                          <Button size="sm" variant="outline" onClick={() => copySchoolInvite({
                            code: invite.code,
                            schoolId: invite.school_id,
                            schoolName: inviteSchool?.name,
                            schoolCode: inviteSchool?.slug,
                            issuedAt: invite.issued_at
                          }, 'code')}>
                            <Copy className="h-3 w-3 mr-1" />
                            Copy
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => copySchoolInvite({
                            code: invite.code,
                            schoolId: invite.school_id,
                            schoolName: inviteSchool?.name,
                            schoolCode: inviteSchool?.slug,
                            issuedAt: invite.issued_at
                          }, 'details')}>
                            <Copy className="h-3 w-3 mr-1" />
                            Details
                          </Button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </PortalSection>

        <PortalSection id="onboarding-checklist" title="Onboarding Checklist" description="Share these steps with the school's onboarding lead." icon={ListOrdered}>
          <CardContent>
            <ol className="list-decimal list-inside space-y-2 text-sm text-gray-600">
              <li>Generate a new invite and copy the code.</li>
              <li>Share the invite code with the school's lead administrator.</li>
              <li>The administrator completes the registration workflow using the invite.</li>
            </ol>
          </CardContent>
        </PortalSection>
        <PortalSection id="rejected-registrations" title="Rejected School Registration Requests" description="Review previously rejected requests." icon={XCircle} count={rejectedRegistrationRequests.length}>
          <CardContent>
            {renderRegistrationRequests(rejectedRegistrationRequests, 'No rejected school registration requests.')}
          </CardContent>
        </PortalSection>

        <PortalSection id="approved-registrations" title="Approved School Registration Requests" description="Review previously approved requests." icon={CheckCircle} count={approvedRegistrationRequests.length}>
          <CardContent>
            {renderRegistrationRequests(approvedRegistrationRequests, 'No approved school registration requests.')}
          </CardContent>
        </PortalSection>
      </main>
    </div>
  )
}

export default InterschoolPortal
