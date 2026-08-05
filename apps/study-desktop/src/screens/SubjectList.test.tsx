import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { test, expect, vi, beforeEach } from 'vitest'
import SubjectList from './SubjectList'

beforeEach(() => {
  ;(window as any).hermesStudy = {
    subjectList: vi.fn(),
    subjectCreate: vi.fn(),
  }
})

test('shows a hint when there are no subjects', async () => {
  ;(window.hermesStudy.subjectList as any).mockResolvedValue([])

  render(<SubjectList onSelectSubject={() => {}} />)

  await waitFor(() => expect(screen.getByText(/no subjects yet/i)).toBeTruthy())
})

test('renders each subject as a card with its source count', async () => {
  ;(window.hermesStudy.subjectList as any).mockResolvedValue([
    { id: 's1', title: 'Biology', source_count: 3 },
    { id: 's2', title: 'History', source_count: 0 },
  ])

  render(<SubjectList onSelectSubject={() => {}} />)

  await waitFor(() => expect(screen.getByText('Biology')).toBeTruthy())
  expect(screen.getByText('History')).toBeTruthy()
  expect(screen.getByText(/3 source/i)).toBeTruthy()
})

test('clicking a subject card calls onSelectSubject with its id', async () => {
  ;(window.hermesStudy.subjectList as any).mockResolvedValue([{ id: 's1', title: 'Biology', source_count: 3 }])
  const onSelectSubject = vi.fn()

  render(<SubjectList onSelectSubject={onSelectSubject} />)

  await waitFor(() => screen.getByText('Biology'))
  fireEvent.click(screen.getByText('Biology'))

  expect(onSelectSubject).toHaveBeenCalledWith('s1')
})

test('creating a subject calls subjectCreate and refreshes the list', async () => {
  const list = window.hermesStudy.subjectList as any
  list.mockResolvedValueOnce([]).mockResolvedValueOnce([{ id: 's1', title: 'Chemistry', source_count: 0 }])
  ;(window.hermesStudy.subjectCreate as any).mockResolvedValue({
    id: 's1',
    title: 'Chemistry',
    description: '',
    created_at: '2026-01-01T00:00:00Z',
  })

  render(<SubjectList onSelectSubject={() => {}} />)

  await waitFor(() => expect(screen.getByText(/no subjects yet/i)).toBeTruthy())

  fireEvent.click(screen.getByRole('button', { name: /new subject/i }))
  fireEvent.change(screen.getByLabelText(/title/i), { target: { value: 'Chemistry' } })
  fireEvent.click(screen.getByRole('button', { name: /^create$/i }))

  await waitFor(() => expect(screen.getByText('Chemistry')).toBeTruthy())
  expect(window.hermesStudy.subjectCreate).toHaveBeenCalledWith('Chemistry', undefined)
  expect(list).toHaveBeenCalledTimes(2)
})

test('shows the error when subjectList returns an error shape', async () => {
  ;(window.hermesStudy.subjectList as any).mockResolvedValue({ error: 'database is locked' })

  render(<SubjectList onSelectSubject={() => {}} />)

  await waitFor(() => expect(screen.getByText(/database is locked/i)).toBeTruthy())
})
