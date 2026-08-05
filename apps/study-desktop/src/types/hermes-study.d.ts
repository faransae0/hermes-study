export interface StudySubject {
  id: string
  title: string
  description: string
  created_at: string
}

export interface StudySubjectListEntry {
  id: string
  title: string
  source_count: number
}

export interface StudyIngestResult {
  success: boolean
  source_id: string
  error: string
}

export interface StudyNote {
  id: string
  summary_md: string
  key_concepts: string[]
  generated_at: string
}

export interface StudyChatResult {
  reply: string | null
  error: string | null
}

export interface StudyErrorResult {
  error: string
}

export interface HermesStudyApi {
  subjectCreate: (title: string, description?: string) => Promise<StudySubject | StudyErrorResult>
  subjectList: () => Promise<StudySubjectListEntry[] | StudyErrorResult>
  sourceIngest: (subjectId: string, type: string, origin: string) => Promise<StudyIngestResult>
  notesList: (subjectId: string) => Promise<StudyNote[] | StudyErrorResult>
  chatSendMessage: (subjectId: string, message: string) => Promise<StudyChatResult>
}

declare global {
  interface Window {
    hermesStudy: HermesStudyApi
  }
}
