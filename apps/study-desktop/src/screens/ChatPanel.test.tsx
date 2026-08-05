import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { test, expect, vi, beforeEach } from 'vitest'
import ChatPanel from './ChatPanel'

beforeEach(() => {
  ;(window as any).hermesStudy = {
    chatSendMessage: vi.fn(),
  }
})

test('sends a message and displays the reply', async () => {
  ;(window.hermesStudy.chatSendMessage as any).mockResolvedValue({
    reply: 'Inertia is the tendency to resist changes in motion.',
    error: null,
  })

  render(<ChatPanel subjectId="s1" />)

  fireEvent.change(screen.getByLabelText(/message/i), { target: { value: 'What is inertia?' } })
  fireEvent.click(screen.getByRole('button', { name: /send/i }))

  expect(screen.getByText('What is inertia?')).toBeTruthy()
  await waitFor(() =>
    expect(screen.getByText('Inertia is the tendency to resist changes in motion.')).toBeTruthy(),
  )
  expect(window.hermesStudy.chatSendMessage).toHaveBeenCalledWith('s1', 'What is inertia?')
})

test('clears the input after sending', async () => {
  ;(window.hermesStudy.chatSendMessage as any).mockResolvedValue({ reply: 'Sure.', error: null })

  render(<ChatPanel subjectId="s1" />)

  const input = screen.getByLabelText(/message/i) as HTMLInputElement
  fireEvent.change(input, { target: { value: 'Hi' } })
  fireEvent.click(screen.getByRole('button', { name: /send/i }))

  await waitFor(() => expect(screen.getByText('Sure.')).toBeTruthy())
  expect(input.value).toBe('')
})

test('shows the error inline instead of a reply bubble when chatSendMessage fails', async () => {
  ;(window.hermesStudy.chatSendMessage as any).mockResolvedValue({ reply: null, error: 'rate limit exceeded' })

  render(<ChatPanel subjectId="s1" />)

  fireEvent.change(screen.getByLabelText(/message/i), { target: { value: 'Hi' } })
  fireEvent.click(screen.getByRole('button', { name: /send/i }))

  await waitFor(() => expect(screen.getByText(/rate limit exceeded/i)).toBeTruthy())
})

test('does not send an empty message', () => {
  render(<ChatPanel subjectId="s1" />)

  fireEvent.click(screen.getByRole('button', { name: /send/i }))

  expect(window.hermesStudy.chatSendMessage).not.toHaveBeenCalled()
})

test('multiple turns accumulate in order', async () => {
  const send = window.hermesStudy.chatSendMessage as any
  send.mockResolvedValueOnce({ reply: 'First reply.', error: null })
  send.mockResolvedValueOnce({ reply: 'Second reply.', error: null })

  render(<ChatPanel subjectId="s1" />)

  fireEvent.change(screen.getByLabelText(/message/i), { target: { value: 'First question' } })
  fireEvent.click(screen.getByRole('button', { name: /send/i }))
  await waitFor(() => expect(screen.getByText('First reply.')).toBeTruthy())

  fireEvent.change(screen.getByLabelText(/message/i), { target: { value: 'Second question' } })
  fireEvent.click(screen.getByRole('button', { name: /send/i }))
  await waitFor(() => expect(screen.getByText('Second reply.')).toBeTruthy())

  const messages = screen.getAllByTestId('chat-message')
  expect(messages.map((m) => m.textContent)).toEqual([
    'First question',
    'First reply.',
    'Second question',
    'Second reply.',
  ])
})
