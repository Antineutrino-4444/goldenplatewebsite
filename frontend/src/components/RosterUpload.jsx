import { HelpTip } from '@/components/HelpTip.jsx'
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

function fileMapping(table, index = 0) {
  return { table: index, columns: table.mapping, skip_first: table.skip_first }
}

function RosterFileReview({ file, tables, kind, isLoading, mapping, update, generateIds, offset, issue }) {
  const { table: tableIndex, columns, skip_first: skipFirst } = mapping
  const [page, setPage] = useState(0)
  const student = kind === 'student'
  const table = tables[tableIndex]
  const sourceColumns = Array.from({ length: table.width }, (_, index) => index)
  const pageCount = Math.ceil(table.rows.length / PAGE_SIZE)
  const start = page * PAGE_SIZE
  const activeColumns = { ...columns }
  if (generateIds) delete activeColumns['Student ID']
  const assigned = Object.values(activeColumns)
  const required = student && !generateIds ? ['Preferred', 'Last', 'Student ID'] : ['Preferred', 'Last']
  const missingFields = required.some((field) => !(field in activeColumns))
  const generatedIds = new Map()
  if (generateIds) {
    table.rows.forEach((row, index) => {
      if (index >= Number(skipFirst) && row.some(Boolean)) generatedIds.set(index, offset + generatedIds.size + 1)
    })
  }

  return (
    <section aria-label={file.name} className="space-y-4 rounded-lg border bg-white p-3 sm:p-4">
      {issue && <p className="text-sm text-red-700" role="status">{issue}</p>}

      <fieldset disabled={isLoading} className="min-w-0 space-y-3">
        {tables.length > 1 && (
          <label className="block max-w-sm text-sm font-medium">
            Sheet or table
            <select className={INPUT_CLASS} value={mapping.table_confirmed ? tableIndex : ''} onChange={(event) => {
              const index = Number(event.target.value)
              update({ ...fileMapping(tables[index], index), table_confirmed: true })
              setPage(0)
            }}>
              <option value="" disabled>Choose a sheet or table</option>
              {tables.map((source, index) => <option key={index} value={index}>{source.name}</option>)}
            </select>
          </label>
        )}
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={skipFirst} onChange={(event) => update({ ...mapping, skip_first: event.target.checked })} />
          Exclude the first row (column headings or title)
        </label>
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
                    const updated = { ...columns }
                    if (value === '') delete updated[field]
                    else updated[field] = Number(value)
                    update({ ...mapping, columns: updated })
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
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button>
        <span aria-live="polite">Rows {start + 1}–{Math.min(start + PAGE_SIZE, table.rows.length)} of {table.rows.length}</span>
        <Button variant="outline" size="sm" disabled={page + 1 >= pageCount} onClick={() => setPage(page + 1)}>Next</Button>
      </div>
    </section>
  )
}

function RosterReview({ reviews, setReviews, kind, loaded, isLoading, upload, close }) {
  const heading = useRef(null)
  const [generateIds, setGenerateIds] = useState(false)
  const [openFileId, setOpenFileId] = useState(undefined)
  useEffect(() => {
    heading.current?.focus()
  }, [])

  let rowCount = 0
  const identifiers = new Map()
  const duplicateFiles = new Map()
  const idField = kind === 'student' ? 'Student ID' : 'Faculty ID'
  const prepared = reviews.map(({ tables, mapping }, index) => {
    const columns = { ...mapping.columns }
    if (generateIds) delete columns['Student ID']
    const required = ['Preferred', 'Last']
    if ((kind === 'student' && !generateIds) || (kind === 'teacher' && idField in columns)) required.push(idField)
    const values = Object.values(columns)
    let issue = ''
    if (tables.length > 1 && !mapping.table_confirmed) issue = 'Choose which sheet or table to import.'
    else if (required.some((field) => !(field in columns))) issue = 'Assign the required columns.'
    else if (new Set(values).size !== values.length) issue = 'Assign a different column to each field.'

    const offset = rowCount
    const first = Number(mapping.skip_first)
    const rows = tables[mapping.table].rows
    for (let i = first; i < rows.length; i++) {
      const row = rows[i]
      if (!row.some(Boolean)) continue
      rowCount++
      if (issue) continue
      const missing = required.find((field) => !row[columns[field]])
      if (missing) {
        issue = `Row ${i + 1} is missing ${missing}.`
        continue
      }
      const identifier = row[columns[idField]]?.toLowerCase()
      if (identifier) {
        const previous = identifiers.get(identifier)
        if (previous) {
          duplicateFiles.set(previous.index, `Row ${previous.row} has a duplicate ${idField}.`)
          duplicateFiles.set(index, `Row ${i + 1} has a duplicate ${idField}.`)
        } else {
          identifiers.set(identifier, { index, row: i + 1 })
        }
      }
    }
    if (!issue && offset === rowCount) issue = 'This sheet or table has no roster rows to import.'
    return { offset, count: rowCount - offset, issue, mapping: { ...mapping, columns, generate_ids: generateIds } }
  })
  const issues = prepared.map(({ issue }, index) => issue || duplicateFiles.get(index))
  const needsReview = issues.filter(Boolean).length
  const openIndex = openFileId === undefined
    ? (reviews.length === 1 ? 0 : issues.findIndex(Boolean))
    : reviews.findIndex(({ id }) => id === openFileId)
  const canImport = rowCount <= 20000 && needsReview === 0

  return (
    <section aria-label="Review roster import" className="mt-3 space-y-4">
      <div className="flex items-center gap-1">
        <h3 ref={heading} tabIndex={-1} className="font-semibold">Review {kind === 'teacher' ? 'faculty' : 'student'} roster</h3>
        <HelpTip topic="matching roster columns" video={kind === 'teacher' ? 6 : 5}>
          If a file needs review, open its preview. Match each required field to the column that contains it and exclude the first row if it contains column headings.
        </HelpTip>
      </div>
      <p className="text-sm" aria-live="polite">
        {reviews.length - needsReview} of {reviews.length} {reviews.length === 1 ? 'file' : 'files'} ready to import.
        {needsReview > 0 && ` ${needsReview} ${needsReview === 1 ? 'needs' : 'need'} review.`}
      </p>
      {kind === 'student' && (
        <div>
          <div className="flex items-center gap-1">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={generateIds} disabled={isLoading} onChange={(event) => setGenerateIds(event.target.checked)} />
              Generate student IDs from row order
            </label>
            <HelpTip topic="generating student IDs">
              Use this if your roster has no student IDs. For repeat imports, use stable student IDs so a change in row order doesn’t change who an ID belongs to.
            </HelpTip>
          </div>
          {generateIds && rowCount > 0 && <p className="mt-1 text-sm text-gray-600">IDs will run from 1 to {rowCount} across the selected files. Use stable IDs for future imports if the roster order changes.</p>}
        </div>
      )}
      <ul className="divide-y rounded-lg border bg-white">
        {reviews.map((review, index) => (
          <li key={review.id} className="space-y-2 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <div className="min-w-0 flex-1">
                <p className="break-all text-sm font-medium">{review.file.name}</p>
                <p className={issues[index] ? 'text-xs text-red-700' : 'text-xs text-gray-600'}>
                  {issues[index] ? `Needs review · ${issues[index]}` : `Ready · ${prepared[index].count} rows`}
                </p>
              </div>
              <Button variant="outline" size="sm" aria-expanded={openIndex === index}
                aria-label={`${openIndex === index ? 'Hide' : 'Review'} ${review.file.name}`}
                onClick={() => setOpenFileId(openIndex === index ? null : review.id)}>
                {openIndex === index ? 'Hide preview' : 'Review'}
              </Button>
              {reviews.length > 1 && <Button variant="outline" size="sm" disabled={isLoading}
                aria-label={`Remove ${review.file.name}`} onClick={() => {
                  if (openFileId === review.id) setOpenFileId(undefined)
                  setReviews((current) => current.filter((entry) => entry.id !== review.id))
                }}>Remove</Button>}
            </div>
            {openIndex === index && <RosterFileReview {...review} kind={kind} isLoading={isLoading}
              generateIds={generateIds} offset={prepared[index].offset} issue={issues[index]}
              update={(mapping) => {
                setOpenFileId(review.id)
                setReviews((current) => current.map((entry) => entry.id === review.id ? { ...entry, mapping } : entry))
              }}
            />}
          </li>
        ))}
      </ul>
      {rowCount > 20000 && <p role="alert" className="text-sm text-red-700">The combined roster can contain up to 20,000 rows.</p>}
      {loaded && (
        <p className="text-sm text-gray-700">
          This import replaces the current roster. Past plate records and draw logs are kept.
          {kind === 'student' && ' Students missing from the new roster will be excluded from ticket draws.'}
        </p>
      )}
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="outline" size="sm" disabled={isLoading} onClick={close}>Cancel</Button>
        <Button size="sm" disabled={isLoading || !canImport} onClick={() => upload(reviews.map(({ file }) => file), prepared.map(({ mapping }) => mapping), close)}>
          {isLoading ? 'Importing…' : loaded ? 'Replace roster' : 'Import roster'}
        </Button>
      </div>
    </section>
  )
}

export default function RosterUpload({ roster, kind, isLoading, upload }) {
  const fileInput = useRef(null)
  const nextFileId = useRef(0)
  const [reviews, setReviews] = useState([])
  const [reading, setReading] = useState(false)
  const [error, setError] = useState('')
  const loaded = Boolean(roster)

  const reviewFiles = async (files) => {
    setError('')
    if (reviews.length + files.length > 10) {
      setError('Choose up to 10 roster files.')
      return
    }
    setReading(true)
    const added = []
    const failed = []
    try {
      for (const file of files) {
        try {
          if (file.size > 8 * 1024 * 1024) throw new Error('File exceeds 8 MB.')
          const body = new FormData()
          body.append('file', file)
          const response = await fetch(`/api/rosters/${kind}/review`, { method: 'POST', body })
          const data = await response.json()
          if (!response.ok) throw new Error(data.error || 'Could not open this file.')
          const tables = data.tables
          const recognized = tables.map((table, index) => ({ table, index }))
            .filter(({ table }) => 'Preferred' in table.mapping && 'Last' in table.mapping)
          const index = recognized.length === 1 ? recognized[0].index : 0
          const mapping = { ...fileMapping(tables[index], index), table_confirmed: recognized.length === 1 }
          added.push({ id: nextFileId.current++, file, tables, mapping })
        } catch (error) {
          failed.push(`${file.name}: ${error.message || 'Could not open this file.'}`)
        }
      }
      setReviews((current) => [...current, ...added])
      if (failed.length) setError(`Files not added. ${failed.join(' ')}`)
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
          multiple
          accept=".csv,.tsv,.xlsx,.xls,.numbers,.txt"
          aria-label={`Choose ${kind} roster`}
          className="hidden"
          disabled={isLoading || reading}
          onChange={(event) => {
            const files = Array.from(event.target.files)
            event.target.value = ''
            if (files.length) reviewFiles(files)
          }}
        />
        <span className="min-w-0 flex-1 text-sm text-gray-700 [overflow-wrap:anywhere]">
          {loaded ? roster.filename || `${kind === 'teacher' ? 'Teacher' : 'Student'} database loaded` : `No ${kind} database loaded`}
        </span>
        <Button variant="outline" size="sm" onClick={() => fileInput.current?.click()} disabled={isLoading || reading}>
          {reading ? 'Reading files…' : reviews.length ? 'Add files' : 'Choose files'}
        </Button>
      </div>
      {error && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
      {reviews.length > 0 && <RosterReview reviews={reviews} setReviews={setReviews} kind={kind} loaded={loaded}
        isLoading={isLoading || reading} upload={upload} close={() => { setReviews([]); setError('') }} />}
    </div>
  )
}
