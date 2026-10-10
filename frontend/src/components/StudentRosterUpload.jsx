import RosterUpload from '@/components/RosterUpload.jsx'

export default function StudentRosterUpload({ app }) {
  return <RosterUpload roster={app.csvData} kind="student" accept=".csv" isLoading={app.isLoading} upload={app.uploadCSV} setModal={app.setModal} />
}
