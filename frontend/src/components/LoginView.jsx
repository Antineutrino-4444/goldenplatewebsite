import React from 'react'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'

function LoginView({ app }) {
  const {
    loginUsername,
    setLoginUsername,
    loginPassword,
    setLoginPassword,
    login,
    guestLogin,
    guestSchoolSlug,
    setGuestSchoolSlug,
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
    signupInviteCode,
    setSignupInviteCode,
    signup,
    setShowSchoolRegistration,
    resetSchoolRegistrationForm
  } = app

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-3xl font-bold bg-gradient-to-r from-amber-600 to-yellow-600 bg-clip-text text-transparent">
            PLATE
          </CardTitle>
          <CardDescription className="text-gray-600 mt-2">
            Prevention, Logging & Assessment of Tossed Edibles
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              type="text"
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
              Have a school invite? Register your school
            </Button>
          </div>
        </CardContent>
      </Card>

      <Dialog
        open={showGuestSchoolDialog}
        onOpenChange={(open) => {
          setShowGuestSchoolDialog(open)
          if (!open) {
            setGuestSchoolSlug('')
          }
        }}
      >
        <DialogContent dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle>Enter School Slug</DialogTitle>
            <DialogDescription>
              Provide the slug for the school you want to view as a guest.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="guest-school-slug">School Slug</Label>
              <Input
                id="guest-school-slug"
                type="text"
                placeholder="e.g., default"
                value={guestSchoolSlug}
                onChange={(e) => setGuestSchoolSlug(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    guestLogin()
                  }
                }}
                autoFocus
              />
              <p className="text-xs text-gray-500">
                Ask your administrator for the slug. Guest access is read-only.
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => {
                  setShowGuestSchoolDialog(false)
                  setGuestSchoolSlug('')
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

      <Dialog open={showSignupDialog} onOpenChange={setShowSignupDialog}>
        <DialogContent dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle>Create Account</DialogTitle>
            <DialogDescription>
              Enter your information to create a new account
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
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
            <div className="space-y-2">
              <Label htmlFor="signup-invite">Invite Code</Label>
              <Input
                id="signup-invite"
                type="text"
                placeholder="Enter invite code"
                value={signupInviteCode}
                onChange={(e) => setSignupInviteCode(e.target.value)}
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={() => setShowSignupDialog(false)} variant="outline" className="flex-1">
                Cancel
              </Button>
              <Button
                onClick={signup}
                className="flex-1 bg-amber-600 hover:bg-amber-700"
                disabled={isLoading}
              >
                {isLoading ? 'Creating...' : 'Create Account'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default LoginView
