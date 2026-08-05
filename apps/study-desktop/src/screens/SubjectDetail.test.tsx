import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { test, expect, vi, beforeEach } from 'vitest'
import SubjectDetail from './SubjectDetail'

beforeEach(() => {
  ;(window as any).hermesStudy = {
    notesList: vi.fn(),
    sourceIngest: vi.fn(),
    chatSendMessage: vi.fn(),
  }
})

test('shows a hint when there are no notes yet', async () => {
  ;(window.hermesStudy.notesList as any).mockResolvedValue([])

  render(<SubjectDetail subjectId="s1" onBack={() => {}} />)

  await waitFor(() => expect(screen.getByText(/no notes yet/i)).toBeTruthy())
})

test('renders each note\'s summary and key concepts on the Notes tab', async () => {
  ;(window.hermesStudy.notesList as any).mockResolvedValue([
    { id: 'n1', summary_md: 'Newton\'s laws of motion.', key_concepts: ['inertia', 'force'], generated_at: '2026-01-01T00:00:00Z' },
  ])

  render(<SubjectDetail subjectId="s1" onBack={() => {}} />)

  await waitFor(() => expect(screen.getByText(/newton's laws of motion/i)).toBeTruthy())
  expect(screen.getByText(/inertia/i)).toBeTruthy()
  expect(screen.getByText(/force/i)).toBeTruthy()
})

test('adding a URL source calls sourceIngest and refreshes notes on success', async () => {
  const notesList = window.hermesStudy.notesList as any
  notesList
    .mockResolvedValueOnce([])
    .mockResolvedValueOnce([
      { id: 'n1', summary_md: 'A summary.', key_concepts: ['x'], generated_at: '2026-01-01T00:00:00Z' },
    ])
  ;(window.hermesStudy.sourceIngest as any).mockResolvedValue({ success: true, source_id: 'src-1', error: '' })

  render(<SubjectDetail subjectId="s1" onBack={() => {}} />)
  await waitFor(() => expect(screen.getByText(/no notes yet/i)).toBeTruthy())

  fireEvent.click(screen.getByRole('button', { name: /add source/i }))
  fireEvent.change(screen.getByLabelText(/url or file path/i), { target: { value: 'https://example.com/article' } })
  fireEvent.click(screen.getByRole('button', { name: /^ingest$/i }))

  expect(screen.getByText(/processing/i)).toBeTruthy()

  await waitFor(() => expect(screen.getByText('A summary.')).toBeTruthy())
  expect(window.hermesStudy.sourceIngest).toHaveBeenCalledWith('s1', 'url', 'https://example.com/article')
  expect(notesList).toHaveBeenCalledTimes(2)
})

test('shows an ingest error without crashing and stops the processing spinner', async () => {
  ;(window.hermesStudy.notesList as any).mockResolvedValue([])
  ;(window.hermesStudy.sourceIngest as any).mockResolvedValue({
    success: false,
    source_id: 'src-1',
    error: 'extraction failed',
  })

  render(<SubjectDetail subjectId="s1" onBack={() => {}} />)
  await waitFor(() => expect(screen.getByText(/no notes yet/i)).toBeTruthy())

  fireEvent.click(screen.getByRole('button', { name: /add source/i }))
  fireEvent.change(screen.getByLabelText(/url or file path/i), { target: { value: 'https://example.com/article' } })
  fireEvent.click(screen.getByRole('button', { name: /^ingest$/i }))

  await waitFor(() => expect(screen.getByText(/extraction failed/i)).toBeTruthy())
  expect(screen.queryByText(/processing/i)).toBeNull()
})

test('the back button calls onBack', async () => {
  ;(window.hermesStudy.notesList as any).mockResolvedValue([])
  const onBack = vi.fn()

  render(<SubjectDetail subjectId="s1" onBack={onBack} />)
  await waitFor(() => screen.getByText(/no notes yet/i))

  fireEvent.click(screen.getByText(/back to subjects/i))
  expect(onBack).toHaveBeenCalled()
})
