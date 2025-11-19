import React from 'react'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Building2, Copy, ListOrdered, LogOut, ShieldCheck, UserPlus } from 'lucide-react'

function InterschoolPortal({ app }) {
  const {
    user,
    logout,
    issueSchoolInvite,
    schoolInviteLoading,
    latestSchoolInvites,
    copySchoolInvite
  } = app

  const formatSchoolNameWithCode = (school) => {
    if (!school?.name) {
      return null
    }
    const code = (school.code ?? school.slug ?? '').trim()
    return code ? `${school.name} (Code: ${code})` : school.name
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
