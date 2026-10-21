import React from 'react'
import CaptchaVerification from '@/components/CaptchaVerification.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import VerificationCodeInput from './VerificationCodeInput.jsx'

function SchoolRegistration({ app }) {
  const {
    schoolEmail,
    setSchoolEmail,
    schoolName,
    setSchoolName,
    schoolCode,
    setSchoolCode,
    schoolInviteCode,
    setSchoolInviteCode,
    schoolInviteSchoolId,
    setSchoolInviteSchoolId,
    schoolSignupMode,
    setSchoolSignupMode,
    schoolAdminUsername,
    setSchoolAdminUsername,
    schoolAdminPassword,
    setSchoolAdminPassword,
    schoolAdminDisplayName,
    setSchoolAdminDisplayName,
    emailVerificationCode,
    setEmailVerificationCode,
    emailVerified,
    verificationSent,
    verificationLoading,
    sendVerificationCode,
    verifyEmailCode,
    verificationExpiryMinutes,
    registerSchool,
    isLoading,
    setShowSchoolRegistration,
    resetSchoolRegistrationForm
  } = app

  const isInviteMode = schoolSignupMode === 'invite'

  const handleBackToLogin = () => {
    resetSchoolRegistrationForm()
    setShowSchoolRegistration(false)
  }

  const handleSendVerificationCode = async () => {
    await sendVerificationCode()
  }

  const handleVerifyCode = async () => {
    await verifyEmailCode()
  }

  const handleSubmit = async () => {
    await registerSchool()
  }

  const handleEmailChange = (e) => {
    setSchoolEmail(e.target.value)
  }

  return (
    <div className="school-registration flex items-center justify-center px-4 py-10 sm:py-14">
      <Card className="w-full max-w-2xl">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl sm:text-3xl font-bold text-[var(--site-ink)]">
            <h1>Register Your School</h1>
          </CardTitle>
          <CardDescription className="text-gray-600 mt-2 text-sm">
            {isInviteMode ? 'Register a school using your invite code.' : 'Register a school for PLATE administrator approval.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label>Registration Method</Label>
            <div className="flex border rounded-lg overflow-hidden">
              <button
                type="button"
                onClick={() => setSchoolSignupMode('request')}
                className={`px-3 py-1.5 text-sm flex-1 transition-colors ${
                  schoolSignupMode === 'request'
                    ? 'bg-amber-600 text-white'
                    : 'bg-white text-gray-700 hover:bg-gray-50'
                }`}
              >
                Email Verification
              </button>
              <button
                type="button"
                onClick={() => setSchoolSignupMode('invite')}
                className={`px-3 py-1.5 text-sm flex-1 transition-colors ${
                  schoolSignupMode === 'invite'
                    ? 'bg-amber-600 text-white'
                    : 'bg-white text-gray-700 hover:bg-gray-50'
                }`}
              >
                Legacy Invite
              </button>
            </div>
            <p className="text-xs text-gray-500">
              Email registration requires approval. A legacy invite gives immediate access.
            </p>
          </div>
          {/* Step 1: Email Verification */}
          {isInviteMode ? (
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-6 h-6 rounded-full flex items-center justify-center text-sm font-bold bg-amber-500 text-white">
                  1
                </div>
                <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
                  Invite Details
                </h3>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="school-invite-code">Legacy Invite Code</Label>
                  <Input
                    id="school-invite-code"
                    type="text"
                    placeholder="Enter the invite code provided"
                    value={schoolInviteCode}
                    onChange={(e) => setSchoolInviteCode(e.target.value)}
                  />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="school-invite-id">School ID (optional)</Label>
                  <Input
                    id="school-invite-id"
                    type="text"
                    placeholder="Enter the school ID if provided"
                    value={schoolInviteSchoolId}
                    onChange={(e) => setSchoolInviteSchoolId(e.target.value)}
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-2">
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-sm font-bold ${emailVerified ? 'bg-green-500 text-white' : 'bg-amber-500 text-white'}`}>
                  {emailVerified ? '✓' : '1'}
                </div>
                <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
                  Verify Your Email
                </h3>
              </div>

              <div className="space-y-3">
                <div className="space-y-2">
                  <Label htmlFor="school-email">Contact Email</Label>
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Input
                      id="school-email"
                      type="email"
                      placeholder="Enter your email address"
                      value={schoolEmail}
                      onChange={handleEmailChange}
                      disabled={emailVerified}
                      className={emailVerified ? 'bg-green-50 border-green-300' : ''}
                    />
                    {!emailVerified && (
                      <Button
                        onClick={handleSendVerificationCode}
                        disabled={verificationLoading || !schoolEmail.trim()}
                        className="bg-amber-600 hover:bg-amber-700 whitespace-nowrap w-full sm:w-auto"
                      >
                        {verificationLoading ? 'Sending...' : verificationSent ? 'Resend Code' : 'Send Code'}
                      </Button>
                    )}
                  </div>
                  {emailVerified && (
                    <p className="text-xs text-green-600 font-medium">
                      Email verified.
                    </p>
                  )}
                  {!emailVerified && (
                    <p className="text-xs text-gray-500">
                      Used for email verification and, after approval, school account signup alerts.
                    </p>
                  )}
                </div>

                {verificationSent && !emailVerified && (
                  <div className="space-y-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                    <Label className="text-center block">Enter Verification Code</Label>
                    <VerificationCodeInput
                      value={emailVerificationCode}
                      onChange={setEmailVerificationCode}
                      disabled={verificationLoading}
                    />
                    <div className="flex justify-center">
                      <Button
                        onClick={handleVerifyCode}
                        disabled={verificationLoading || emailVerificationCode.length !== 6}
                        className="bg-green-600 hover:bg-green-700 px-8"
                      >
                        {verificationLoading ? 'Verifying...' : 'Verify Code'}
                      </Button>
                    </div>
                    <p className="text-xs text-amber-700 text-center">
                      Enter the 6-digit code from your email. It expires in {verificationExpiryMinutes} minutes.
                      <br />
                      <span className="text-gray-500">Can't find it? Check your junk/spam folder.</span>
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Step 2: School Details (shown after email verification or invite selection) */}
          {(emailVerified || isInviteMode) && (
            <>
              <div className="border-t border-gray-200 pt-4">
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-6 h-6 rounded-full flex items-center justify-center text-sm font-bold bg-amber-500 text-white">
                    2
                  </div>
                  <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
                    School Information
                  </h3>
                </div>
                <div className="grid gap-4">
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
                      Leave blank to generate a school code.
                    </p>
                  </div>
                </div>
              </div>

              <div className="border-t border-gray-200 pt-4">
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-6 h-6 rounded-full flex items-center justify-center text-sm font-bold bg-amber-500 text-white">
                    3
                  </div>
                  <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
                    Primary Admin Account
                  </h3>
                </div>
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
                      placeholder="Choose a password (at least 6 characters)"
                      value={schoolAdminPassword}
                      onChange={(e) => setSchoolAdminPassword(e.target.value)}
                    />
                  </div>
                </div>
              </div>
            </>
          )}

          <CaptchaVerification actions="school_email_code school_register" />

          <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-3">
            <Button variant="ghost" onClick={handleBackToLogin} className="sm:w-auto w-full">
              Back to Login
            </Button>
            {(emailVerified || isInviteMode) && (
              <Button
                onClick={handleSubmit}
                className="bg-amber-600 hover:bg-amber-700 sm:w-auto w-full"
                disabled={isLoading}
              >
                {isLoading ? 'Submitting...' : isInviteMode ? 'Register School' : 'Submit Registration Request'}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default SchoolRegistration
