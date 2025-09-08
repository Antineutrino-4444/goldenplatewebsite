import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/card'
import { Button } from './components/ui/button'
import { Input } from './components/ui/input'
import { Badge } from './components/ui/badge'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from './components/ui/dialog'
import { Trash2, Github, Users, BarChart3, Upload, Download, Settings, Plus, Eye } from 'lucide-react'

const API_BASE = 'http://localhost:5000/api'

function App() {
  // State variables
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState(null)
  const [sessionId, setSessionId] = useState(null)
  const [sessionName, setSessionName] = useState('')
  const [sessionStats, setSessionStats] = useState({ 
    clean_count: 0, 
    dirty_count: 0, 
    red_count: 0, 
    combined_dirty_count: 0, 
    total_recorded: 0, 
    clean_percentage: 0, 
    dirty_percentage: 0 
  })
  const [combinedStats, setCombinedStats] = useState({ 
    clean_count: 0, 
    dirty_count: 0, 
    red_count: 0, 
    combined_dirty_count: 0, 
    total_recorded: 0, 
    clean_percentage: 0, 
    dirty_percentage: 0 
  })
  const [scanHistory, setScanHistory] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState('')
  const [showStartupAnimation, setShowStartupAnimation] = useState(true)

  // Dialog states
  const [showCleanDialog, setShowCleanDialog] = useState(false)
  const [showDirtyDialog, setShowDirtyDialog] = useState(false)
  const [showRedDialog, setShowRedDialog] = useState(false)
  const [showSwitchSession, setShowSwitchSession] = useState(false)
  const [showDashboard, setShowDashboard] = useState(false)
  const [showAdminPanel, setShowAdminPanel] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [showPreviewDialog, setShowPreviewDialog] = useState(false)

  // Form states
  const [loginForm, setLoginForm] = useState({ username: '', password: '' })
  const [signupForm, setSignupForm] = useState({ name: '', username: '', password: '' })
  const [isSignup, setIsSignup] = useState(false)
  const [studentId, setStudentId] = useState('')
  const [sessions, setSessions] = useState([])
  const [sessionToDelete, setSessionToDelete] = useState(null)
  const [csvPreview, setCsvPreview] = useState({ data: [], metadata: null })
  const [previewPage, setPreviewPage] = useState(1)

  // Admin states
  const [adminUsers, setAdminUsers] = useState([])
  const [adminSessions, setAdminSessions] = useState([])

  // Startup animation effect
  useEffect(() => {
    const animationTimer = setTimeout(() => {
      setShowStartupAnimation(false)
    }, 3000) // 3 second animation

    checkAuthStatus()

    return () => clearTimeout(animationTimer)
  }, [])

  const checkAuthStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/status`, {
        credentials: 'include'
      })
      if (response.ok) {
        const data = await response.json()
        setIsAuthenticated(data.authenticated)
        if (data.authenticated) {
          setUser(data.user)
          await initializeSession()
        }
      }
    } catch (error) {
      console.error('Auth check failed:', error)
    }
  }

  const initializeSession = async () => {
    try {
      // Check if there are any existing sessions
      const sessionsResponse = await fetch(`${API_BASE}/session/list`, {
        credentials: 'include'
      })
      if (sessionsResponse.ok) {
        const sessionsData = await sessionsResponse.json()
        if (sessionsData.sessions && sessionsData.sessions.length > 0) {
          // Auto-join the latest session
          const latestSession = sessionsData.sessions[sessionsData.sessions.length - 1]
          await switchSession(latestSession.session_id)
        }
        // If no sessions exist, user will see the create session prompt
      }
    } catch (error) {
      console.error('Failed to initialize session:', error)
    }
  }

  const showMessage = (msg, type = 'info') => {
    setMessage(msg)
    setMessageType(type)
    setTimeout(() => {
      setMessage('')
      setMessageType('')
    }, 3000)
  }

  const handleLogin = async (e) => {
    e.preventDefault()
    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' }, credentials: 'include',
        body: JSON.stringify(loginForm)
      })
      
      if (response.ok) {
        const data = await response.json()
        setIsAuthenticated(true)
        setUser(data.user)
        showMessage('Login successful!', 'success')
        await initializeSession()
      } else {
        const error = await response.json()
        showMessage(error.error, 'error')
      }
    } catch (error) {
      showMessage('Login failed', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const handleSignup = async (e) => {
    e.preventDefault()
    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/auth/signup`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' }, credentials: 'include',
        body: JSON.stringify(signupForm)
      })
      
      if (response.ok) {
        const data = await response.json()
        showMessage('Account created successfully!', 'success')
        setIsSignup(false)
        setSignupForm({ name: '', username: '', password: '' })
      } else {
        const error = await response.json()
        showMessage(error.error, 'error')
      }
    } catch (error) {
      showMessage('Signup failed', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const handleLogout = async () => {
    try {
      await fetch(`${API_BASE}/auth/logout`, { method: 'POST', credentials: 'include' })
      setIsAuthenticated(false)
      setUser(null)
      setSessionId(null)
      setSessionName('')
      setSessionStats({ 
        clean_count: 0, 
        dirty_count: 0, 
        red_count: 0, 
        combined_dirty_count: 0, 
        total_recorded: 0, 
        clean_percentage: 0, 
        dirty_percentage: 0 
      })
      setScanHistory([])
      showMessage('Logged out successfully', 'success')
    } catch (error) {
      showMessage('Logout failed', 'error')
    }
  }

  const createNewSession = async () => {
    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/session/create`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' }, credentials: 'include'
      })
      
      if (response.ok) {
        const data = await response.json()
        setSessionId(data.session_id)
        setSessionName(data.session_name)
        setSessionStats({ 
          clean_count: 0, 
          dirty_count: 0, 
          red_count: 0, 
          combined_dirty_count: 0, 
          total_recorded: 0, 
          clean_percentage: 0, 
          dirty_percentage: 0 
        })
        setScanHistory([])
        showMessage(`Session "${data.session_name}" created successfully!`, 'success')
      } else {
        const error = await response.json()
        showMessage(error.error, 'error')
      }
    } catch (error) {
      showMessage('Failed to create session', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const loadSessions = async () => {
    try {
      const response = await fetch(`${API_BASE}/session/list`)
      if (response.ok) {
        const data = await response.json()
        setSessions(data.sessions)
      }
    } catch (error) {
      showMessage('Failed to load sessions', 'error')
    }
  }

  const switchSession = async (newSessionId) => {
    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/session/switch/${newSessionId}`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' }, credentials: 'include'
      })
      
      if (response.ok) {
        const data = await response.json()
        setSessionId(data.session_id)
        setSessionName(data.session_name)
        setSessionStats({
          clean_count: data.clean_count || 0,
          dirty_count: data.dirty_count || 0,
          red_count: data.red_count || 0,
          combined_dirty_count: (data.dirty_count || 0) + (data.red_count || 0),
          total_recorded: (data.clean_count || 0) + (data.dirty_count || 0) + (data.red_count || 0),
          clean_percentage: data.clean_percentage || 0,
          dirty_percentage: data.dirty_percentage || 0
        })
        setScanHistory(data.scan_history || [])
        setShowSwitchSession(false)
        showMessage(`Switched to session "${data.session_name}"`, 'success')
      } else {
        const error = await response.json()
        showMessage(error.error, 'error')
      }
    } catch (error) {
      showMessage('Failed to switch session', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const deleteSession = async (sessionId) => {
    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/session/delete/${sessionId}`, {
        method: 'DELETE', credentials: 'include',
        headers: { 'Content-Type': 'application/json' }, credentials: 'include'
      })
      
      if (response.ok) {
        const data = await response.json()
        showMessage(data.message, 'success')
        setShowDeleteConfirm(false)
        setSessionToDelete(null)
        // Refresh sessions list
        loadSessions()
        // If we deleted the current session, clear session state
        if (sessionId === sessionId) {
          setSessionId(null)
          setSessionName('')
          setSessionStats({ 
            clean_count: 0, 
            dirty_count: 0, 
            red_count: 0, 
            combined_dirty_count: 0, 
            total_recorded: 0, 
            clean_percentage: 0, 
            dirty_percentage: 0 
          })
          setScanHistory([])
        }
      } else {
        const error = await response.json()
        showMessage(error.error, 'error')
      }
    } catch (error) {
      showMessage('Failed to delete session', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const recordPlate = async (category) => {
    if (!studentId.trim()) {
      showMessage('Please enter a student ID', 'error')
      return
    }

    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/record`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' }, credentials: 'include',
        credentials: 'include', // Include cookies for session
        body: JSON.stringify({
          student_id: studentId,
          category: category
        })
      })
      
      if (response.ok) {
        const data = await response.json()
        setSessionStats({
          clean_count: data.clean_count || 0,
          dirty_count: data.dirty_count || 0,
          red_count: data.red_count || 0,
          combined_dirty_count: (data.dirty_count || 0) + (data.red_count || 0),
          total_recorded: (data.clean_count || 0) + (data.dirty_count || 0) + (data.red_count || 0),
          clean_percentage: data.clean_percentage || 0,
          dirty_percentage: data.dirty_percentage || 0
        })
        setScanHistory(data.scan_history || [])
        setStudentId('')
        showMessage(data.message, 'success')
        
        // Close the appropriate dialog
        setShowCleanDialog(false)
        setShowDirtyDialog(false)
        setShowRedDialog(false)
      } else {
        const error = await response.json()
        showMessage(error.error, 'error')
      }
    } catch (error) {
      showMessage('Failed to record plate', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  // Startup Animation
  if (showStartupAnimation) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-amber-50 via-yellow-50 to-orange-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-bounce mb-8">
            <div className="text-8xl mb-4">🍽️</div>
          </div>
          <div className="text-4xl font-bold bg-gradient-to-r from-amber-600 to-yellow-600 bg-clip-text text-transparent mb-4">
            P.L.A.T.E.
          </div>
          <div className="text-lg text-gray-600 mb-8">
            Prevention, Logging & Assessment of Tossed Edibles
          </div>
          <div className="flex justify-center space-x-1">
            <div className="w-2 h-2 bg-amber-500 rounded-full animate-pulse"></div>
            <div className="w-2 h-2 bg-amber-500 rounded-full animate-pulse" style={{animationDelay: '0.2s'}}></div>
            <div className="w-2 h-2 bg-amber-500 rounded-full animate-pulse" style={{animationDelay: '0.4s'}}></div>
          </div>
        </div>
      </div>
    )
  }

  // Login Screen
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="text-3xl font-bold bg-gradient-to-r from-amber-600 to-yellow-600 bg-clip-text text-transparent">
              P.L.A.T.E.
            </CardTitle>
            <CardDescription>Prevention, Logging & Assessment of Tossed Edibles</CardDescription>
          </CardHeader>
          <CardContent>
            {message && (
              <div className={`mb-4 p-3 rounded-lg text-sm ${
                messageType === 'success' ? 'bg-green-100 text-green-700' :
                messageType === 'error' ? 'bg-red-100 text-red-700' :
                'bg-blue-100 text-blue-700'
              }`}>
                {message}
              </div>
            )}
            
            {!isSignup ? (
              <form onSubmit={handleLogin} className="space-y-4">
                <Input
                  type="text"
                  placeholder="Username"
                  value={loginForm.username}
                  onChange={(e) => setLoginForm({...loginForm, username: e.target.value})}
                  required
                />
                <Input
                  type="password"
                  placeholder="Password"
                  value={loginForm.password}
                  onChange={(e) => setLoginForm({...loginForm, password: e.target.value})}
                  required
                />
                <Button 
                  type="submit" 
                  className="w-full bg-gradient-to-r from-amber-500 to-yellow-500 hover:from-amber-600 hover:to-yellow-600" 
                  disabled={isLoading}
                >
                  {isLoading ? 'Logging in...' : 'Login'}
                </Button>
                <Button 
                  type="button" 
                  variant="outline" 
                  className="w-full border-amber-200 text-amber-700 hover:bg-amber-50" 
                  onClick={() => setIsSignup(true)}
                >
                  Create Account
                </Button>
              </form>
            ) : (
              <form onSubmit={handleSignup} className="space-y-4">
                <Input
                  type="text"
                  placeholder="Full Name"
                  value={signupForm.name}
                  onChange={(e) => setSignupForm({...signupForm, name: e.target.value})}
                  required
                />
                <Input
                  type="text"
                  placeholder="Username"
                  value={signupForm.username}
                  onChange={(e) => setSignupForm({...signupForm, username: e.target.value})}
                  required
                />
                <Input
                  type="password"
                  placeholder="Password"
                  value={signupForm.password}
                  onChange={(e) => setSignupForm({...signupForm, password: e.target.value})}
                  required
                />
                <Button 
                  type="submit" 
                  className="w-full bg-gradient-to-r from-amber-500 to-yellow-500 hover:from-amber-600 hover:to-yellow-600" 
                  disabled={isLoading}
                >
                  {isLoading ? 'Creating Account...' : 'Create Account'}
                </Button>
                <Button 
                  type="button" 
                  variant="outline" 
                  className="w-full border-amber-200 text-amber-700 hover:bg-amber-50" 
                  onClick={() => setIsSignup(false)}
                >
                  Back to Login
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    )
  }

  // No Session State
  if (!sessionId) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md text-center">
          <CardHeader>
            <div className="text-6xl mb-4">🍽️</div>
            <CardTitle className="text-2xl font-bold bg-gradient-to-r from-amber-600 to-yellow-600 bg-clip-text text-transparent">
              P.L.A.T.E.
            </CardTitle>
            <CardDescription>No active session found</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-gray-600">Create a new session to start tracking plate cleanliness.</p>
            <Button 
              onClick={createNewSession}
              className="w-full bg-gradient-to-r from-amber-500 to-yellow-500 hover:from-amber-600 hover:to-yellow-600"
              disabled={isLoading}
            >
              <Plus className="h-4 w-4 mr-2" />
              {isLoading ? 'Creating...' : 'Create New Session'}
            </Button>
            <Button 
              onClick={handleLogout}
              variant="outline"
              className="w-full"
            >
              Logout
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Main Application
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-amber-600 to-yellow-600 bg-clip-text text-transparent">
                P.L.A.T.E.
              </h1>
              <p className="text-sm text-gray-600">Prevention, Logging & Assessment of Tossed Edibles</p>
            </div>
            <div className="flex items-center gap-4">
              <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
                {user.name} ({user.username})
              </Badge>
              <Button 
                onClick={() => window.open('https://github.com/Antineutrino-4444/goldenplatewebsite', '_blank')}
                variant="outline" 
                size="sm"
                className="hidden sm:flex"
              >
                <Github className="h-4 w-4 mr-2" />
                GitHub
              </Button>
              <Button onClick={handleLogout} variant="outline" size="sm">
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Message Display */}
      {message && (
        <div className={`mx-4 mt-4 p-3 rounded-lg text-sm ${
          messageType === 'success' ? 'bg-green-100 text-green-700' :
          messageType === 'error' ? 'bg-red-100 text-red-700' :
          'bg-blue-100 text-blue-700'
        }`}>
          {message}
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Session Info */}
        <div className="mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Session: {sessionName}</h2>
            <p className="text-sm text-gray-600">
              Total Recorded: {sessionStats.total_recorded} | 
              Clean: {sessionStats.clean_count} ({sessionStats.clean_percentage}%) | 
              Dirty: {sessionStats.combined_dirty_count} ({sessionStats.dirty_percentage}%)
            </p>
          </div>
          <div className="flex gap-2">
            <Button onClick={() => { loadSessions(); setShowSwitchSession(true) }} variant="outline" size="sm">
              Switch Session
            </Button>
            {(user.role === 'admin' || user.role === 'superadmin') && (
              <Button onClick={() => setShowAdminPanel(true)} variant="outline" size="sm">
                <Settings className="h-4 w-4 mr-2" />
                Admin Panel
              </Button>
            )}
          </div>
        </div>

        {/* Plate Recording Buttons */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <Card className="cursor-pointer hover:shadow-lg transition-shadow border-2 border-yellow-200 hover:border-yellow-300" 
                onClick={() => setShowCleanDialog(true)}>
            <CardContent className="p-6 text-center">
              <div className="text-4xl mb-4">🥇</div>
              <h3 className="text-lg font-semibold text-yellow-700 mb-2">CLEAN PLATE</h3>
              <p className="text-sm text-gray-600">Minimal food waste</p>
              <div className="mt-4 text-2xl font-bold text-yellow-600">{sessionStats.clean_count}</div>
            </CardContent>
          </Card>

          <Card className="cursor-pointer hover:shadow-lg transition-shadow border-2 border-orange-200 hover:border-orange-300" 
                onClick={() => setShowDirtyDialog(true)}>
            <CardContent className="p-6 text-center">
              <div className="text-4xl mb-4">🍽️</div>
              <h3 className="text-lg font-semibold text-orange-700 mb-2">DIRTY PLATE</h3>
              <p className="text-sm text-gray-600">Moderate food waste</p>
              <div className="mt-4 text-2xl font-bold text-orange-600">{sessionStats.dirty_count}</div>
            </CardContent>
          </Card>

          <Card className="cursor-pointer hover:shadow-lg transition-shadow border-2 border-red-200 hover:border-red-300" 
                onClick={() => setShowRedDialog(true)}>
            <CardContent className="p-6 text-center">
              <div className="text-4xl mb-4">🍝</div>
              <h3 className="text-lg font-semibold text-red-700 mb-2">VERY DIRTY PLATE</h3>
              <p className="text-sm text-gray-600">Significant food waste</p>
              <div className="mt-4 text-2xl font-bold text-red-600">{sessionStats.red_count}</div>
            </CardContent>
          </Card>
        </div>

        {/* Additional Features */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center gap-3 mb-4">
                <Users className="h-6 w-6 text-blue-600" />
                <h3 className="text-lg font-semibold">Student Database</h3>
              </div>
              <p className="text-sm text-gray-600 mb-4">Upload and manage student data for tracking</p>
              <div className="space-y-2">
                <Button 
                  onClick={() => document.getElementById('csv-upload').click()} 
                  className="w-full" 
                  variant="outline"
                >
                  <Upload className="h-4 w-4 mr-2" />
                  Upload CSV
                </Button>
                <Button 
                  onClick={() => setShowPreviewDialog(true)} 
                  className="w-full" 
                  variant="outline"
                >
                  <Eye className="h-4 w-4 mr-2" />
                  Preview Database
                </Button>
              </div>
              <input
                id="csv-upload"
                type="file"
                accept=".csv"
                style={{ display: 'none' }}
                onChange={(e) => {
                  if (e.target.files[0]) {
                    // Handle CSV upload
                  }
                }}
              />
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center gap-3 mb-4">
                <Download className="h-6 w-6 text-green-600" />
                <h3 className="text-lg font-semibold">Export Records</h3>
              </div>
              <p className="text-sm text-gray-600 mb-4">Download food waste tracking data</p>
              <Button className="w-full bg-gradient-to-r from-amber-500 to-yellow-500 hover:from-amber-600 hover:to-yellow-600">
                <Download className="h-4 w-4 mr-2" />
                Export Food Waste Data
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center gap-3 mb-4">
                <BarChart3 className="h-6 w-6 text-purple-600" />
                <h3 className="text-lg font-semibold">Analytics</h3>
              </div>
              <p className="text-sm text-gray-600 mb-4">View detailed statistics and insights</p>
              <Button onClick={() => setShowDashboard(true)} className="w-full" variant="outline">
                <BarChart3 className="h-4 w-4 mr-2" />
                View Dashboard
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Plate Tracking History */}
        <Card>
          <CardHeader>
            <CardTitle>Plate Tracking History</CardTitle>
            <CardDescription>Recent plate cleanliness recordings</CardDescription>
          </CardHeader>
          <CardContent>
            {scanHistory.length > 0 ? (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {scanHistory.map((record, index) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="text-lg">
                        {record.category === 'CLEAN' ? '🥇' : 
                         record.category === 'DIRTY' ? '🍽️' : '🍝'}
                      </div>
                      <div>
                        <div className="font-medium">Student ID: {record.student_id}</div>
                        <div className="text-sm text-gray-600">
                          {record.category === 'CLEAN' ? 'Clean Plate' : 
                           record.category === 'DIRTY' ? 'Dirty Plate' : 'Very Dirty Plate'}
                        </div>
                      </div>
                    </div>
                    <div className="text-sm text-gray-500">
                      {new Date(record.timestamp).toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <div className="text-4xl mb-4">🍽️</div>
                <p>No plate tracking history yet</p>
                <p className="text-sm">Start recording plate cleanliness to see history here</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* All Dialogs */}
        {/* Clean Plate Dialog */}
        <Dialog open={showCleanDialog} onOpenChange={setShowCleanDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="text-yellow-600">🥇 Clean Plate Recording</DialogTitle>
              <DialogDescription>Record a clean plate with minimal food waste</DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <Input
                placeholder="Enter Student ID"
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
              />
              <div className="flex gap-2">
                <Button onClick={() => setShowCleanDialog(false)} variant="outline" className="flex-1">
                  Cancel
                </Button>
                <Button onClick={() => recordPlate('CLEAN')} className="flex-1 bg-yellow-600 hover:bg-yellow-700" disabled={isLoading}>
                  Record Clean Plate
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Dirty Plate Dialog */}
        <Dialog open={showDirtyDialog} onOpenChange={setShowDirtyDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="text-orange-600">🍽️ Dirty Plate Recording</DialogTitle>
              <DialogDescription>Record a dirty plate with moderate food waste</DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <Input
                placeholder="Enter Student ID"
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
              />
              <div className="flex gap-2">
                <Button onClick={() => setShowDirtyDialog(false)} variant="outline" className="flex-1">
                  Cancel
                </Button>
                <Button onClick={() => recordPlate('DIRTY')} className="flex-1 bg-orange-600 hover:bg-orange-700" disabled={isLoading}>
                  Record Dirty Plate
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Very Dirty Plate Dialog */}
        <Dialog open={showRedDialog} onOpenChange={setShowRedDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="text-red-600">🍝 Very Dirty Plate Recording</DialogTitle>
              <DialogDescription>Record a very dirty plate with significant food waste</DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <Input
                placeholder="Enter Student ID"
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
              />
              <div className="flex gap-2">
                <Button onClick={() => setShowRedDialog(false)} variant="outline" className="flex-1">
                  Cancel
                </Button>
                <Button onClick={() => recordPlate('RED')} className="flex-1 bg-red-600 hover:bg-red-700" disabled={isLoading}>
                  Record Very Dirty Plate
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Switch Session Dialog */}
        <Dialog open={showSwitchSession} onOpenChange={setShowSwitchSession}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Switch Session</DialogTitle>
              <DialogDescription>Select a session to switch to</DialogDescription>
            </DialogHeader>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {sessions.map((session) => (
                <div key={session.session_id} className="flex items-center justify-between p-3 border rounded-lg">
                  <div>
                    <div className="font-medium">{session.session_name}</div>
                    <div className="text-sm text-gray-500">
                      Clean: {session.clean_count || 0} | 
                      Dirty: {(session.dirty_count || 0) + (session.red_count || 0)} ({((((session.dirty_count || 0) + (session.red_count || 0)) / Math.max((session.clean_count || 0) + (session.dirty_count || 0) + (session.red_count || 0), 1)) * 100).toFixed(1)}%) | 
                      Total: {(session.clean_count || 0) + (session.dirty_count || 0) + (session.red_count || 0)}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button 
                      onClick={() => switchSession(session.session_id)} 
                      size="sm"
                      disabled={session.session_id === sessionId}
                    >
                      {session.session_id === sessionId ? 'Current' : 'Switch'}
                    </Button>
                    <Button 
                      onClick={() => {
                        setSessionToDelete(session)
                        setShowDeleteConfirm(true)
                      }} 
                      size="sm" 
                      variant="destructive"
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
            <Button onClick={() => setShowSwitchSession(false)} className="w-full">
              Close
            </Button>
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="text-red-600">Delete Session</DialogTitle>
              <DialogDescription>
                Are you sure you want to delete "{sessionToDelete?.session_name}"? This action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <div className="flex gap-2">
              <Button 
                onClick={() => setShowDeleteConfirm(false)} 
                variant="outline" 
                className="flex-1"
              >
                Cancel
              </Button>
              <Button 
                onClick={() => deleteSession(sessionToDelete?.session_id)} 
                className="flex-1 bg-red-600 hover:bg-red-700"
                disabled={isLoading}
              >
                Delete Session
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Dashboard Dialog */}
        <Dialog open={showDashboard} onOpenChange={setShowDashboard}>
          <DialogContent className="max-w-4xl">
            <DialogHeader>
              <DialogTitle>P.L.A.T.E. Analytics Dashboard</DialogTitle>
              <DialogDescription>Combined statistics for all sessions</DialogDescription>
            </DialogHeader>
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-4">
                <div className="p-4 bg-yellow-50 rounded-lg border border-yellow-200">
                  <div className="text-2xl font-bold text-yellow-600">{combinedStats.clean_count}</div>
                  <div className="text-sm text-yellow-700">Clean Plates ({combinedStats.clean_percentage}%)</div>
                </div>
                <div className="p-4 bg-red-50 rounded-lg border border-red-200">
                  <div className="text-2xl font-bold text-red-600">{combinedStats.combined_dirty_count}</div>
                  <div className="text-sm text-red-700">Dirty Plates ({combinedStats.dirty_percentage}%)</div>
                </div>
              </div>
              <div className="space-y-4">
                <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                  <div className="text-2xl font-bold text-blue-600">{combinedStats.total_recorded}</div>
                  <div className="text-sm text-blue-700">Total Recorded</div>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                  <div className="text-lg font-semibold text-gray-700">Food Waste Impact</div>
                  <div className="text-sm text-gray-600">
                    {combinedStats.dirty_percentage}% of plates had food waste
                  </div>
                </div>
              </div>
            </div>
            <Button onClick={() => setShowDashboard(false)} className="w-full">
              Close
            </Button>
          </DialogContent>
        </Dialog>

        {/* Admin Panel Dialog */}
        <Dialog open={showAdminPanel} onOpenChange={setShowAdminPanel}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="text-red-600">Admin Panel</DialogTitle>
              <DialogDescription>System administration and management</DialogDescription>
            </DialogHeader>
            <div className="space-y-6 max-h-[70vh] overflow-y-auto pr-2">
              {/* User Management */}
              <div>
                <h3 className="text-lg font-semibold mb-4">User Management</h3>
                <div className="space-y-2">
                  {adminUsers.map((adminUser) => (
                    <div key={adminUser.username} className="flex items-center justify-between p-3 border rounded-lg">
                      <div>
                        <div className="font-medium">{adminUser.name}</div>
                        <div className="text-sm text-gray-500">@{adminUser.username}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <select
                          value={adminUser.role}
                          className="px-2 py-1 border rounded text-sm"
                          onChange={(e) => {
                            // Handle role change
                          }}
                        >
                          <option value="user">User</option>
                          <option value="admin">Admin</option>
                          <option value="superadmin">Super Admin</option>
                        </select>
                        <Button size="sm" variant="destructive">
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Session Management */}
              <div>
                <h3 className="text-lg font-semibold mb-4">Session Management</h3>
                <div className="space-y-2">
                  {adminSessions.map((adminSession) => (
                    <div key={adminSession.session_id} className="flex items-center justify-between p-3 border rounded-lg">
                      <div>
                        <div className="font-medium">{adminSession.session_name}</div>
                        <div className="text-sm text-gray-500">
                          Clean: {adminSession.clean_count || 0} | 
                          Dirty: {(adminSession.dirty_count || 0) + (adminSession.red_count || 0)} | 
                          Total: {(adminSession.clean_count || 0) + (adminSession.dirty_count || 0) + (adminSession.red_count || 0)}
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => {
                          if (confirm(`Are you sure you want to delete session "${adminSession.session_name}"? This action cannot be undone.`)) {
                            deleteSession(adminSession.session_id)
                          }
                        }}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>

              <Button onClick={() => setShowAdminPanel(false)} className="w-full">
                Close
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  )
}

export default App

