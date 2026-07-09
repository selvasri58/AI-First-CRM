import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const client = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
})

export async function sendChatMessage(threadId, message) {
  const { data } = await client.post('/api/chat', {
    thread_id: threadId,
    message,
  })
  return data // { reply, interaction_state }
}

export async function fetchInteractionState(threadId) {
  const { data } = await client.get(`/api/interaction-state/${threadId}`)
  return data
}
