import React, { useRef } from 'react'
import ReCAPTCHA from 'react-google-recaptcha'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'

const RECAPTCHA_SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY

function SchoolRegistration({ app }) {
  const {
    schoolEmail,
    setSchoolEmail,
    schoolName,
    setSchoolName,
    schoolCode,
    setSchoolCode,
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

  const recaptchaRef = useRef(null)

  const handleBackToLogin = () => {
    resetSchoolRegistrationForm()
    setShowSchoolRegistration(false)
  }

  const handleSubmit = async () => {
    const recaptchaToken = recaptchaRef.current?.getValue() || null
    await registerSchool(recaptchaToken)
    recaptchaRef.current?.reset()
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-2xl">
        <CardHeader className="text-center">
          <CardTitle className="text-3xl font-bold bg-gradient-to-r from-amber-600 to-yellow-600 bg-clip-text text-transparent">
            Register Your School
          </CardTitle>
          <CardDescription className="text-gray-600 mt-2">
            Submit your school registration request for PLATE administrator approval.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-4">
            <div className="space-y-2">
              <Label htmlFor="school-email">Contact Email</Label>
              <Input
                id="school-email"
                type="email"
                placeholder="Enter your email address"
                value={schoolEmail}
                onChange={(e) => setSchoolEmail(e.target.value)}
              />
              <p className="text-xs text-gray-500">
                We'll use this email to contact you about your registration.
              </p>
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
              <Label htmlFor="school-code">School Code (optional)</Label>
              <Input
                id="school-code"
                type="text"
                placeholder="Shareable code for your school"
                value={schoolCode}
                onChange={(e) => setSchoolCode(e.target.value)}
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

          {RECAPTCHA_SITE_KEY && (
            <div className="flex justify-center">
              <ReCAPTCHA
                ref={recaptchaRef}
                sitekey={RECAPTCHA_SITE_KEY}
              />
            </div>
          )}

          <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-3">
            <Button variant="ghost" onClick={handleBackToLogin} className="sm:w-auto w-full">
              Back to Login
            </Button>
            <Button
              onClick={handleSubmit}
              className="bg-amber-600 hover:bg-amber-700 sm:w-auto w-full"
              disabled={isLoading}
            >
              {isLoading ? 'Submitting...' : 'Submit Registration Request'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default SchoolRegistration
