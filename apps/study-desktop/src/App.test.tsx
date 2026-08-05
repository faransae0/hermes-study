import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { test, expect, vi, beforeEach } from 'vitest'
import App from './App'

beforeEach(() => {
  ;(window as any).hermesStudy = {
    subjectList: vi.fn().mockResolvedValue([{ id: 's1', title: 'Biology', source_count: 1 }]),
    subjectCreate: vi.fn(),
    notesList: vi.fn().mockResolvedValue([]),
    sourceIngest: vi.fn(),
    chatSendMessage: vi.fn(),
  }
})

test('starts on the subject list', async () => {
  render(<App />)
  await waitFor(() => expect(screen.getByText('Biology')).toBeTruthy())
})

test('selecting a subject switches to its detail view, and back returns to the list', async () => {
  render(<App />)
  await waitFor(() => screen.getByText('Biology'))

  fireEvent.click(screen.getByText('Biology'))
  await waitFor(() => expect(screen.getByText(/no notes yet/i)).toBeTruthy())

  fireEvent.click(screen.getByText(/back to subjects/i))
  await waitFor(() => expect(screen.getByText('Biology')).toBeTruthy())
})
