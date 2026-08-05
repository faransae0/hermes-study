import { useEffect, useState } from 'react'
import type { StudyNote } from '../types/hermes-study'

interface SubjectDetailProps {
  subjectId: string
  onBack: () => void
}

const SOURCE_TYPES = ['url', 'pdf', 'youtube'] as const
type SourceType = (typeof SOURCE_TYPES)[number]

export default function SubjectDetail({ subjectId, onBack }: SubjectDetailProps) {
  const [activeTab, setActiveTab] = useState<'notes' | 'chat'>('notes')
  const [notes, setNotes] = useState<StudyNote[]>([])
  const [notesError, setNotesError] = useState<string | null>(null)
  const [notesLoading, setNotesLoading] = useState(true)

  const [showAddSource, setShowAddSource] = useState(false)
  const [sourceType, setSourceType] = useState<SourceType>('url')
  const [origin, setOrigin] = useState('')
  const [ingesting, setIngesting] = useState(false)
  const [ingestError, setIngestError] = useState<string | null>(null)

  const loadNotes = async () => {
    setNotesLoading(true)
    const result = await window.hermesStudy.notesList(subjectId)
    if (Array.isArray(result)) {
      setNotes(result)
      setNotesError(null)
    } else {
      setNotesError(result.error)
    }
    setNotesLoading(false)
  }

  useEffect(() => {
    loadNotes()
  }, [subjectId])

  const handleIngest = async () => {
    if (!origin.trim()) {
      return
    }
    setIngesting(true)
    setIngestError(null)
    const result = await window.hermesStudy.sourceIngest(subjectId, sourceType, origin.trim())
    setIngesting(false)
    if (!result.success) {
      setIngestError(result.error)
      return
    }
    setOrigin('')
    setShowAddSource(false)
    await loadNotes()
  }

  return (
    <div className="p-6">
      <button className="mb-4 text-sm text-neutral-500" onClick={onBack}>
        ← Back to Subjects
      </button>

      <div className="mb-4 flex items-center justify-between">
        <div className="flex gap-4">
          <button
            className={`text-sm ${activeTab === 'notes' ? 'font-semibold' : 'text-neutral-500'}`}
            onClick={() => setActiveTab('notes')}
          >
            Notes
          </button>
          <button
            className={`text-sm ${activeTab === 'chat' ? 'font-semibold' : 'text-neutral-500'}`}
            onClick={() => setActiveTab('chat')}
          >
            Chat
          </button>
        </div>
        <button
          className="rounded bg-neutral-800 px-3 py-1.5 text-sm text-white"
          onClick={() => setShowAddSource((v) => !v)}
        >
          Add Source
        </button>
      </div>

      {showAddSource && (
        <div className="mb-6 flex flex-col gap-2 rounded border border-neutral-200 p-4">
          <label className="text-sm font-medium" htmlFor="source-type">
            Type
          </label>
          <select
            id="source-type"
            className="rounded border border-neutral-300 px-2 py-1"
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value as SourceType)}
          >
            {SOURCE_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <label className="text-sm font-medium" htmlFor="source-origin">
            URL or file path
          </label>
          <input
            id="source-origin"
            className="rounded border border-neutral-300 px-2 py-1"
            value={origin}
            onChange={(e) => setOrigin(e.target.value)}
          />
          {ingestError && <p className="text-sm text-red-600">{ingestError}</p>}
          {ingesting && <p className="text-sm text-neutral-500">Processing…</p>}
          <button
            className="mt-2 self-start rounded bg-neutral-800 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            onClick={handleIngest}
            disabled={ingesting}
          >
            Ingest
          </button>
        </div>
      )}

      {activeTab === 'notes' && (
        <div>
          {notesError && <p className="text-sm text-red-600">{notesError}</p>}
          {!notesLoading && notes.length === 0 && !notesError && (
            <p className="text-neutral-500">No notes yet for this subject.</p>
          )}
          <div className="flex flex-col gap-4">
            {notes.map((note) => (
              <div key={note.id} className="rounded border border-neutral-200 p-4">
                <p className="mb-2 whitespace-pre-wrap">{note.summary_md}</p>
                <div className="flex flex-wrap gap-1">
                  {note.key_concepts.map((concept) => (
                    <span key={concept} className="rounded bg-neutral-100 px-2 py-0.5 text-xs">
                      {concept}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'chat' && <p className="text-neutral-500">Chat tab (coming in Task 6)</p>}
    </div>
  )
}
