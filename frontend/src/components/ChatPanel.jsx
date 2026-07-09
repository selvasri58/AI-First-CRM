import { useEffect, useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Bot, Send, Mic, CheckCircle2 } from 'lucide-react'
import { addMessage, setSending } from '../slices/chatSlice'
import { setInteractionState } from '../slices/interactionSlice'
import { sendChatMessage } from '../api'

const PLACEHOLDER_TEXT =
  "Log interaction details here (e.g., \"Met Dr. Smith, discussed Prodo-X efficacy, positive sentiment, shared brochure\") or ask for help."

export default function ChatPanel({ threadId }) {
  const dispatch = useDispatch()
  const { messages, isSending } = useSelector((state) => state.chat)
  const [draft, setDraft] = useState('')
  const scrollRef = useRef(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, isSending])

  async function handleSend() {
    const text = draft.trim()
    if (!text || isSending) return

    dispatch(addMessage({ id: crypto.randomUUID(), role: 'user', text }))
    setDraft('')
    dispatch(setSending(true))

    try {
      const { reply, interaction_state } = await sendChatMessage(threadId, text)
      dispatch(setInteractionState(interaction_state))
      dispatch(
        addMessage({
          id: crypto.randomUUID(),
          role: 'assistant',
          text: reply,
          isSuccess: /logged successfully|updated!/i.test(reply),
        })
      )
    } catch (err) {
      dispatch(
        addMessage({
          id: crypto.randomUUID(),
          role: 'assistant',
          text:
            err?.response?.data?.detail ||
            'Something went wrong reaching the AI assistant. Please check the backend server and try again.',
          isError: true,
        })
      )
    } finally {
      dispatch(setSending(false))
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="px-6 py-5 border-b border-gray-200 bg-white flex items-center gap-2">
        <Bot size={18} className="text-blue-600" />
        <h1 className="text-lg font-semibold text-gray-900">AI Assistant</h1>
      </div>

      <div ref={scrollRef} className="chat-scroll flex-1 overflow-y-auto px-6 py-5 space-y-3">
        {messages.length === 0 && (
          <div className="max-w-[85%] rounded-xl rounded-tl-sm bg-blue-50 text-gray-700 text-sm px-4 py-3">
            {PLACEHOLDER_TEXT}
          </div>
        )}

        {messages.map((m) => (
          <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={[
                'max-w-[85%] rounded-xl px-4 py-3 text-sm whitespace-pre-wrap',
                m.role === 'user'
                  ? 'bg-blue-600 text-white rounded-tr-sm'
                  : m.isError
                  ? 'bg-red-50 text-red-700 rounded-tl-sm'
                  : m.isSuccess
                  ? 'bg-green-50 text-green-800 rounded-tl-sm'
                  : 'bg-blue-50 text-gray-700 rounded-tl-sm',
              ].join(' ')}
            >
              {m.isSuccess && (
                <CheckCircle2 size={14} className="inline mr-1.5 -mt-0.5 text-green-600" />
              )}
              {m.text}
            </div>
          </div>
        ))}

        {isSending && (
          <div className="flex justify-start">
            <div className="max-w-[60%] rounded-xl rounded-tl-sm bg-blue-50 text-gray-400 text-sm px-4 py-3 italic">
              AI Assistant is thinking...
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-gray-200 bg-white px-4 py-4">
        <div className="flex items-end gap-2 rounded-xl border border-gray-300 bg-white px-3 py-2 focus-within:ring-2 focus-within:ring-blue-100">
          <textarea
            rows={1}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe interaction..."
            className="flex-1 resize-none border-none outline-none text-sm py-1.5 max-h-28"
          />
          <button
            type="button"
            title="Voice input (not wired up in this build)"
            className="shrink-0 rounded-full p-2 text-white bg-emerald-500 hover:bg-emerald-600 transition-colors"
          >
            <Mic size={16} />
          </button>
          <button
            type="button"
            onClick={handleSend}
            disabled={isSending || !draft.trim()}
            className="shrink-0 inline-flex items-center gap-1.5 rounded-full bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2 transition-colors"
          >
            <Send size={14} />
            Log
          </button>
        </div>
      </div>
    </div>
  )
}
