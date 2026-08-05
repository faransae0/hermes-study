export function buildSubjectCreateArgs(title: string, description?: string): string[] {
  const args = ['study', 'subject', 'create', title, '--json']
  if (description) {
    args.push('--description', description)
  }
  return args
}

export function buildSubjectListArgs(): string[] {
  return ['study', 'subject', 'list', '--json']
}

export function buildSourceIngestArgs(subjectId: string, type: string, origin: string): string[] {
  return ['study', 'ingest', subjectId, type, origin, '--json']
}

export function buildNotesListArgs(subjectId: string): string[] {
  return ['study', 'notes', subjectId, '--json']
}

// chat-turn's parser sets json=True by default (Plan 3a) — no --json flag needed.
export function buildChatSendMessageArgs(subjectId: string, message: string): string[] {
  return ['study', 'chat-turn', subjectId, '--message', message]
}
