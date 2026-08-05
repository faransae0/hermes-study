import { useEffect, useState } from 'react'
import type { StudySubjectListEntry } from '../types/hermes-study'

interface SubjectListProps {
  onSelectSubject: (subjectId: string) => void
}

export default function SubjectList({ onSelectSubject }: SubjectListProps) {
  const [subjects, setSubjects] = useState<StudySubjectListEntry[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newDescription, setNewDescription] = useState('')

  const loadSubjects = async () => {
    setLoading(true)
    const result = await window.hermesStudy.subjectList()
    if (Array.isArray(result)) {
      setSubjects(result)
      setError(null)
    } else {
      setError(result.error)
    }
    setLoading(false)
  }

  useEffect(() => {
    loadSubjects()
  }, [])

  const handleCreate = async () => {
    if (!newTitle.trim()) {
      return
    }
    const result = await window.hermesStudy.subjectCreate(newTitle.trim(), newDescription.trim() || undefined)
    if ('error' in result) {
      setError(result.error)
      return
    }
    setNewTitle('')
    setNewDescription('')
    setShowCreateForm(false)
    await loadSubjects()
  }

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Subjects</h1>
        <button
          className="rounded bg-neutral-800 px-3 py-1.5 text-sm text-white"
          onClick={() => setShowCreateForm((v) => !v)}
        >
          + New Subject
        </button>
      </div>

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      {showCreateForm && (
        <div className="mb-6 flex flex-col gap-2 rounded border border-neutral-200 p-4">
          <label className="text-sm font-medium" htmlFor="subject-title">
            Title
          </label>
          <input
            id="subject-title"
            className="rounded border border-neutral-300 px-2 py-1"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
          />
          <label className="text-sm font-medium" htmlFor="subject-description">
            Description (optional)
          </label>
          <input
            id="subject-description"
            className="rounded border border-neutral-300 px-2 py-1"
            value={newDescription}
            onChange={(e) => setNewDescription(e.target.value)}
          />
          <button className="mt-2 self-start rounded bg-neutral-800 px-3 py-1.5 text-sm text-white" onClick={handleCreate}>
            Create
          </button>
        </div>
      )}

      {!loading && subjects.length === 0 && (
        <p className="text-neutral-500">No subjects yet. Create one to get started.</p>
      )}

      <div className="grid grid-cols-3 gap-4">
        {subjects.map((subject) => (
          <button
            key={subject.id}
            className="rounded border border-neutral-200 p-4 text-left hover:border-neutral-400"
            onClick={() => onSelectSubject(subject.id)}
          >
            <div className="font-medium">{subject.title}</div>
            <div className="text-sm text-neutral-500">{subject.source_count} source(s)</div>
          </button>
        ))}
      </div>
    </div>
  )
}
