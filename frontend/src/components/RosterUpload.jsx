import { useRef } from 'react'
import { Button } from '@/components/ui/button.jsx'

export default function RosterUpload({ roster, kind, accept, isLoading, upload, setModal }) {
  const fileInput = useRef(null)
  const loaded = Boolean(roster)
  const chooseFile = () => fileInput.current?.click()
  const requestFile = () => {
    if (!loaded) {
      chooseFile()
      return
    }
    setModal({
      type: 'confirm', title: 'Upload a new database?', confirmLabel: 'Choose new file',
      message: `Choose a new ${kind} roster to replace the loaded database. You will confirm the replacement before it is uploaded.`,
      onConfirm: chooseFile
    })
  }

  return (
    <div className="mb-4 flex min-w-0 flex-wrap items-center gap-3 rounded-lg border bg-white p-3">
      <input
        ref={fileInput}
        type="file"
        accept={accept}
        aria-label={`Upload ${kind} database`}
        className="hidden"
        disabled={isLoading}
        onChange={(event) => {
          const file = event.target.files[0]
          event.target.value = ''
          if (file) upload(file)
        }}
      />
      <span className="min-w-0 flex-1 text-sm text-gray-700 [overflow-wrap:anywhere]">
        {loaded ? roster.filename || `${kind === 'teacher' ? 'Teacher' : 'Student'} database loaded` : `No ${kind} database loaded`}
      </span>
      <Button variant="outline" size="sm" onClick={requestFile} disabled={isLoading}>
        {isLoading ? 'Uploading…' : loaded ? 'Replace database' : 'Choose file'}
      </Button>
    </div>
  )
}
