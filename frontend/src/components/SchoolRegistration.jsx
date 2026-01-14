import React, { useRef } from 'react'
import ReCAPTCHA from 'react-google-recaptcha'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import VerificationCodeInput from './VerificationCodeInput.jsx'

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
    emailVerificationCode,
    setEmailVerificationCode,
    emailVerified,
    verificationSent,
    verificationLoading,
    sendVerificationCode,
    verifyEmailCode,
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

  const handleSendVerificationCode = async () => {
    const recaptchaToken = recaptchaRef.current?.getValue() || null
    await sendVerificationCode(recaptchaToken)
    recaptchaRef.current?.reset()
  }

  const handleVerifyCode = async () => {
    await verifyEmailCode()
  }

  const handleSubmit = async () => {
    const recaptchaToken = recaptchaRef.current?.getValue() || null
    await registerSchool(recaptchaToken)
    recaptchaRef.current?.reset()
  }

  const handleEmailChange = (e) => {
    setSchoolEmail(e.target.value)
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
          {/* Step 1: Email Verification */}
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
                <div className="flex gap-2">
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
                      className="bg-amber-600 hover:bg-amber-700 whitespace-nowrap"
                    >
                      {verificationLoading ? 'Sending...' : verificationSent ? 'Resend Code' : 'Send Code'}
                    </Button>
                  )}
                </div>
                {emailVerified && (
                  <p className="text-xs text-green-600 font-medium">
                    Email verified successfully!
                  </p>
                )}
                {!emailVerified && (
                  <p className="text-xs text-gray-500">
                    We'll send a verification code to this email address.
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
                    Check your email for the 6-digit verification code. The code expires in 15 minutes.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Step 2: School Details (only shown after email verification) */}
          {emailVerified && (
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
                      Leave blank and we will generate one automatically.
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
                      placeholder="Choose a secure password"
                      value={schoolAdminPassword}
                      onChange={(e) => setSchoolAdminPassword(e.target.value)}
                    />
                  </div>
                </div>
              </div>
            </>
          )}

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
            {emailVerified && (
              <Button
                onClick={handleSubmit}
                className="bg-amber-600 hover:bg-amber-700 sm:w-auto w-full"
                disabled={isLoading}
              >
                {isLoading ? 'Submitting...' : 'Submit Registration Request'}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default SchoolRegistration
