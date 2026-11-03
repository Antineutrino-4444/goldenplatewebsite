import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button.jsx'

const PAGE_SIZE = 20
const NAME_FIELDS = [['Preferred', 'First or preferred name'], ['Last', 'Last name']]
const STUDENT_FIELDS = [...NAME_FIELDS, ['Student ID'], ['Grade'], ['Advisor'], ['House'], ['Clan']]
const TEACHER_FIELDS = [...NAME_FIELDS, ['Faculty ID']]
const INPUT_CLASS = 'w-full min-w-0 rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm'

function columnName(index) {
  const letter = String.fromCharCode(65 + index % 26)
  return index < 26 ? letter : columnName(Math.floor(index / 26) - 1) + letter
}

function RosterReview({ file, tables, kind, loaded, isLoading, upload, close }) {
  const heading = useRef(null)
  const [tableIndex, setTableIndex] = useState(0)
  const [columns, setColumns] = useState(tables[0].mapping)
  const [skipFirst, setSkipFirst] = useState(tables[0].skip_first)
  const [generateIds, setGenerateIds] = useState(false)
  const [page, setPage] = useState(0)
  useEffect(() => {
    heading.current?.focus()
  }, [])

  const student = kind === 'student'
  const table = tables[tableIndex]
  const sourceColumns = Array.from({ length: table.width }, (_, index) => index)
  const pageCount = Math.ceil(table.rows.length / PAGE_SIZE)
  const start = page * PAGE_SIZE
  const activeColumns = { ...columns }
  if (generateIds) delete activeColumns['Student ID']
  const assigned = Object.values(activeColumns)
  const required = student && !generateIds ? ['Preferred', 'Last', 'Student ID'] : ['Preferred', 'Last']
  const canImport = required.every((field) => field in activeColumns)
    && new Set(assigned).size === assigned.length
    && table.rows.length > Number(skipFirst)
  const missingFields = required.some((field) => !(field in activeColumns))
  const generatedIds = new Map()
  if (generateIds) {
    table.rows.forEach((row, index) => {
      if (index >= Number(skipFirst) && row.some(Boolean)) generatedIds.set(index, generatedIds.size + 1)
    })
  }

  return (
    <section aria-label="Review roster import" className="mt-3 space-y-4 rounded-lg border bg-white p-3 sm:p-4">
      <div>
        <h3 ref={heading} tabIndex={-1} className="font-semibold">Review {kind === 'teacher' ? 'faculty' : 'student'} roster</h3>
        <p className="break-all text-sm text-gray-600">{file.name}</p>
      </div>

      <fieldset disabled={isLoading} className="min-w-0 space-y-3">
        {tables.length > 1 && (
          <label className="block max-w-sm text-sm font-medium">
            Sheet or table
            <select className={INPUT_CLASS} value={tableIndex} onChange={(event) => {
              const index = Number(event.target.value)
              setTableIndex(index)
              setColumns(tables[index].mapping)
              setSkipFirst(tables[index].skip_first)
              setPage(0)
            }}>
              {tables.map((source, index) => <option key={index} value={index}>{source.name}</option>)}
            </select>
          </label>
        )}
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={skipFirst} onChange={(event) => setSkipFirst(event.target.checked)} />
          Exclude the first row (column headings or title)
        </label>
        {student && (
          <div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={generateIds} onChange={(event) => setGenerateIds(event.target.checked)} />
              Generate student IDs from row order
            </label>
            {generateIds && (
              <p className="mt-1 text-sm text-gray-600">
                {generatedIds.size ? `IDs will run from 1 to ${generatedIds.size}. ` : ''}
                Use stable IDs for future imports if the roster order changes.
              </p>
            )}
          </div>
        )}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
          {(student ? STUDENT_FIELDS : TEACHER_FIELDS).map(([field, label]) => {
            const generated = generateIds && field === 'Student ID'
            return (
              <label key={field} className={`min-w-0 text-sm font-medium ${required.includes(field) || generated ? 'col-span-2 sm:col-span-1' : ''}`}>
                {label || field}{!required.includes(field) && !generated && ' (optional)'}
                <select
                  className={INPUT_CLASS}
                  disabled={generated}
                  value={generated ? '' : columns[field] ?? ''}
                  onChange={(event) => {
                    const value = event.target.value
                    setColumns((current) => {
                      const updated = { ...current }
                      if (value === '') delete updated[field]
                      else updated[field] = Number(value)
                      return updated
                    })
                  }}
                >
                  <option value="">{generated ? 'Generated from row order' : 'Choose a column'}</option>
                  {sourceColumns.map((index) => (
                    <option key={index} value={index}>
                      {columnName(index)}{skipFirst && table.rows[0][index] ? ` · ${table.rows[0][index]}` : ''}
                    </option>
                  ))}
                </select>
              </label>
            )
          })}
        </div>
        {missingFields && (
          <p className="text-sm text-gray-600">Assign a column for each required field before importing.</p>
        )}
        {new Set(assigned).size !== assigned.length && (
          <p role="alert" className="text-sm text-red-700">Assign a different source column to each field.</p>
        )}
      </fieldset>

      <div className="max-h-80 overflow-auto rounded-md border" tabIndex={0} role="region" aria-label="Spreadsheet preview. Scroll to see more rows and columns.">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="sticky top-0 bg-gray-100">
            <tr>
              <th scope="col" className="p-2">Row</th>
              {generateIds && <th scope="col" className="min-w-24 border-l p-2">Student ID</th>}
              {sourceColumns.map((index) => (
                <th key={index} scope="col" className="min-w-24 border-l p-2">
                  {columnName(index)}
                  <span className="block text-xs font-normal text-gray-600">
                    {Object.keys(activeColumns).filter((field) => activeColumns[field] === index).join(', ')}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.slice(start, start + PAGE_SIZE).map((row, index) => {
              const rowIndex = start + index
              const excluded = rowIndex === 0 && skipFirst
              return (
                <tr key={rowIndex} className={excluded ? 'bg-gray-100 text-gray-600' : 'bg-white'}>
                  <th scope="row" className="whitespace-nowrap border-t p-2 font-normal">
                    {rowIndex + 1}{excluded && <span className="block text-xs"> (excluded)</span>}
                  </th>
                  {generateIds && <td className="border-l border-t p-2">{generatedIds.get(rowIndex)}</td>}
                  {sourceColumns.map((column) => (
                    <td key={column} className="max-w-64 whitespace-pre-wrap break-words border-l border-t p-2">{row[column]}</td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {loaded && (
        <p className="text-sm text-gray-700">
          This import replaces the current roster. Past plate records and draw logs are kept.
          {student && ' Students missing from the new roster will be excluded from ticket draws.'}
        </p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button>
          <span aria-live="polite">Rows {start + 1}–{Math.min(start + PAGE_SIZE, table.rows.length)} of {table.rows.length}</span>
          <Button variant="outline" size="sm" disabled={page + 1 >= pageCount} onClick={() => setPage(page + 1)}>Next</Button>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" disabled={isLoading} onClick={close}>Cancel</Button>
          <Button size="sm" disabled={isLoading || !canImport} onClick={() => upload(file, {
            table: tableIndex, columns: activeColumns, skip_first: skipFirst, generate_ids: generateIds,
          }, close)}>
            {isLoading ? 'Importing…' : loaded ? 'Replace roster' : 'Import roster'}
          </Button>
        </div>
      </div>
    </section>
  )
}

export default function RosterUpload({ roster, kind, isLoading, upload }) {
  const fileInput = useRef(null)
  const [review, setReview] = useState(null)
  const [reading, setReading] = useState(false)
  const [error, setError] = useState('')
  const loaded = Boolean(roster)

  const reviewFile = async (file) => {
    setReview(null)
    setError('')
    if (file.size > 8 * 1024 * 1024) {
      setError('Choose a roster file of 8 MB or less.')
      return
    }
    setReading(true)
    const body = new FormData()
    body.append('file', file)
    try {
      const response = await fetch(`/api/rosters/${kind}/review`, { method: 'POST', body })
      const data = await response.json()
      if (response.ok) setReview({ file, tables: data.tables })
      else setError(data.error || 'Could not open the roster file.')
    } catch {
      setError('Could not open the roster file.')
    } finally {
      setReading(false)
    }
  }

  return (
    <div className="mb-4 min-w-0">
      <div className="flex min-w-0 flex-wrap items-center gap-3 rounded-lg border bg-white p-3">
        <input
          ref={fileInput}
          type="file"
          accept=".csv,.tsv,.xlsx,.xls,.numbers,.txt"
          aria-label={`Choose ${kind} roster`}
          className="hidden"
          disabled={isLoading || reading}
          onChange={(event) => {
            const file = event.target.files[0]
            event.target.value = ''
            if (file) reviewFile(file)
          }}
        />
        <span className="min-w-0 flex-1 text-sm text-gray-700 [overflow-wrap:anywhere]">
          {loaded ? roster.filename || `${kind === 'teacher' ? 'Teacher' : 'Student'} database loaded` : `No ${kind} database loaded`}
        </span>
        <Button variant="outline" size="sm" onClick={() => fileInput.current?.click()} disabled={isLoading || reading}>
          {reading ? 'Reading file…' : 'Choose file'}
        </Button>
      </div>
      {error && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
      {review && <RosterReview {...review} kind={kind} loaded={loaded} isLoading={isLoading} upload={upload} close={() => setReview(null)} />}
    </div>
  )
}
