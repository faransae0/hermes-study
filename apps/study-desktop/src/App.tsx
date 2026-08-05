import { useState } from 'react'
import SubjectList from './screens/SubjectList'

export default function App() {
  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(null)

  if (selectedSubjectId) {
    return (
      <div className="p-6">
        <button className="mb-4 text-sm text-neutral-500" onClick={() => setSelectedSubjectId(null)}>
          ← Back to Subjects
        </button>
        <p className="text-neutral-500">Subject detail for {selectedSubjectId} (coming in Task 5)</p>
      </div>
    )
  }

  return <SubjectList onSelectSubject={setSelectedSubjectId} />
}
