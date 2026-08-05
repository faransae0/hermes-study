import { render, screen } from '@testing-library/react'
import { test, expect } from 'vitest'
import App from './App'

test('renders the Hermes Study placeholder', () => {
  render(<App />)
  expect(screen.getByText('Hermes Study')).toBeTruthy()
})
