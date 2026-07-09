import { useMemo } from 'react'
import FormPanel from './components/FormPanel'
import ChatPanel from './components/ChatPanel'

export default function App() {
  // One thread_id per browser session = one "Log HCP Interaction" screen's
  // worth of conversation memory on the backend (LangGraph checkpointer).
  // Persisted in sessionStorage so a page refresh doesn't lose context.
  const threadId = useMemo(() => {
    const existing = sessionStorage.getItem('hcp_crm_thread_id')
    if (existing) return existing
    const fresh = crypto.randomUUID()
    sessionStorage.setItem('hcp_crm_thread_id', fresh)
    return fresh
  }, [])

  return (
    <div className="h-screen w-screen grid grid-cols-2 overflow-hidden">
      <FormPanel />
      <ChatPanel threadId={threadId} />
    </div>
  )
}
