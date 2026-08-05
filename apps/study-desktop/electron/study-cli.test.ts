import assert from 'node:assert/strict'
import { test } from 'vitest'
import {
  buildChatSendMessageArgs,
  buildNotesListArgs,
  buildSourceIngestArgs,
  buildSubjectCreateArgs,
  buildSubjectListArgs,
} from './study-cli'

test('buildSubjectCreateArgs without a description', () => {
  assert.deepEqual(buildSubjectCreateArgs('Biology'), ['study', 'subject', 'create', 'Biology', '--json'])
})

test('buildSubjectCreateArgs with a description', () => {
  assert.deepEqual(buildSubjectCreateArgs('Biology', 'Intro course'), [
    'study',
    'subject',
    'create',
    'Biology',
    '--json',
    '--description',
    'Intro course',
  ])
})

test('buildSubjectListArgs', () => {
  assert.deepEqual(buildSubjectListArgs(), ['study', 'subject', 'list', '--json'])
})

test('buildSourceIngestArgs', () => {
  assert.deepEqual(buildSourceIngestArgs('subj-1', 'url', 'https://example.com'), [
    'study',
    'ingest',
    'subj-1',
    'url',
    'https://example.com',
    '--json',
  ])
})

test('buildNotesListArgs', () => {
  assert.deepEqual(buildNotesListArgs('subj-1'), ['study', 'notes', 'subj-1', '--json'])
})

test('buildChatSendMessageArgs', () => {
  assert.deepEqual(buildChatSendMessageArgs('subj-1', 'What is inertia?'), [
    'study',
    'chat-turn',
    'subj-1',
    '--message',
    'What is inertia?',
  ])
})
