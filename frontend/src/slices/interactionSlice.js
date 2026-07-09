import { createSlice } from '@reduxjs/toolkit'

const emptyInteraction = {
  interaction_id: null,
  hcp_id: null,
  hcp_name: null,
  interaction_type: null,
  date: null,
  time: null,
  attendees: null,
  topics: null,
  materials_shared: [],
  samples_distributed: [],
  sentiment: null,
  outcomes: null,
  follow_up_actions: [],
}

const interactionSlice = createSlice({
  name: 'interaction',
  initialState: emptyInteraction,
  reducers: {
    // The ONLY way this slice ever changes is by replacing it wholesale with
    // whatever the backend agent returns after a tool runs. There is no
    // "setField" reducer on purpose - per the Golden Rule, the UI is not
    // allowed to author changes to this state itself.
    setInteractionState: (state, action) => {
      return { ...emptyInteraction, ...action.payload }
    },
    resetInteractionState: () => emptyInteraction,
  },
})

export const { setInteractionState, resetInteractionState } = interactionSlice.actions
export default interactionSlice.reducer
