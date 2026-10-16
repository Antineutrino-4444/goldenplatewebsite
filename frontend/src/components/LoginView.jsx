import React from 'react'
import RecaptchaNotice from '@/components/RecaptchaNotice.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'

function SignupPageContent({ children }) {
  return <Card className="w-full max-w-md"><CardContent className="space-y-4 pt-6">{children}</CardContent></Card>
}

function LoginView({ app }) {
  const SignupContent = app.signupPage ? SignupPageContent : DialogContent
  const {
    loginUsername,
    setLoginUsername,
    loginPassword,
    setLoginPassword,
    login,
    guestLogin,
    guestSchoolCode,
    setGuestSchoolCode,
    showGuestSchoolDialog,
    setShowGuestSchoolDialog,
    isLoading,
    showSignupDialog,
    setShowSignupDialog,
    signupUsername,
    setSignupUsername,
    signupPassword,
    setSignupPassword,
    signupName,
    setSignupName,
    signupSchoolCode,
    setSignupSchoolCode,
    signupInviteCode,
    setSignupInviteCode,
    signupMode,
    setSignupMode,
    signup,
    setShowSchoolRegistration,
    resetSchoolRegistrationForm
  } = app

  const handleSignupDialogChange = (open) => {
    setShowSignupDialog(open)
    if (!open) {
      setSignupInviteCode('')
      setSignupMode('school')
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-3 sm:p-4">
      {!app.signupPage && <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl sm:text-3xl font-bold bg-gradient-to-r from-amber-600 to-yellow-600 bg-clip-text text-transparent">
            PLATE
          </CardTitle>
          <CardDescription className="text-gray-600 mt-2 text-sm">
            Prevention, Logging & Assessment of Tossed Edibles
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              type="text"
              autoComplete="username"
              placeholder="Enter username"
              value={loginUsername}
              onChange={(e) => setLoginUsername(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && login()}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="Enter password"
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && login()}
            />
          </div>
          <Button
            onClick={login}
            className="w-full bg-amber-600 hover:bg-amber-700"
            disabled={isLoading}
          >
            {isLoading ? 'Logging in...' : 'Login'}
          </Button>

          <Button
            onClick={() => setShowGuestSchoolDialog(true)}
            variant="outline"
            className="w-full border-amber-600 text-amber-600 hover:bg-amber-50"
            disabled={isLoading}
          >
            Continue as Guest
          </Button>

          <div className="text-center space-y-1">
            <Button
              variant="link"
              onClick={() => setShowSignupDialog(true)}
              className="text-amber-600 hover:text-amber-700"
            >
              Don't have an account? Sign up
            </Button>
            <Button
              variant="link"
              onClick={() => {
                resetSchoolRegistrationForm()
                setShowSchoolRegistration(true)
              }}
              className="text-amber-600 hover:text-amber-700"
            >
              Register your school
            </Button>
          </div>
        </CardContent>
      </Card>}

      <Dialog
        open={showGuestSchoolDialog}
        onOpenChange={(open) => {
          setShowGuestSchoolDialog(open)
          if (!open) {
            setGuestSchoolCode('')
          }
        }}
      >
        <DialogContent dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle>Enter School Code</DialogTitle>
            <DialogDescription>
              Provide the code for the school you want to view as a guest.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="guest-school-code">School Code</Label>
              <Input
                id="guest-school-code"
                type="text"
                placeholder="e.g., SAC"
                value={guestSchoolCode}
                onChange={(e) => setGuestSchoolCode(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    guestLogin()
                  }
                }}
                autoFocus
              />
              <p className="text-xs text-gray-500">
                Ask your school administrator for the code. Guest access is read-only.
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => {
                  setShowGuestSchoolDialog(false)
                  setGuestSchoolCode('')
                }}
                disabled={isLoading}
              >
                Cancel
              </Button>
              <Button
                className="flex-1 bg-amber-600 hover:bg-amber-700"
                onClick={guestLogin}
                disabled={isLoading}
              >
                {isLoading ? 'Connecting...' : 'Continue as Guest'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={showSignupDialog}
        onOpenChange={handleSignupDialogChange}
      >
        <SignupContent dismissOnOverlayClick={false} className="max-h-[90dvh] overflow-y-auto p-4 sm:p-6">
          <DialogHeader>
            <DialogTitle>Request Account</DialogTitle>
            <DialogDescription>
              Enter your information to request an account. Your school administrator will review your request.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Sign-up method</Label>
              <div className="flex border rounded-lg overflow-hidden">
                <button
                  type="button"
                  onClick={() => {
                    setSignupMode('school')
                    setSignupInviteCode('')
                  }}
                  className={`px-3 py-1.5 text-sm flex-1 transition-colors ${
                    signupMode === 'school'
                      ? 'bg-amber-600 text-white'
                      : 'bg-white text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  School Code
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setSignupMode('invite')
                    setSignupSchoolCode('')
                  }}
                  className={`px-3 py-1.5 text-sm flex-1 transition-colors ${
                    signupMode === 'invite'
                      ? 'bg-amber-600 text-white'
                      : 'bg-white text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  Legacy Invite
                </button>
              </div>
              <p className="text-xs text-gray-500">
                Use a legacy invite code for immediate access, or request approval with your school code.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="signup-name">Full Name</Label>
              <Input
                id="signup-name"
                type="text"
                placeholder="Enter your full name"
                value={signupName}
                onChange={(e) => setSignupName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="signup-username">Username</Label>
              <Input
                id="signup-username"
                type="text"
                placeholder="Choose a username (min 3 characters)"
                value={signupUsername}
                onChange={(e) => setSignupUsername(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="signup-password">Password</Label>
              <Input
                id="signup-password"
                type="password"
                placeholder="Choose a password (min 6 characters)"
                value={signupPassword}
                onChange={(e) => setSignupPassword(e.target.value)}
              />
            </div>
            {signupMode === 'school' ? (
              <div className="space-y-2">
                <Label htmlFor="signup-school">School Code</Label>
                <Input
                  id="signup-school"
                  type="text"
                  placeholder="Enter your school code (e.g., SAC)"
                  value={signupSchoolCode}
                  onChange={(e) => setSignupSchoolCode(e.target.value)}
                />
                <p className="text-xs text-gray-500">
                  Ask your school administrator for your school code.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <Label htmlFor="signup-invite">Legacy Invite Code</Label>
                <Input
                  id="signup-invite"
                  type="text"
                  placeholder="Enter your invite code"
                  value={signupInviteCode}
                  onChange={(e) => setSignupInviteCode(e.target.value)}
                />
                <p className="text-xs text-gray-500">
                  Enter the one-time invite code provided by your administrator.
                </p>
              </div>
            )}
            <RecaptchaNotice />
            <div className="flex gap-2">
              <Button onClick={() => handleSignupDialogChange(false)} variant="outline" className="flex-1">
                Cancel
              </Button>
              <Button
                onClick={signup}
                className="flex-1 bg-amber-600 hover:bg-amber-700"
                disabled={isLoading}
              >
                {isLoading ? 'Submitting...' : 'Submit Request'}
              </Button>
            </div>
          </div>
        </SignupContent>
      </Dialog>
    </div>
  )
}

export default LoginView
