import React from 'react'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { SearchableNameInput } from '@/components/SearchableNameInput.jsx'
import {
  AlertCircle,
  ArrowDownNarrowWide,
  ArrowUpNarrowWide,
  Ban,
  BarChart3,
  Building2,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  Copy,
  Download,
  FileText,
  History,
  Home,
  ListOrdered,
  LogOut,
  Plus,
  RefreshCcw,
  Shield,
  ShieldCheck,
  Sparkles,
  Trash2,
  Trophy,
  Upload,
  Users,
  Wand2,
  XCircle
} from 'lucide-react'

function MainPortal({ app }) {
  const {
    user,
    logout,
    sessionId,
    sessionName,
    sessionStats,
    sessionDashboardStats,
    dashboardWinner,
    isSessionDiscarded,
    currentDrawInfo,
    studentRecordCount,
    hasStudentRecords,
    showExportCard,
    canManageDraw,
    canOverrideWinner,
    selectedCandidate,
    selectedCandidateKey,
    setSelectedCandidateKey,
    drawSummary,
    drawSummaryLoading,
    drawActionLoading,
    discardLoading,
    isDrawCenterCollapsed,
    setIsDrawCenterCollapsed,
    drawActionComment,
    setDrawActionComment,
    facultyPick,
    facultyPickLoading,
    pickRandomFaculty,
    overrideInput,
    setOverrideInput,
    overrideCandidate,
    setOverrideCandidate,
    overrideOptions,
    loadDrawSummary,
    startDrawProcess,
    finalizeDrawWinner,
    resetDrawWinner,
    overrideDrawWinner,
    toggleDiscardState,
    showNewSessionDialog,
    setShowNewSessionDialog,
    customSessionName,
    setCustomSessionName,
    createSession,
    isLoading,
    deleteRequests,
    loadAdminData,
    setShowAdminPanel,
    showAdminPanel,
    loadSessions,
    setShowSessionsDialog,
    showSessionsDialog,
    sessions,
    switchSession,
    setSessionToDelete,
    setShowDeleteConfirm,
    showDeleteConfirm,
    deleteSession,
    sessionToDelete,
    showDashboard,
    setShowDashboard,
    showCleanDialog,
    setShowCleanDialog,
    showDirtyDialog,
    setShowDirtyDialog,
    showRedDialog,
    setShowRedDialog,
    showFacultyDialog,
    setShowFacultyDialog,
    handleCategoryClick,
    handlePopupSubmit,
    handleKeyPress,
    popupInputValue,
    setPopupInputValue,
    popupSelectedEntry,
    setPopupSelectedEntry,
    studentNames,
    teacherNames,
    sanitizeSelection,
    csvData,
    uploadCSV,
    csvPreviewLoading,
    previewCSV,
    showCsvPreview,
    setShowCsvPreview,
    csvPreviewData,
    csvPreviewPage,
    teacherPreviewLoading,
    previewTeachers,
    showTeacherPreview,
    setShowTeacherPreview,
    teacherPreviewData,
    teacherPreviewPage,
    uploadTeachers,
    exportCSV,
    exportDetailedCSV,
    scanHistory,
    allUsers,
    loadAllUsers,
    toggleAccountStatus,
    showAccountManagement,
    setShowAccountManagement,
    adminUsers,
    adminSessions,
    showDeleteRequests,
    setShowDeleteRequests,
    loadDeleteRequests,
    approveDeleteRequest,
    rejectDeleteRequest,
    generateInviteCode,
    changeUserRole,
    setUserToDelete,
    setShowUserDeleteConfirm,
    showUserDeleteConfirm,
    userToDelete,
    deleteUserAccount,
    houseStats,
    houseStatsLoading,
    houseSortBy,
    setHouseSortBy,
    loadHouseStats
  } = app

  const formatSchoolNameWithCode = (school) => {
    if (!school?.name) {
      return null
    }
    const code = (school.code ?? school.slug ?? '').trim()
    return code ? `${school.name} (Code: ${code})` : school.name
  }

  const userSchoolLabel = formatSchoolNameWithCode(user?.school)
  const deleteRequestsCount = deleteRequests.length

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-amber-600 to-yellow-600 bg-clip-text text-transparent">
                PLATE
              </h1>
              <p className="text-sm text-gray-600">Prevention, Logging & Assessment of Tossed Edibles</p>
            </div>
            <div className="flex items-center gap-4">
              <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
                {user.name} ({user.username})
              </Badge>
              {userSchoolLabel && (
                <Badge variant="secondary" className="flex items-center gap-1 bg-blue-50 text-blue-700 border-blue-200">
                  <Building2 className="h-3.5 w-3.5" />
                  {userSchoolLabel}
                </Badge>
              )}
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

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {!sessionId ? (
          <div className="text-center py-16">
            <div className="max-w-md mx-auto">
              <div className="mb-8">
                <div className="text-6xl mb-4">🍽️</div>
                <h2 className="text-2xl font-bold text-gray-900 mb-2">No Active Session</h2>
                <p className="text-gray-600 mb-6">
                  Create a new session to start tracking plate cleanliness and food waste data.
                </p>
              </div>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Button
                  onClick={() => createSession('')}
                  className="bg-amber-600 hover:bg-amber-700 text-white px-8 py-3 text-lg"
                  size="lg"
                  disabled={isLoading}
                >
                  <Plus className="h-5 w-5 mr-2" />
                  {isLoading ? 'Creating...' : 'Create New Session'}
                </Button>
                {['admin', 'superadmin'].includes(user?.role) && (
                  <Button
                    onClick={() => {
                      setShowAdminPanel(true)
                      loadAdminData()
                    }}
                    className="relative bg-red-600 hover:bg-red-700 text-white px-8 py-3 text-lg"
                    size="lg"
                    disabled={isLoading}
                  >
                    <Shield className="h-5 w-5 mr-2" />
                    Admin Panel
                    {deleteRequestsCount > 0 && (
                      <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs rounded-full px-2 py-0.5">
                        {deleteRequestsCount}
                      </span>
                    )}
                  </Button>
                )}
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="mb-6 text-center">
              <div className="text-lg font-medium text-gray-900">
                Session: {sessionName}
              </div>
              <div className="text-sm text-gray-500">
                Student Total: {sessionStats.clean_count + sessionStats.dirty_count + sessionStats.red_count}
              </div>
              <div className="text-sm text-gray-500">
                Faculty Clean: {sessionStats.faculty_clean_count}
              </div>
              {isSessionDiscarded && (
                <div className="mt-2 flex justify-center">
                  <Badge variant="destructive" className="uppercase tracking-wide">Discarded from draw</Badge>
                </div>
              )}
              <div className="mt-3 text-sm text-gray-600">
                {currentDrawInfo?.winner ? (
                  <div className="space-y-1">
                    <div>
                      Current Winner:{' '}
                      <span className="font-semibold">{currentDrawInfo.winner.display_name}</span>
                      {currentDrawInfo.finalized ? ' (Finalized)' : ' (Pending Finalization)'}
                    </div>
                    {currentDrawInfo.winner_timestamp && (
                      <div className="text-xs text-gray-500 flex items-center justify-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(currentDrawInfo.winner_timestamp).toLocaleString()}
                      </div>
                    )}
                  </div>
                ) : (
                  <span className="text-gray-500">No winner selected yet.</span>
                )}
              </div>
            </div>

            <div className="flex flex-wrap gap-2 mb-6 justify-center">
              {user?.role !== 'guest' && (
                <Button onClick={() => setShowNewSessionDialog(true)} className="bg-blue-600 hover:bg-blue-700">
                  <Plus className="h-4 w-4 mr-2" />
                  New Session
                </Button>
              )}
              <Button onClick={() => { loadSessions(); setShowSessionsDialog(true) }} className="bg-orange-600 hover:bg-orange-700">
                <Users className="h-4 w-4 mr-2" />
                Switch Session
              </Button>
              <Button
                onClick={() => {
                  if (['admin', 'superadmin'].includes(user?.role)) {
                    loadAdminData()
                  }
                  setShowDashboard(true)
                }}
                className="bg-purple-600 hover:bg-purple-700"
              >
                <BarChart3 className="h-4 w-4 mr-2" />
                Dashboard
              </Button>
              {['admin', 'superadmin'].includes(user.role) && (
                <Button
                  onClick={() => { loadAdminData(); setShowAdminPanel(true) }}
                  className="relative bg-red-600 hover:bg-red-700"
                >
                  <Shield className="h-4 w-4 mr-2" />
                  Admin Panel
                  {deleteRequestsCount > 0 && (
                    <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs rounded-full px-2 py-0.5">
                      {deleteRequestsCount}
                    </span>
                  )}
                </Button>
              )}
            </div>

            <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Upload className="h-5 w-5" />
                    Student Database
                  </CardTitle>
                  <CardDescription>
                    Upload CSV with student data for food waste tracking (Student ID, Last, Preferred, Grade, Advisor, House, Clan)
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {!['admin', 'superadmin'].includes(user?.role) ? (
                    <Alert className="border-blue-200 bg-blue-50">
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription className="text-blue-800">
                        CSV upload is restricted to admin and super admin users only.
                      </AlertDescription>
                    </Alert>
                  ) : (
                    <Input
                      type="file"
                      accept=".csv"
                      onChange={(e) => e.target.files[0] && uploadCSV(e.target.files[0])}
                      className="mb-4"
                    />
                  )}
                  {['admin', 'superadmin'].includes(user?.role) && (
                    <div className="flex gap-2 mb-4">
                      <Button
                        onClick={() => previewCSV(1)}
                        variant="outline"
                        className="flex-1"
                        disabled={csvPreviewLoading}
                      >
                        <FileText className="h-4 w-4 mr-2" />
                        {csvPreviewLoading ? 'Loading...' : 'Preview Database'}
                      </Button>
                    </div>
                  )}
                  {csvData && (
                    <div className="text-sm text-green-600">
                      ✓ {csvData.rows_count} students loaded
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Users className="h-5 w-5" />
                    Teacher Database
                  </CardTitle>
                  <CardDescription>
                    Upload teacher list for faculty clean plate tracking (one teacher name per line, e.g., "Smith, J")
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {!['admin', 'superadmin'].includes(user?.role) ? (
                    <Alert className="border-blue-200 bg-blue-50">
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription className="text-blue-800">
                        Teacher list upload is restricted to admin and super admin users only.
                      </AlertDescription>
                    </Alert>
                  ) : (
                    <Input
                      type="file"
                      accept=".csv,.txt"
                      onChange={(e) => e.target.files[0] && uploadTeachers(e.target.files[0])}
                      className="mb-4"
                    />
                  )}
                  {['admin', 'superadmin'].includes(user?.role) && (
                    <div className="flex gap-2 mb-4">
                      <Button
                        onClick={() => previewTeachers(1)}
                        variant="outline"
                        className="flex-1"
                        disabled={teacherPreviewLoading}
                      >
                        <FileText className="h-4 w-4 mr-2" />
                        {teacherPreviewLoading ? 'Loading...' : 'Preview Teacher List'}
                      </Button>
                    </div>
                  )}
                  {teacherNames.length > 0 && (
                    <div className="text-sm text-green-600">
                      ✓ {teacherNames.length} teachers loaded
                    </div>
                  )}
                </CardContent>
              </Card>

              {showExportCard && (
                <div className="flex flex-col gap-4 lg:row-span-2">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Download className="h-5 w-5" />
                        Export Food Waste Data
                      </CardTitle>
                      <CardDescription>
                        Download plate cleanliness records by category (Clean, Dirty Count, Very Dirty, Faculty Clean)
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-col gap-2">
                        <Button onClick={exportCSV} className="w-full bg-amber-600 hover:bg-amber-700">
                          <Download className="h-4 w-4 mr-2" />
                          Export Food Waste Data
                        </Button>
                        <Button onClick={exportDetailedCSV} variant="outline" className="w-full">
                          <FileText className="h-4 w-4 mr-2" />
                          Export Detailed Record List
                        </Button>
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="flex-1 flex flex-col">
                    <CardHeader>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <CardTitle className="flex items-center gap-2">
                          <Home className="h-5 w-5" />
                          House Data
                        </CardTitle>
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-gray-500">Sort by:</span>
                          <div className="flex border rounded-lg overflow-hidden">
                            <button
                              onClick={() => setHouseSortBy('count')}
                              className={`px-3 py-1.5 text-sm flex items-center gap-1 transition-colors ${
                                houseSortBy === 'count'
                                  ? 'bg-teal-600 text-white'
                                  : 'bg-white text-gray-700 hover:bg-gray-50'
                              }`}
                            >
                              <ArrowDownNarrowWide className="h-3.5 w-3.5" />
                              Count
                            </button>
                            <button
                              onClick={() => setHouseSortBy('percentage')}
                              className={`px-3 py-1.5 text-sm flex items-center gap-1 transition-colors ${
                                houseSortBy === 'percentage'
                                  ? 'bg-teal-600 text-white'
                                  : 'bg-white text-gray-700 hover:bg-gray-50'
                              }`}
                            >
                              <ArrowUpNarrowWide className="h-3.5 w-3.5" />
                              Clean Rate
                            </button>
                          </div>
                          <Button
                            onClick={() => loadHouseStats({ silent: false })}
                            variant="outline"
                            size="sm"
                          >
                            <RefreshCcw className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                      <CardDescription>
                        House ranking statistics for the current session
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="flex-1 overflow-y-auto">
                      {!sessionId ? (
                        <div className="py-8 text-center text-gray-500">
                          No active session selected. Switch to a session to view house data.
                        </div>
                      ) : houseStatsLoading ? (
                        <div className="py-8 text-center text-gray-500">
                          Loading house statistics...
                        </div>
                      ) : !houseStats?.has_house_data ? (
                        <div className="py-8 text-center text-gray-500">
                          <Home className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                          <p className="text-lg font-medium">No House Data Available</p>
                          <p className="text-sm mt-2">
                            {houseStats?.message || 'The student database does not contain house information.'}
                          </p>
                        </div>
                      ) : (
                        <div className="space-y-4">
                          <div className="text-sm text-gray-500">
                            Total records with house data: <span className="font-medium">{houseStats.total_records_with_house}</span>
                          </div>
                          <div className="space-y-2">
                            {(houseStats.house_stats || [])
                              .slice()
                              .sort((a, b) => {
                                if (houseSortBy === 'percentage') {
                                  return b.clean_rate - a.clean_rate
                                }
                                return b.total_count - a.total_count
                              })
                              .map((house, index) => (
                                <div
                                  key={house.house}
                                  className="flex items-center justify-between p-4 border rounded-lg bg-white shadow-sm"
                                >
                                  <div className="flex items-center gap-4">
                                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-teal-100 text-teal-700 font-semibold text-sm">
                                      #{index + 1}
                                    </div>
                                    <div>
                                      <div className="font-semibold text-gray-900">{house.house}</div>
                                      <div className="text-sm text-gray-500">
                                        Clean: {house.clean_count} • Very Dirty: {house.red_count}
                                      </div>
                                    </div>
                                  </div>
                                  <div className="text-right">
                                    <div className="text-2xl font-bold text-emerald-600">
                                      {houseSortBy === 'percentage' ? `${house.clean_rate}%` : house.total_count}
                                    </div>
                                    <div className="text-xs text-gray-500">
                                      {houseSortBy === 'percentage' ? `${house.total_count} total` : `${house.clean_rate}% clean rate`}
                                    </div>
                                    <div className="text-xs text-gray-500">
                                      {house.percentage}% of all records
                                    </div>
                                  </div>
                                </div>
                              ))}
                          </div>
                          {(houseStats.house_stats || []).length === 0 && (
                            <div className="py-8 text-center text-gray-500">
                              No house data recorded in this session yet.
                            </div>
                          )}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>
              )}

              <Card
                id="draw-center-section"
                className={`${showExportCard ? '' : 'lg:col-span-2'}`}
              >
                <CardHeader>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <CardTitle className="flex items-center gap-2">
                      <Trophy className="h-5 w-5" />
                      Draw Center
                    </CardTitle>
                    <div className="flex items-center gap-2">
                        <Button
                          onClick={() => loadDrawSummary({ silent: false })}
                          variant="outline"
                          size="sm"
                          disabled={drawSummaryLoading}
                        >
                          <RefreshCcw className="h-4 w-4 mr-2" />
                          Refresh
                        </Button>
                        <Button
                          onClick={() => setIsDrawCenterCollapsed((prev) => !prev)}
                          variant="outline"
                          size="sm"
                        >
                          {isDrawCenterCollapsed ? (
                            <>
                              <ChevronDown className="h-4 w-4 mr-2" />
                              Expand
                            </>
                          ) : (
                            <>
                              <ChevronUp className="h-4 w-4 mr-2" />
                              Collapse
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                    {!isDrawCenterCollapsed && (
                      <>
                        <CardDescription>
                          Review ticket standings and manage the draw for this session.
                        </CardDescription>
                        {drawSummary?.generated_at && (
                          <div className="text-xs text-gray-500">
                            Updated {new Date(drawSummary.generated_at).toLocaleString()}
                          </div>
                        )}
                      </>
                    )}
                  </CardHeader>
                  {!isDrawCenterCollapsed ? (
                    <CardContent>
                      {drawSummaryLoading ? (
                        <div className="py-8 text-center text-gray-500">Loading draw summary...</div>
                      ) : drawSummary ? (
                        <div className="space-y-6">
                          {isSessionDiscarded && (
                            <Alert variant="destructive">
                              <Ban className="h-4 w-4" />
                              <AlertDescription>
                                This session is currently discarded from draw calculations. Restore it to include ticket updates.
                              </AlertDescription>
                            </Alert>
                          )}
                          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                              <div className="text-sm text-gray-500">Total tickets</div>
                              <div className="text-2xl font-semibold">
                                {Number(drawSummary.total_tickets ?? 0).toFixed(2)}
                              </div>
                            </div>
                            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                              <div className="text-sm text-gray-500">Eligible students</div>
                              <div className="text-2xl font-semibold">
                                {drawSummary.eligible_count ?? 0}
                              </div>
                            </div>
                            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                              <div className="text-sm text-gray-500">Excluded records</div>
                              <div className="text-2xl font-semibold">
                                {drawSummary.excluded_records ?? 0}
                              </div>
                            </div>
                            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                              <div className="text-sm text-gray-500">Winner status</div>
                              <div className="text-2xl font-semibold">
                                {currentDrawInfo?.finalized ? 'Finalized' : 'Pending'}
                              </div>
                            </div>
                          </div>
                          <div className="flex flex-wrap items-center gap-3">
                            <Button
                              onClick={startDrawProcess}
                              className="bg-emerald-600 hover:bg-emerald-700"
                              disabled={
                                drawActionLoading ||
                                !canManageDraw ||
                                user?.role === 'guest' ||
                                isSessionDiscarded ||
                                !hasStudentRecords ||
                                (drawSummary?.total_tickets ?? 0) <= 0
                              }
                            >
                              <Wand2 className="h-4 w-4 mr-2" />
                              Start Draw
                            </Button>
                            <Button
                              onClick={finalizeDrawWinner}
                              variant="outline"
                              disabled={
                                drawActionLoading ||
                                !canManageDraw ||
                                user?.role === 'guest' ||
                                !currentDrawInfo?.winner ||
                                currentDrawInfo.finalized
                              }
                            >
                              <CheckCircle className="h-4 w-4 mr-2" />
                              Finalize Winner
                            </Button>
                            <Button
                              onClick={resetDrawWinner}
                              variant="outline"
                              disabled={
                                drawActionLoading ||
                                !canManageDraw ||
                                user?.role === 'guest' ||
                                !currentDrawInfo?.winner
                              }
                            >
                              <RefreshCcw className="h-4 w-4 mr-2" />
                              Reset Draw
                            </Button>
                          </div>
                          <div className="flex flex-col gap-1">
                            <Label htmlFor="draw-action-comment" className="text-xs text-gray-600">
                              Action comment (optional)
                            </Label>
                            <Input
                              id="draw-action-comment"
                              value={drawActionComment}
                              onChange={(event) => setDrawActionComment(event.target.value)}
                              placeholder="Add context for this draw action"
                            />
                            <p className="text-xs text-gray-500">
                              The note is saved to the draw history when you start, finalize, reset, or override.
                            </p>
                          </div>
                          <div className="flex w-full flex-col gap-2 rounded-lg border border-gray-200 bg-white p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
                            <div>
                              <div className="text-sm text-gray-500">Random Faculty Picker</div>
                              <div className="text-lg font-semibold">
                                {facultyPick?.display_name || 'No faculty selected yet'}
                              </div>
                              {facultyPick?.recorded_at && (
                                <div className="text-xs text-gray-500">
                                  Recorded at {new Date(facultyPick.recorded_at).toLocaleString()}
                                </div>
                              )}
                            </div>
                            <Button
                              onClick={pickRandomFaculty}
                              variant="outline"
                              disabled={
                                facultyPickLoading ||
                                user?.role === 'guest' ||
                                isSessionDiscarded ||
                                (sessionStats.faculty_clean_count ?? 0) <= 0 ||
                                !sessionId
                              }
                            >
                              <Sparkles className="h-4 w-4 mr-2" />
                              Pick Faculty Name
                            </Button>
                          </div>
                          {canOverrideWinner && (
                            <div className="flex w-full flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
                              <div className="w-full sm:max-w-xs">
                                <SearchableNameInput
                                  placeholder="Search student (name or ID)"
                                  value={overrideInput}
                                  onChange={(value, meta) => {
                                    setOverrideInput(value)
                                    if (!meta || meta.source !== 'selection') {
                                      setOverrideCandidate(null)
                                    }
                                  }}
                                  onSelectName={(candidate) => {
                                    if (candidate) {
                                      const sanitized = sanitizeSelection(candidate)
                                      setOverrideCandidate(sanitized)
                                      if (sanitized?.key && drawSummary?.candidates?.some(entry => entry.key === sanitized.key)) {
                                        setSelectedCandidateKey(sanitized.key)
                                      }
                                    }
                                  }}
                                  onKeyPress={(e) => {
                                    if (e.key === 'Enter') {
                                      e.preventDefault()
                                      overrideDrawWinner()
                                    }
                                  }}
                                  names={overrideOptions}
                                  className="w-full"
                                />
                              </div>
                              <Button
                                onClick={overrideDrawWinner}
                                variant="outline"
                                disabled={
                                  drawActionLoading ||
                                  user?.role === 'guest' ||
                                  !overrideInput.trim() ||
                                  !hasStudentRecords
                                }
                              >
                                <ShieldCheck className="h-4 w-4 mr-2" />
                                Override Winner
                              </Button>
                              <Button
                                onClick={() => toggleDiscardState(!isSessionDiscarded)}
                                variant={isSessionDiscarded ? 'default' : 'outline'}
                                disabled={discardLoading || user?.role === 'guest'}
                              >
                                <Ban className="h-4 w-4 mr-2" />
                                {isSessionDiscarded ? 'Restore Session' : 'Discard Session'}
                              </Button>
                            </div>
                          )}
                          <div className="grid gap-4 lg:grid-cols-2">
                            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                              <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                                <Trophy className="h-4 w-4" />
                                Current Winner
                              </div>
                              <div className="mt-3 text-sm">
                                {currentDrawInfo?.winner ? (
                                  <div className="space-y-2">
                                    <div className="text-lg font-semibold">{currentDrawInfo.winner.display_name}</div>
                                    {currentDrawInfo.winner.student_identifier && (
                                      <div className="text-xs text-gray-500">Student ID: {currentDrawInfo.winner.student_identifier}</div>
                                    )}
                                    <div className="flex flex-wrap gap-2 text-xs text-gray-500">
                                      {currentDrawInfo.winner.grade && <span>Grade: {currentDrawInfo.winner.grade}</span>}
                                      {currentDrawInfo.winner.house && <span>House: {currentDrawInfo.winner.house}</span>}
                                      {currentDrawInfo.winner.clan && <span>Clan: {currentDrawInfo.winner.clan}</span>}
                                    </div>
                                    <div className="flex items-center gap-1 text-xs text-gray-500">
                                      <Clock className="h-3 w-3" />
                                      {currentDrawInfo.winner_timestamp ? new Date(currentDrawInfo.winner_timestamp).toLocaleString() : 'Time not recorded'}
                                    </div>
                                    <div className="text-xs text-gray-500">
                                      Tickets at selection: {Number(currentDrawInfo.tickets_at_selection ?? 0).toFixed(2)} • Chance: {Number(currentDrawInfo.probability_at_selection ?? 0).toFixed(2)}%
                                    </div>
                                    <div className="text-xs">
                                      Status:{' '}
                                      <Badge variant={currentDrawInfo.finalized ? 'default' : 'outline'}>
                                        {currentDrawInfo.finalized ? 'Finalized' : 'Awaiting Finalization'}
                                      </Badge>
                                    </div>
                                  </div>
                                ) : (
                                  <div className="text-sm text-gray-500">No winner selected yet.</div>
                                )}
                              </div>
                            </div>
                            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                              <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                                <ListOrdered className="h-4 w-4" />
                                Top Candidates
                              </div>
                              <div className="mt-3">
                                {drawSummary.top_candidates && drawSummary.top_candidates.length > 0 ? (
                                  <div className="space-y-2">
                                    {drawSummary.top_candidates.map((candidate, index) => {
                                      const isActive = selectedCandidateKey === candidate.key
                                      return (
                                        <button
                                          key={candidate.key}
                                          type="button"
                                          onClick={() => setSelectedCandidateKey(candidate.key)}
                                          className={`flex w-full items-center justify-between rounded border px-3 py-2 text-left transition ${
                                            isActive ? 'border-emerald-500 bg-emerald-50' : 'border-gray-200 hover:bg-gray-50'
                                          }`}
                                        >
                                          <div>
                                            <div className="font-medium">{candidate.display_name}</div>
                                            <div className="text-xs text-gray-500">
                                              Tickets: {Number(candidate.tickets ?? 0).toFixed(2)} • Chance: {Number(candidate.probability ?? 0).toFixed(2)}%
                                            </div>
                                          </div>
                                          <Badge variant={isActive ? 'default' : 'outline'}>#{index + 1}</Badge>
                                        </button>
                                      )
                                    })}
                                  </div>
                                ) : (
                                  <div className="text-sm text-gray-500">No eligible students yet.</div>
                                )}
                              </div>
                            </div>
                          </div>
                          <div className="grid gap-4 lg:grid-cols-2">
                            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                              <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                                <Users className="h-4 w-4" />
                                Selected Candidate Details
                              </div>
                              <div className="mt-3 text-sm">
                                {selectedCandidate ? (
                                  <div className="space-y-3">
                                    <div>
                                      <div className="text-lg font-semibold">{selectedCandidate.display_name}</div>
                                      {selectedCandidate.student_identifier && (
                                        <div className="text-xs text-gray-500">Student ID: {selectedCandidate.student_identifier}</div>
                                      )}
                                    </div>
                                    <div className="grid grid-cols-1 gap-1 text-xs text-gray-600 sm:grid-cols-2">
                                      {selectedCandidate.grade && <span>Grade: {selectedCandidate.grade}</span>}
                                      {selectedCandidate.advisor && <span>Advisor: {selectedCandidate.advisor}</span>}
                                      {selectedCandidate.house && <span>House: {selectedCandidate.house}</span>}
                                      {selectedCandidate.clan && <span>Clan: {selectedCandidate.clan}</span>}
                                    </div>
                                    <div className="text-xs text-gray-600">
                                      Tickets: {Number(selectedCandidate.tickets ?? 0).toFixed(2)} • Chance: {Number(selectedCandidate.probability ?? 0).toFixed(2)}%
                                    </div>
                                  </div>
                                ) : (
                                  <div className="text-sm text-gray-500">Select a student to see their ticket details and student ID.</div>
                                )}
                              </div>
                            </div>
                            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                              <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                                <History className="h-4 w-4" />
                                Draw History
                              </div>
                              <div className="mt-3 text-sm">
                                {drawSummary?.history && drawSummary.history.length > 0 ? (
                                  <div className="max-h-48 space-y-2 overflow-y-auto pr-1 text-xs text-gray-600">
                                    {drawSummary.history
                                      .slice()
                                      .reverse()
                                      .map((entry, index) => (
                                        <div key={`${entry.timestamp}-${index}`} className="rounded border p-2">
                                          <div className="font-semibold uppercase">{entry.event_type.replace(/_/g, ' ')}</div>
                                          <div>When: {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : 'N/A'}</div>
                                          {entry.student_name && <div>Student: {entry.student_name}</div>}
                                          {entry.tickets !== null && entry.tickets !== undefined && (
                                            <div>Student tickets: {Number(entry.tickets ?? 0).toFixed(2)}</div>
                                          )}
                                          {entry.probability !== null && entry.probability !== undefined && (
                                            <div>Probability: {Number(entry.probability ?? 0).toFixed(2)}%</div>
                                          )}
                                          {entry.pool_size !== null && entry.pool_size !== undefined && (
                                            <div>Eligible pool: {entry.pool_size}</div>
                                          )}
                                          {entry.created_by && <div>By: {entry.created_by}</div>}
                                          {entry.comment && <div className="text-gray-700">Comment: {entry.comment}</div>}
                                        </div>
                                      ))}
                                  </div>
                                ) : (
                                  <div className="text-sm text-gray-500">No draw activity recorded yet.</div>
                                )}
                              </div>
                            </div>
                          </div>
                          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                            <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                              <ListOrdered className="h-4 w-4" />
                              Eligible Students
                            </div>
                            <div className="mt-3">
                              {drawSummary.candidates && drawSummary.candidates.length > 0 ? (
                                <div className="max-h-56 space-y-1 overflow-y-auto pr-1">
                                  {drawSummary.candidates.map((candidate) => {
                                    const isActive = selectedCandidateKey === candidate.key
                                    return (
                                      <button
                                        key={candidate.key}
                                        type="button"
                                        onClick={() => setSelectedCandidateKey(candidate.key)}
                                        className={`flex w-full items-center justify-between rounded border px-3 py-2 text-left transition ${
                                          isActive ? 'border-emerald-500 bg-emerald-50' : 'border-gray-200 hover:bg-gray-50'
                                        }`}
                                      >
                                        <div>
                                          <div className="font-medium">{candidate.display_name}</div>
                                          <div className="flex flex-wrap gap-2 text-xs text-gray-500">
                                            {candidate.student_identifier && <span>ID: {candidate.student_identifier}</span>}
                                            <span>Tickets: {Number(candidate.tickets ?? 0).toFixed(2)}</span>
                                            <span>Chance: {Number(candidate.probability ?? 0).toFixed(2)}%</span>
                                          </div>
                                        </div>
                                        {candidate.key === currentDrawInfo?.winner?.key && (
                                          <Badge variant="outline" className="text-xs">Winner</Badge>
                                        )}
                                      </button>
                                    )
                                  })}
                                </div>
                              ) : (
                                <div className="text-sm text-gray-500">No eligible students yet.</div>
                              )}
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="py-8 text-center text-gray-500">
                          No draw data available yet. Record plate data to generate tickets.
                        </div>
                      )}
                      </CardContent>
                    ) : null}
                  </Card>

              {!showExportCard && (
                <Card className="lg:col-span-2">
                  <CardHeader>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <CardTitle className="flex items-center gap-2">
                        <Home className="h-5 w-5" />
                        House Data
                      </CardTitle>
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-500">Sort by:</span>
                        <div className="flex border rounded-lg overflow-hidden">
                          <button
                            onClick={() => setHouseSortBy('count')}
                            className={`px-3 py-1.5 text-sm flex items-center gap-1 transition-colors ${
                              houseSortBy === 'count'
                                ? 'bg-teal-600 text-white'
                                : 'bg-white text-gray-700 hover:bg-gray-50'
                            }`}
                          >
                            <ArrowDownNarrowWide className="h-3.5 w-3.5" />
                            Count
                          </button>
                          <button
                            onClick={() => setHouseSortBy('percentage')}
                            className={`px-3 py-1.5 text-sm flex items-center gap-1 transition-colors ${
                              houseSortBy === 'percentage'
                                ? 'bg-teal-600 text-white'
                                : 'bg-white text-gray-700 hover:bg-gray-50'
                            }`}
                          >
                            <ArrowUpNarrowWide className="h-3.5 w-3.5" />
                            Clean Rate
                          </button>
                        </div>
                        <Button
                          onClick={() => loadHouseStats({ silent: false })}
                          variant="outline"
                          size="sm"
                        >
                          <RefreshCcw className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                    <CardDescription>
                      House ranking statistics for the current session
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {!sessionId ? (
                      <div className="py-8 text-center text-gray-500">
                        No active session selected. Switch to a session to view house data.
                      </div>
                    ) : houseStatsLoading ? (
                      <div className="py-8 text-center text-gray-500">
                        Loading house statistics...
                      </div>
                    ) : !houseStats?.has_house_data ? (
                      <div className="py-8 text-center text-gray-500">
                        <Home className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                        <p className="text-lg font-medium">No House Data Available</p>
                        <p className="text-sm mt-2">
                          {houseStats?.message || 'The student database does not contain house information.'}
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <div className="text-sm text-gray-500">
                          Total records with house data: <span className="font-medium">{houseStats.total_records_with_house}</span>
                        </div>
                        <div className="space-y-2">
                          {(houseStats.house_stats || [])
                            .slice()
                            .sort((a, b) => {
                              if (houseSortBy === 'percentage') {
                                return b.clean_rate - a.clean_rate
                              }
                              return b.total_count - a.total_count
                            })
                            .map((house, index) => (
                              <div
                                key={house.house}
                                className="flex items-center justify-between p-4 border rounded-lg bg-white shadow-sm"
                              >
                                <div className="flex items-center gap-4">
                                  <div className="flex items-center justify-center w-8 h-8 rounded-full bg-teal-100 text-teal-700 font-semibold text-sm">
                                    #{index + 1}
                                  </div>
                                  <div>
                                    <div className="font-semibold text-gray-900">{house.house}</div>
                                    <div className="text-sm text-gray-500">
                                      Clean: {house.clean_count} • Very Dirty: {house.red_count}
                                    </div>
                                  </div>
                                </div>
                                <div className="text-right">
                                  <div className="text-2xl font-bold text-emerald-600">
                                    {houseSortBy === 'percentage' ? `${house.clean_rate}%` : house.total_count}
                                  </div>
                                  <div className="text-xs text-gray-500">
                                    {houseSortBy === 'percentage' ? `${house.total_count} total` : `${house.clean_rate}% clean rate`}
                                  </div>
                                  <div className="text-xs text-gray-500">
                                    {house.percentage}% of all records
                                  </div>
                                </div>
                              </div>
                            ))}
                        </div>
                        {(houseStats.house_stats || []).length === 0 && (
                          <div className="py-8 text-center text-gray-500">
                            No house data recorded in this session yet.
                          </div>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
                </div>

            <div className="mt-8 space-y-4">
              {user?.role === 'guest' && (
                <Alert className="border-blue-200 bg-blue-50">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription className="text-blue-800">
                    You are viewing as a guest. Recording is not available. Please sign up to record plate data.
                  </AlertDescription>
                </Alert>
              )}

              <Button
                onClick={() => handleCategoryClick('clean')}
                className="w-full h-20 text-xl font-semibold bg-yellow-500 hover:bg-yellow-600 text-white shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading || user?.role === 'guest'}
              >
                🥇 CLEAN PLATE
                <br />
                <span className="text-sm opacity-90">({sessionStats.clean_count} recorded)</span>
              </Button>

              <Button
                onClick={() => handleCategoryClick('faculty')}
                className="w-full h-20 text-xl font-semibold bg-green-500 hover:bg-green-600 text-white shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading || user?.role === 'guest'}
              >
                🧑‍🏫 FACULTY CLEAN
                <br />
                <span className="text-sm opacity-90">({sessionStats.faculty_clean_count} recorded)</span>
              </Button>

              <Button
                onClick={() => handleCategoryClick('dirty')}
                className="w-full h-20 text-xl font-semibold bg-orange-500 hover:bg-orange-600 text-white shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading || user?.role === 'guest'}
              >
                🍽️ DIRTY PLATE COUNT
                <br />
                <span className="text-sm opacity-90">({sessionStats.dirty_count} total)</span>
              </Button>

              <Button
                onClick={() => handleCategoryClick('red')}
                className="w-full h-20 text-xl font-semibold bg-red-500 hover:bg-red-600 text-white shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading || user?.role === 'guest'}
              >
                🍝 VERY DIRTY PLATE
                <br />
                <span className="text-sm opacity-90">({sessionStats.red_count} recorded)</span>
              </Button>
            </div>

            <div className="mt-8">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5" />
                    Plate Tracking History
                  </CardTitle>
                  <CardDescription>
                    Recent plate cleanliness entries for this session
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {scanHistory.length > 0 ? (
                    <div className="space-y-2 max-h-60 overflow-y-auto">
                      {scanHistory.map((record, index) => (
                        <div key={index} className="flex items-center justify-between p-2 border rounded-lg text-sm">
                          <div className="flex items-center gap-4">
                            <div className="text-gray-500">
                              {new Date(record.timestamp).toLocaleTimeString()}
                            </div>
                            <div className="font-medium">
                              {record.name}
                            </div>
                          </div>
                          <div className={`px-2 py-1 rounded text-xs font-medium ${
                            record.category === 'CLEAN' ? 'bg-yellow-100 text-yellow-800' :
                            record.category === 'DIRTY' ? 'bg-orange-100 text-orange-800' :
                            record.category === 'FACULTY' ? 'bg-green-100 text-green-800' :
                            'bg-red-100 text-red-800'
                          }`}>
                            {record.category === 'CLEAN' ? '🥇 CLEAN' :
                             record.category === 'DIRTY' ? '🍽️ DIRTY' :
                             record.category === 'FACULTY' ? '🧑‍🏫 FACULTY CLEAN' :
                             '🍝 VERY DIRTY'}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center text-gray-500 py-4">
                      No plate entries recorded yet
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </>
        )}
      </div>

      <Dialog open={showCleanDialog} onOpenChange={setShowCleanDialog}>
        <DialogContent dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle className="text-yellow-600">🥇 Record as CLEAN PLATE</DialogTitle>
            <DialogDescription>
              Enter Student ID or Name for clean plate tracking
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <SearchableNameInput
              placeholder="Student ID or Name (e.g., 12345 or John Smith)"
              value={popupInputValue}
              onChange={(value, meta) => {
                setPopupInputValue(value)
                if (!meta || meta.source !== 'selection') {
                  setPopupSelectedEntry(null)
                }
              }}
              onSelectName={(entry) => {
                const sanitized = sanitizeSelection(entry)
                setPopupSelectedEntry(sanitized)
              }}
              onKeyPress={(e) => handleKeyPress(e, 'clean')}
              names={studentNames}
              autoFocus
            />
            <div className="flex gap-2">
              <Button onClick={() => { setShowCleanDialog(false); setPopupSelectedEntry(null) }} variant="outline" className="flex-1">
                Cancel
              </Button>
              <Button
                onClick={() => handlePopupSubmit('clean')}
                className="flex-1 bg-yellow-500 hover:bg-yellow-600"
                disabled={isLoading}
              >
                Record as CLEAN PLATE
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showDirtyDialog} onOpenChange={setShowDirtyDialog}>
        <DialogContent dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle className="text-orange-600">🍽️ Add DIRTY PLATE</DialogTitle>
            <DialogDescription>
              Increase the dirty plate counter without recording a name
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-gray-600">
              This action adds one to the dirty plate count. No student information is stored.
            </p>
            <div className="flex gap-2">
              <Button onClick={() => { setShowDirtyDialog(false); setPopupSelectedEntry(null) }} variant="outline" className="flex-1">
                Cancel
              </Button>
              <Button
                onClick={() => handlePopupSubmit('dirty')}
                className="flex-1 bg-orange-500 hover:bg-orange-600"
                disabled={isLoading}
              >
                Add Dirty Plate
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showFacultyDialog} onOpenChange={setShowFacultyDialog}>
        <DialogContent dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle className="text-green-600">🧑‍🏫 Record FACULTY CLEAN PLATE</DialogTitle>
            <DialogDescription>
              Enter the faculty member's name for clean plate tracking
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <SearchableNameInput
              placeholder="Faculty Name (e.g., Alex Morgan)"
              value={popupInputValue}
              onChange={(value, meta) => {
                setPopupInputValue(value)
                if (!meta || meta.source !== 'selection') {
                  setPopupSelectedEntry(null)
                }
              }}
              onSelectName={(entry) => {
                const sanitized = sanitizeSelection(entry)
                setPopupSelectedEntry(sanitized)
              }}
              onKeyPress={(e) => handleKeyPress(e, 'faculty')}
              names={teacherNames}
              autoFocus
            />
            <div className="flex gap-2">
              <Button onClick={() => { setShowFacultyDialog(false); setPopupSelectedEntry(null) }} variant="outline" className="flex-1">
                Cancel
              </Button>
              <Button
                onClick={() => handlePopupSubmit('faculty')}
                className="flex-1 bg-green-500 hover:bg-green-600"
                disabled={isLoading}
              >
                Record Faculty Clean Plate
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showRedDialog} onOpenChange={setShowRedDialog}>
        <DialogContent dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle className="text-red-600">🍝 Record as VERY DIRTY PLATE</DialogTitle>
            <DialogDescription>
              Enter Student ID or Name for very dirty plate tracking
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <SearchableNameInput
              placeholder="Student ID or Name (e.g., 12345 or John Smith)"
              value={popupInputValue}
              onChange={(value, meta) => {
                setPopupInputValue(value)
                if (!meta || meta.source !== 'selection') {
                  setPopupSelectedEntry(null)
                }
              }}
              onSelectName={(entry) => {
                const sanitized = sanitizeSelection(entry)
                setPopupSelectedEntry(sanitized)
              }}
              onKeyPress={(e) => handleKeyPress(e, 'red')}
              names={studentNames}
              autoFocus
            />
            <div className="flex gap-2">
              <Button onClick={() => { setShowRedDialog(false); setPopupSelectedEntry(null) }} variant="outline" className="flex-1">
                Cancel
              </Button>
              <Button
                onClick={() => handlePopupSubmit('red')}
                className="flex-1 bg-red-500 hover:bg-red-600"
                disabled={isLoading}
              >
                Record as VERY DIRTY PLATE
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showNewSessionDialog} onOpenChange={setShowNewSessionDialog}>
        <DialogContent dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle>Create New Session</DialogTitle>
            <DialogDescription>
              Enter a custom name or leave blank for default naming
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="session-name">Session Name (Optional)</Label>
              <Input
                id="session-name"
                type="text"
                placeholder="Leave blank for default name"
                value={customSessionName}
                onChange={(e) => setCustomSessionName(e.target.value)}
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={() => setShowNewSessionDialog(false)} variant="outline" className="flex-1">
                Cancel
              </Button>
              <Button
                onClick={() => createSession(customSessionName)}
                className="flex-1 bg-blue-600 hover:bg-blue-700"
                disabled={isLoading}
              >
                Create Session
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle className="text-red-600">Delete Session</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this session? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          {sessionToDelete && (
            <div className="bg-gray-50 p-4 rounded-lg">
              <div className="font-medium">{sessionToDelete.session_name}</div>
              <div className="text-sm text-gray-600">
                {sessionToDelete.total_records} records will be permanently deleted
              </div>
            </div>
          )}
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

      <Dialog open={showCsvPreview} onOpenChange={setShowCsvPreview}>
        <DialogContent
          className="w-full sm:max-w-2xl lg:max-w-3xl max-h-[75vh] overflow-y-auto"
          dismissOnOverlayClick={false}
        >
          <DialogHeader>
            <DialogTitle>Student Database Preview</DialogTitle>
            <DialogDescription>
              Current student database with pagination
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {csvPreviewData && (
              <>
                <div className="text-sm text-gray-600">
                  <p><strong>Total Records:</strong> {csvPreviewData.pagination.total_records}</p>
                  <p><strong>Uploaded by:</strong> {csvPreviewData.metadata.uploaded_by}</p>
                  <p><strong>Uploaded at:</strong> {new Date(csvPreviewData.metadata.uploaded_at).toLocaleString()}</p>
                </div>

                <div className="border rounded-lg overflow-hidden">
                  <div className="max-h-96 overflow-auto">
                    <table className="min-w-full table-auto text-xs leading-tight">
                      <thead className="bg-gray-50 sticky top-0 z-10">
                        <tr>
                          {csvPreviewData.columns.map((column, index) => (
                            <th
                              key={index}
                              className="px-3 py-2 text-left font-semibold text-gray-700 border-b border-gray-200 whitespace-nowrap"
                            >
                              {column}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {csvPreviewData.data.map((row, index) => (
                          <tr
                            key={index}
                            className={`${index % 2 === 0 ? 'bg-white' : 'bg-gray-50'} border-b border-gray-100 last:border-b-0`}
                          >
                            {csvPreviewData.columns.map((column, colIndex) => (
                              <td
                                key={colIndex}
                                className="px-3 py-1.5 text-gray-700 align-top break-words"
                              >
                                {row[column] || '-'}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="flex justify-between items-center">
                  <div className="text-sm text-gray-600">
                    Page {csvPreviewData.pagination.page} of {csvPreviewData.pagination.total_pages}
                    ({csvPreviewData.data.length} of {csvPreviewData.pagination.total_records} records)
                  </div>
                  <div className="flex gap-2">
                    <Button
                      onClick={() => previewCSV(csvPreviewPage - 1)}
                      disabled={!csvPreviewData.pagination.has_prev || csvPreviewLoading}
                      variant="outline"
                      size="sm"
                    >
                      Previous
                    </Button>
                    <Button
                      onClick={() => previewCSV(csvPreviewPage + 1)}
                      disabled={!csvPreviewData.pagination.has_next || csvPreviewLoading}
                      variant="outline"
                      size="sm"
                    >
                      Next
                    </Button>
                  </div>
                </div>
              </>
            )}
          </div>
          <Button onClick={() => setShowCsvPreview(false)} className="w-full">
            Close
          </Button>
        </DialogContent>
      </Dialog>

      {showTeacherPreview && (
        <Dialog open={showTeacherPreview} onOpenChange={setShowTeacherPreview}>
          <DialogContent className="w-full sm:max-w-2xl lg:max-w-4xl max-h-[80vh] overflow-hidden" dismissOnOverlayClick={false}>
            <DialogHeader>
              <DialogTitle>Teacher List Preview</DialogTitle>
              <DialogDescription>
                Preview of the uploaded teacher names
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              {teacherPreviewLoading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="text-muted-foreground">Loading teacher list...</div>
                </div>
              ) : teacherPreviewData ? (
                <>
                  <div className="text-sm text-muted-foreground">
                    <p><strong>Total Teachers:</strong> {teacherPreviewData.pagination.total_records}</p>
                    <p><strong>Uploaded by:</strong> {teacherPreviewData.metadata.uploaded_by}</p>
                    <p><strong>Uploaded at:</strong> {new Date(teacherPreviewData.metadata.uploaded_at).toLocaleString()}</p>
                  </div>

                  <div className="max-h-96 overflow-y-auto border rounded-lg">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 p-4">
                      {teacherPreviewData.data.map((teacher, index) => (
                        <div key={index} className="p-2 bg-gray-50 rounded text-sm">
                          {teacher.name}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-4">
                    <div className="text-sm text-muted-foreground">
                      Page {teacherPreviewData.pagination.page} of {teacherPreviewData.pagination.total_pages}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        onClick={() => previewTeachers(teacherPreviewPage - 1)}
                        disabled={!teacherPreviewData.pagination.has_prev || teacherPreviewLoading}
                        variant="outline"
                        size="sm"
                      >
                        Previous
                      </Button>
                      <Button
                        onClick={() => previewTeachers(teacherPreviewPage + 1)}
                        disabled={!teacherPreviewData.pagination.has_next || teacherPreviewLoading}
                        variant="outline"
                        size="sm"
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center py-8">
                  <div className="text-muted-foreground">No teacher data available</div>
                </div>
              )}
            </div>
            <Button onClick={() => setShowTeacherPreview(false)} className="w-full">
              Close
            </Button>
          </DialogContent>
        </Dialog>
      )}

      <Dialog open={showDashboard} onOpenChange={setShowDashboard}>
        <DialogContent
          className="w-full sm:max-w-2xl lg:max-w-4xl max-h-[82vh] overflow-y-auto"
          dismissOnOverlayClick={false}
        >
          <DialogHeader>
            <DialogTitle className="text-purple-600">Session Dashboard</DialogTitle>
            <DialogDescription>
              Key metrics for the currently selected session.
            </DialogDescription>
          </DialogHeader>
          {!sessionId ? (
            <div className="py-12 text-center text-gray-500">
              No active session selected. Switch to a session to view dashboard insights.
            </div>
          ) : (
            <div className="space-y-6">
              {isSessionDiscarded && (
                <Alert variant="destructive">
                  <Ban className="h-4 w-4" />
                  <AlertDescription>
                    This session is discarded from draw calculations. Reinstate it to include ticket updates.
                  </AlertDescription>
                </Alert>
              )}

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm sm:col-span-2 lg:col-span-3">
                  <div className="text-sm text-gray-500">Session</div>
                  <div className="text-2xl font-semibold text-gray-900">{sessionName || 'Untitled session'}</div>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-gray-500">
                    <Badge variant={isSessionDiscarded ? 'destructive' : 'outline'}>
                      {isSessionDiscarded ? 'Discarded' : 'Active'}
                    </Badge>
                    {drawSummary?.generated_at && (
                      <span>Updated {new Date(drawSummary.generated_at).toLocaleString()}</span>
                    )}
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                  <div className="text-sm text-gray-500">Total records</div>
                  <div className="text-2xl font-semibold text-gray-900">
                    {sessionDashboardStats.totalRecorded.toLocaleString()}
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    Includes faculty clean plates
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                  <div className="text-sm text-gray-500">Clean plates</div>
                  <div className="text-2xl font-semibold text-emerald-700">
                    {sessionDashboardStats.cleanCount.toLocaleString()}
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    Clean rate {sessionDashboardStats.cleanPercentage.toFixed(1)}% • Includes faculty clean
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                  <div className="text-sm text-gray-500">Dirty plates</div>
                  <div className="text-2xl font-semibold text-orange-700">
                    {sessionDashboardStats.combinedDirty.toLocaleString()}
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    Dirty rate {sessionDashboardStats.dirtyPercentage.toFixed(1)}% • Standard dirty {sessionDashboardStats.dirtyCount.toLocaleString()}
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                  <div className="text-sm text-gray-500">Very dirty plates</div>
                  <div className="text-2xl font-semibold text-red-700">
                    {sessionDashboardStats.redCount.toLocaleString()}
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                  <div className="text-sm text-gray-500">Faculty clean plates</div>
                  <div className="text-2xl font-semibold text-gray-900">
                    {sessionDashboardStats.facultyCount.toLocaleString()}
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                  <Trophy className="h-4 w-4" />
                  Current winner
                </div>
                <div className="mt-3 text-sm text-gray-700">
                  {dashboardWinner.winner ? (
                    <div className="space-y-2">
                      <div className="text-lg font-semibold text-gray-900">{dashboardWinner.winner.display_name}</div>
                      {dashboardWinner.winner.student_identifier && (
                        <div className="text-xs text-gray-500">Student ID: {dashboardWinner.winner.student_identifier}</div>
                      )}
                      <div className="flex flex-wrap gap-2 text-xs text-gray-500">
                        {dashboardWinner.winner.grade && <span>Grade: {dashboardWinner.winner.grade}</span>}
                        {dashboardWinner.winner.house && <span>House: {dashboardWinner.winner.house}</span>}
                        {dashboardWinner.winner.clan && <span>Clan: {dashboardWinner.winner.clan}</span>}
                      </div>
                      <div className="text-xs text-gray-500">
                        Status:{' '}
                        <Badge variant={dashboardWinner.finalized ? 'default' : 'outline'}>
                          {dashboardWinner.finalized ? 'Finalized' : 'Pending finalization'}
                        </Badge>
                      </div>
                      {dashboardWinner.timestamp && (
                        <div className="flex items-center gap-1 text-xs text-gray-500">
                          <Clock className="h-3 w-3" />
                          {dashboardWinner.timestamp.toLocaleString()}
                        </div>
                      )}
                      {(dashboardWinner.tickets !== null || dashboardWinner.probability !== null) && (
                        <div className="text-xs text-gray-500">
                          Tickets at selection: {dashboardWinner.tickets !== null ? Number(dashboardWinner.tickets).toFixed(2) : '—'} • Chance: {dashboardWinner.probability !== null ? Number(dashboardWinner.probability).toFixed(2) : '—'}%
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-gray-500">No winner selected yet.</div>
                  )}
                </div>
              </div>
            </div>
          )}

          <Button onClick={() => setShowDashboard(false)} className="w-full">
            Close
          </Button>
        </DialogContent>
      </Dialog>

      <Dialog open={showAdminPanel} onOpenChange={setShowAdminPanel}>
        <DialogContent
          className="w-full sm:max-w-2xl lg:max-w-3xl max-h-[82vh] overflow-y-auto"
          dismissOnOverlayClick={false}
        >
          <DialogHeader>
            <DialogTitle className="text-red-600">Admin Panel</DialogTitle>
            <DialogDescription>
              System administration and management
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-6">
            <div className="flex gap-4">
              {['admin', 'superadmin'].includes(user.role) && (
                <>
                  <Button
                    onClick={generateInviteCode}
                    variant="outline"
                    className="flex-1"
                  >
                    <Copy className="h-4 w-4 mr-2" />
                    Generate Invite Code
                  </Button>
                  <Button
                    onClick={() => {
                      setShowDeleteRequests(true)
                      loadDeleteRequests()
                    }}
                    variant="outline"
                    className="relative flex-1"
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete Requests
                    {deleteRequestsCount > 0 && (
                      <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs rounded-full px-2 py-0.5">
                        {deleteRequestsCount}
                      </span>
                    )}
                  </Button>
                  <Button
                    onClick={() => {
                      loadAllUsers()
                      setShowAccountManagement(true)
                    }}
                    variant="outline"
                    className="flex-1"
                  >
                    <Users className="h-4 w-4 mr-2" />
                    Manage Accounts
                  </Button>
                </>
              )}
            </div>

            <div>
              <h3 className="text-lg font-semibold mb-3">Users</h3>
              <div className="space-y-2">
                {adminUsers.map((adminUser) => (
                  <div key={adminUser.username} className="flex items-center justify-between p-3 border rounded-lg">
                    <div>
                      <div className="font-medium">{adminUser.name}</div>
                      <div className="text-sm text-gray-500">
                        @{adminUser.username} • {adminUser.role}
                        {formatSchoolNameWithCode(adminUser.school) && (
                          <> • {formatSchoolNameWithCode(adminUser.school)}</>
                        )}
                      </div>
                      {user.role === 'superadmin' && adminUser.password && (
                        <div className="text-xs text-gray-500">Password: {adminUser.password}</div>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={adminUser.role === 'superadmin' ? 'destructive' : adminUser.role === 'admin' ? 'default' : 'secondary'}
                      >
                        {adminUser.role}
                      </Badge>
                      {user.role === 'superadmin' && adminUser.username !== user.username && (
                        <div className="flex gap-1">
                          <select
                            className="text-xs border rounded px-2 py-1"
                            value={adminUser.role}
                            onChange={(e) => changeUserRole(adminUser.username, e.target.value)}
                          >
                            <option value="user">User</option>
                            <option value="admin">Admin</option>
                            <option value="superadmin">Super Admin</option>
                          </select>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => {
                              setUserToDelete(adminUser)
                              setShowUserDeleteConfirm(true)
                            }}
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h3 className="text-lg font-semibold mb-3">All Sessions</h3>
              <div className="space-y-2 max-h-40 overflow-y-auto">
                {adminSessions.map((adminSession) => (
                  <div key={adminSession.session_id} className="flex items-center justify-between p-3 border rounded-lg">
                    <div>
                      <div className="font-medium flex items-center gap-2">
                        {adminSession.session_name}
                        {adminSession.is_discarded && (
                          <Badge variant="destructive" className="text-xs uppercase">Discarded</Badge>
                        )}
                      </div>
                      <div className="text-sm text-gray-500">
                        Owner: {adminSession.owner} • {adminSession.total_records} records • Faculty Clean: {adminSession.faculty_clean_count ?? 0}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <Button onClick={() => setShowAdminPanel(false)} className="w-full">
            Close
          </Button>
        </DialogContent>
      </Dialog>

      <Dialog open={showAccountManagement} onOpenChange={setShowAccountManagement}>
        <DialogContent className="max-w-2xl" dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle>Account Management</DialogTitle>
            <DialogDescription>
              Manage user account status (enable/disable accounts)
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 max-h-96 overflow-y-auto">
            {allUsers.map((userAccount) => (
              <div key={userAccount.username} className="flex items-center justify-between p-3 border rounded-lg">
                <div>
                  <div className="font-medium">{userAccount.name}</div>
                  <div className="text-sm text-gray-500">
                    @{userAccount.username} • {userAccount.role}
                    {formatSchoolNameWithCode(userAccount.school) && (
                      <> • {formatSchoolNameWithCode(userAccount.school)}</>
                    )}
                  </div>
                  {user.role === 'superadmin' && userAccount.password && (
                    <div className="text-xs text-gray-500">Password: {userAccount.password}</div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    variant={userAccount.status === 'active' ? 'default' : 'destructive'}
                  >
                    {userAccount.status}
                  </Badge>
                  {((user.role === 'superadmin' && userAccount.username !== user.username) ||
                    (user.role === 'admin' && !['superadmin', 'admin'].includes(userAccount.role))) && (
                    <Button
                      onClick={() => toggleAccountStatus(userAccount.username, userAccount.status)}
                      variant={userAccount.status === 'active' ? 'destructive' : 'default'}
                      size="sm"
                    >
                      {userAccount.status === 'active' ? 'Disable' : 'Enable'}
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
          <Button onClick={() => setShowAccountManagement(false)} className="w-full">
            Close
          </Button>
        </DialogContent>
      </Dialog>

      <Dialog open={showUserDeleteConfirm} onOpenChange={setShowUserDeleteConfirm}>
        <DialogContent dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle>Confirm Account Deletion</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete account "{userToDelete?.username}"? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="flex gap-2 mt-4">
            <Button
              variant="destructive"
              onClick={() => {
                if (userToDelete) {
                  deleteUserAccount(userToDelete.username)
                }
                setShowUserDeleteConfirm(false)
                setUserToDelete(null)
              }}
            >
              Delete
            </Button>
            <Button variant="outline" onClick={() => { setShowUserDeleteConfirm(false); setUserToDelete(null) }}>
              Cancel
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showDeleteRequests} onOpenChange={setShowDeleteRequests}>
        <DialogContent className="max-w-2xl" dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle>Delete Requests</DialogTitle>
            <DialogDescription>
              Pending session deletion requests from users
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 max-h-96 overflow-y-auto">
            {deleteRequests.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No pending delete requests
              </div>
            ) : (
              deleteRequests.map((request) => (
                <div key={request.id} className="flex items-center justify-between p-3 border rounded-lg">
                  <div>
                    <div className="font-medium">{request.session_name}</div>
                    <div className="text-sm text-gray-500">
                      Requested by: {request.requester_name} (@{request.requester}) • {request.total_records} records
                    </div>
                    <div className="text-xs text-gray-400">
                      Clean: {request.clean_records} • Dirty: {request.dirty_records} • Red: {request.red_records} • Faculty: {request.faculty_clean_records || 0}
                    </div>
                    <div className="text-xs text-gray-400">
                      {new Date(request.requested_at).toLocaleString()}
                    </div>
                  </div>
                  <div className="flex flex-col gap-2">
                    <Button
                      onClick={() => approveDeleteRequest(request.id)}
                      variant="destructive"
                      size="sm"
                    >
                      <Trash2 className="h-4 w-4 mr-1" />
                      Approve
                    </Button>
                    <Button
                      onClick={() => rejectDeleteRequest(request.id)}
                      variant="outline"
                      size="sm"
                    >
                      <XCircle className="h-4 w-4 mr-1" />
                      Reject
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
          <Button onClick={() => setShowDeleteRequests(false)} className="w-full">
            Close
          </Button>
        </DialogContent>
      </Dialog>

      <Dialog open={showSessionsDialog} onOpenChange={setShowSessionsDialog}>
        <DialogContent dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle>Switch Session</DialogTitle>
            <DialogDescription>
              Select a session to switch to or delete sessions
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {sessions.map((session) => (
              <div key={session.session_id} className="flex items-center justify-between p-2 border rounded">
                <Button
                  variant="ghost"
                  onClick={() => switchSession(session.session_id)}
                  className="flex-1 justify-start"
                  disabled={session.session_id === sessionId}
                >
                  <div className="text-left">
                    <div className="font-medium">{session.session_name}</div>
                    {session.is_discarded && (
                      <Badge variant="destructive" className="mt-1 text-xs uppercase">Discarded</Badge>
                    )}
                    <div className="text-sm text-gray-500">
                      {session.total_records > 0 ? (
                        <>
                          🥇 {session.clean_count} ({session.clean_percentage}% incl. faculty) •
                          🍽️ {session.dirty_count} ({session.dirty_percentage}%) •
                          🧑‍🏫 {session.faculty_clean_count ?? 0}
                        </>
                      ) : (
                        'No records yet'
                      )}
                    </div>
                  </div>
                </Button>
                {sessionId && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setSessionToDelete(session)
                      setShowDeleteConfirm(true)
                    }}
                    className="text-red-600 hover:text-red-700 hover:bg-red-50"
                    disabled={session.delete_requested}
                    title={session.delete_requested ? 'Delete request pending' : 'Delete session'}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            ))}
          </div>
          <Button onClick={() => setShowSessionsDialog(false)} className="w-full">
            Close
          </Button>
        </DialogContent>
      </Dialog>

    </div>
  )
}

export default MainPortal
