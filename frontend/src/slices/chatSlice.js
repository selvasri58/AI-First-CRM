import { createSlice } from '@reduxjs/toolkit'

const chatSlice = createSlice({
  name: 'chat',
  initialState: {
    messages: [], // { id, role: 'user' | 'assistant', text, isSuccess }
    isSending: false,
  },
  reducers: {
    addMessage: (state, action) => {
      state.messages.push(action.payload)
    },
    setSending: (state, action) => {
      state.isSending = action.payload
    },
  },
})

export const { addMessage, setSending } = chatSlice.actions
export default chatSlice.reducer
