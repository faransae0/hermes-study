import { useState } from 'react'

interface ChatMessage {
  role: 'user' | 'assistant' | 'error'
  content: string
}

interface ChatPanelProps {
  subjectId: string
}

export default function ChatPanel({ subjectId }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)

  const handleSend = async () => {
    const text = input.trim()
    if (!text) {
      return
    }
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setInput('')
    setSending(true)

    const result = await window.hermesStudy.chatSendMessage(subjectId, text)
    setSending(false)

    if (result.error) {
      setMessages((prev) => [...prev, { role: 'error', content: result.error as string }])
      return
    }
    setMessages((prev) => [...prev, { role: 'assistant', content: result.reply as string }])
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2">
        {messages.map((message, index) => (
          <div
            key={index}
            data-testid={message.role === 'error' ? undefined : 'chat-message'}
            className={
              message.role === 'user'
                ? 'self-end rounded bg-neutral-800 px-3 py-1.5 text-sm text-white'
                : message.role === 'error'
                  ? 'text-sm text-red-600'
                  : 'self-start rounded bg-neutral-100 px-3 py-1.5 text-sm'
            }
          >
            {message.content}
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <label className="sr-only" htmlFor="chat-message-input">
          Message
        </label>
        <input
          id="chat-message-input"
          className="flex-1 rounded border border-neutral-300 px-2 py-1"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={sending}
        />
        <button
          className="rounded bg-neutral-800 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          onClick={handleSend}
          disabled={sending}
        >
          Send
        </button>
      </div>
    </div>
  )
}
