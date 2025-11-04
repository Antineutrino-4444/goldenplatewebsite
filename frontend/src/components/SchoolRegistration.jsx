import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'

function SchoolRegistration({ app }) {
  const {
    schoolInviteCode,
    setSchoolInviteCode,
    schoolName,
    setSchoolName,
    schoolSlug,
    setSchoolSlug,
    schoolAdminUsername,
    setSchoolAdminUsername,
    schoolAdminPassword,
    setSchoolAdminPassword,
    schoolAdminDisplayName,
    setSchoolAdminDisplayName,
    registerSchool,
    isLoading,
    setShowSchoolRegistration,
    resetSchoolRegistrationForm
  } = app

  const handleBackToLogin = () => {
    resetSchoolRegistrationForm()
    setShowSchoolRegistration(false)
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-2xl">
        <CardHeader className="text-center">
          <CardTitle className="text-3xl font-bold bg-gradient-to-r from-amber-600 to-yellow-600 bg-clip-text text-transparent">
            Register Your School
          </CardTitle>
          <CardDescription className="text-gray-600 mt-2">
            Use the invite code provided by PLATE to activate your school and create the primary admin account.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-4">
            <div className="space-y-2">
              <Label htmlFor="invite-code">Invite Code</Label>
              <Input
                id="invite-code"
                type="text"
                placeholder="Enter invite code"
                value={schoolInviteCode}
                onChange={(e) => setSchoolInviteCode(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="school-name">School Name</Label>
              <Input
                id="school-name"
                type="text"
                placeholder="Full school name"
                value={schoolName}
                onChange={(e) => setSchoolName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="school-slug">School URL Slug (optional)</Label>
              <Input
                id="school-slug"
                type="text"
                placeholder="Lowercase letters and numbers only"
                value={schoolSlug}
                onChange={(e) => setSchoolSlug(e.target.value)}
              />
              <p className="text-xs text-gray-500">
                Leave blank and we will generate one automatically.
              </p>
            </div>
          </div>

          <div className="border-t border-gray-200 pt-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">Primary Admin Account</h3>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="admin-display-name">Display Name</Label>
                <Input
                  id="admin-display-name"
                  type="text"
                  placeholder="Name shown to other users"
                  value={schoolAdminDisplayName}
                  onChange={(e) => setSchoolAdminDisplayName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="admin-username">Admin Username</Label>
                <Input
                  id="admin-username"
                  type="text"
                  placeholder="Choose a username"
                  value={schoolAdminUsername}
                  onChange={(e) => setSchoolAdminUsername(e.target.value)}
                />
              </div>
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="admin-password">Admin Password</Label>
                <Input
                  id="admin-password"
                  type="password"
                  placeholder="Choose a secure password"
                  value={schoolAdminPassword}
                  onChange={(e) => setSchoolAdminPassword(e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-3">
            <Button variant="ghost" onClick={handleBackToLogin} className="sm:w-auto w-full">
              Back to Login
            </Button>
            <Button
              onClick={registerSchool}
              className="bg-amber-600 hover:bg-amber-700 sm:w-auto w-full"
              disabled={isLoading}
            >
              {isLoading ? 'Registering...' : 'Complete Registration'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default SchoolRegistration
