import { useRef } from 'react'
import { Button } from '@/components/ui/button.jsx'

export default function StudentRosterUpload({ app }) {
  const fileInput = useRef(null)
  const loaded = Boolean(app.csvData)
  const chooseFile = () => fileInput.current?.click()
  const requestFile = () => {
    if (!loaded) {
      chooseFile()
      return
    }
    app.setModal({
      type: 'confirm', title: 'Upload a new database?', confirmLabel: 'Choose new CSV',
      message: 'Choose a new student roster to replace the loaded database. You will confirm the replacement before it is uploaded.',
      onConfirm: chooseFile
    })
  }

  return (
    <div className="mb-4 flex min-w-0 flex-wrap items-center gap-3 rounded-lg border bg-white p-3">
      <input
        ref={fileInput}
        type="file"
        accept=".csv"
        aria-label="Upload student CSV"
        className="hidden"
        disabled={app.isLoading}
        onChange={(event) => {
          const file = event.target.files[0]
          event.target.value = ''
          if (file) app.uploadCSV(file)
        }}
      />
      <span className="min-w-0 flex-1 text-sm text-gray-700 [overflow-wrap:anywhere]">
        {loaded ? app.csvData.filename || 'Student database loaded' : 'No student database loaded'}
      </span>
      <Button variant="outline" size="sm" onClick={requestFile} disabled={app.isLoading}>
        {app.isLoading ? 'Uploading…' : loaded ? 'Replace database' : 'Choose file'}
      </Button>
    </div>
  )
}
