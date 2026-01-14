import React from 'react'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Building2, CheckCircle, Copy, KeyRound, ListOrdered, LogOut, RefreshCcw, School, ShieldCheck, UserPlus, XCircle } from 'lucide-react'

function InterschoolPortal({ app }) {
  const {
    user,
    logout,
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
    rejectSchoolRegistration
  } = app

  const formatSchoolNameWithCode = (school) => {
    if (!school?.name) {
      return null
    }
    const code = (school.code ?? school.slug ?? '').trim()
    return code ? `${school.name} (Code: ${code})` : school.name
  }

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

  const toTitle = (value) => {
    if (!value) return ''
    return value
      .toString()
      .split('_')
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ')
  }

  const userSchoolLabel = formatSchoolNameWithCode(user?.school)

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-wrap items-center justify-between gap-3 h-16">
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-amber-600 to-yellow-600 bg-clip-text text-transparent">
                PLATE
              </h1>
              <p className="text-sm text-gray-600">Inter-School Control Center</p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
                {user.name} ({user.username})
              </Badge>
              {userSchoolLabel && (
                <Badge variant="secondary" className="flex items-center gap-1 bg-blue-50 text-blue-700 border-blue-200">
                  <Building2 className="h-3.5 w-3.5" />
                  {userSchoolLabel}
                </Badge>
              )}
              <Badge variant="secondary" className="bg-amber-100 text-amber-700 border-amber-200 uppercase tracking-wide">
                Inter-School
              </Badge>
              <Button
                onClick={() => window.open('https://github.com/Antineutrino-4444/goldenplatewebsite', '_blank')}
                variant="outline"
                size="sm"
                className="text-gray-600 hover:text-gray-900"
              >
                <svg className="h-4 w-4 mr-2" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                </svg>
                GitHub
              </Button>
              <Button onClick={logout} variant="outline" size="sm">
                <LogOut className="h-4 w-4 mr-2" />
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-amber-600" />
              Inter-School Overview
            </CardTitle>
            <CardDescription>
              Coordinate onboarding for partner schools across the district.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm text-gray-600">
              <p>
                Use this portal to issue single-use invites for new schools and track onboarding responsibilities.
              </p>
              <ul className="list-disc list-inside space-y-1">
                <li>Generate unique school IDs paired with invite codes.</li>
                <li>Share credentials securely with the school's lead administrator.</li>
                <li>Reference onboarding guidance and upcoming management tools.</li>
              </ul>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <UserPlus className="h-5 w-5 text-amber-600" />
                Pending School Registration Requests
                {pendingRegistrationRequests.length > 0 && (
                  <Badge className="bg-amber-500 text-white">
                    {pendingRegistrationRequests.length}
                  </Badge>
                )}
              </CardTitle>
              <CardDescription>
                Review and approve school registration requests submitted via the registration form.
              </CardDescription>
            </div>
            <Button
              onClick={refreshInterschoolOverview}
              variant="outline"
              size="sm"
              disabled={interschoolOverviewLoading}
              className="flex items-center gap-2"
            >
              <RefreshCcw className={`h-4 w-4 ${interschoolOverviewLoading ? 'animate-spin' : ''}`} />
              {interschoolOverviewLoading ? 'Refreshing…' : 'Refresh'}
            </Button>
          </CardHeader>
          <CardContent>
            {interschoolRegistrationRequests.length === 0 ? (
              <p className="text-sm text-gray-500">
                No school registration requests have been submitted yet. Schools can register via the registration form.
              </p>
            ) : (
              <div className="space-y-3">
                {interschoolRegistrationRequests.map((request) => {
                  const requestedLabel = formatDateTime(request.requested_at)
                  const reviewedLabel = formatDateTime(request.reviewed_at)
                  const statusClasses = getRequestStatusClasses(request.status)
                  return (
                    <div
                      key={request.id}
                      className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
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
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UserPlus className="h-5 w-5 text-amber-600" />
              Generate School Invite
            </CardTitle>
            <CardDescription>
              Create a one-time invite that provisions a new school ID and administrator slot.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Alert className="mb-4 border-amber-200 bg-amber-50 text-amber-800">
              <ShieldCheck className="h-4 w-4" />
              <AlertDescription className="text-amber-800">
                Codes are shown once. Copy the invite and school ID before closing the dialog.
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
                Each invite is single-use and locks when redeemed.
              </span>
            </div>
            <div className="mt-6">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
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
                  Invites generated during this session will appear here for quick copying.
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
                        <div className="text-xs text-gray-600">School ID: {invite.schoolId}</div>
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
              <div className="mt-3 text-xs text-gray-500">
                The list keeps invites created after you signed in.
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <School className="h-5 w-5 text-amber-600" />
                School Directory
              </CardTitle>
              <CardDescription>
                Monitor partner schools as they complete onboarding.
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {interschoolSchools.length > 0 && (
                <Badge variant="outline" className="text-xs uppercase tracking-wide">
                  {interschoolSchools.length} total
                </Badge>
              )}
              <Button
                onClick={refreshInterschoolOverview}
                variant="outline"
                size="sm"
                disabled={interschoolOverviewLoading}
                className="flex items-center gap-2"
              >
                <RefreshCcw className={`h-4 w-4 ${interschoolOverviewLoading ? 'animate-spin' : ''}`} />
                {interschoolOverviewLoading ? 'Refreshing…' : 'Refresh'}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {interschoolSchools.length === 0 ? (
              <p className="text-sm text-gray-500">
                No partner schools have been registered yet. Once an invite is redeemed the school will appear here.
              </p>
            ) : (
              <div className="space-y-3">
                {interschoolSchools.map((school) => {
                  const createdLabel = formatDateTime(school.created_at)
                  return (
                    <div
                      key={school.id}
                      className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
                    >
                      <div className="space-y-1">
                        <div className="font-semibold text-gray-900">{school.name}</div>
                        <div className="text-xs text-gray-500">School ID: {school.id}</div>
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
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <KeyRound className="h-5 w-5 text-amber-600" />
              Invite Codes Ledger
            </CardTitle>
            <CardDescription>
              Track issued school invites and their redemption status.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {interschoolInvites.length === 0 ? (
              <p className="text-sm text-gray-500">
                Generate a school invite to populate the ledger. Redeemed invites remain visible for auditing.
              </p>
            ) : (
              <div className="space-y-3">
                {interschoolInvites.map((invite) => {
                  const inviteKey = invite.id || invite.code
                  const issuedLabel = formatDateTime(invite.issued_at)
                  const usedLabel = formatDateTime(invite.used_at)
                  const statusClasses = getInviteStatusClasses(invite.status)
                  return (
                    <div
                      key={inviteKey}
                      className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-amber-100 bg-white p-4 shadow-sm"
                    >
                      <div className="space-y-1">
                        <div className="font-mono text-sm text-gray-900">{invite.code}</div>
                        <div className="text-xs text-gray-600">School ID: {invite.school_id}</div>
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
                            issuedAt: invite.issued_at
                          }, 'code')}>
                            <Copy className="h-3 w-3 mr-1" />
                            Copy
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => copySchoolInvite({
                            code: invite.code,
                            schoolId: invite.school_id,
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
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ListOrdered className="h-5 w-5 text-amber-600" />
              Onboarding Checklist
            </CardTitle>
            <CardDescription>
              Share these steps with the school's onboarding lead.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ol className="list-decimal list-inside space-y-2 text-sm text-gray-600">
              <li>Generate a new invite and copy the code and school ID.</li>
              <li>Send the credentials securely to the school's lead administrator.</li>
              <li>The administrator completes the registration workflow using the invite.</li>
            </ol>
            <Alert className="mt-4 border-amber-200 bg-amber-50 text-amber-800">
              <ShieldCheck className="h-4 w-4" />
              <AlertDescription className="text-amber-800">
                Need to audit or disable a school? Coordinate with a super admin while expanded management tools are rolling out here.
              </AlertDescription>
            </Alert>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}

export default InterschoolPortal
