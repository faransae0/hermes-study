import { useState } from 'react'
import SubjectDetail from './screens/SubjectDetail'
import SubjectList from './screens/SubjectList'

export default function App() {
  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(null)

  if (selectedSubjectId) {
    return <SubjectDetail subjectId={selectedSubjectId} onBack={() => setSelectedSubjectId(null)} />
  }

  return <SubjectList onSelectSubject={setSelectedSubjectId} />
}
