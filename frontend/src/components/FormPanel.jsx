import { useSelector } from 'react-redux'
import { Search, Mic, PlusCircle } from 'lucide-react'

// Every field below is `readOnly` (text inputs/textareas) or wrapped in a
// `pointer-events-none` div (select/radio, which HTML has no readOnly for).
// Nothing in this file ever dispatches a Redux action - it only reads
// `state.interaction` and renders it. See slices/interactionSlice.js: there
// is intentionally no "setField" action for the UI to call.

function FieldLabel({ children }) {
  return <label className="block text-sm font-medium text-gray-700 mb-1">{children}</label>
}

function ReadOnlyText({ value, placeholder }) {
  return (
    <input
      type="text"
      readOnly
      tabIndex={-1}
      value={value ?? ''}
      placeholder={placeholder}
      className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 cursor-default focus:outline-none"
    />
  )
}

export default function FormPanel() {
  const interaction = useSelector((state) => state.interaction)

  const sentimentOptions = [
    { value: 'Positive', dot: 'bg-amber-500' },
    { value: 'Neutral', dot: 'bg-gray-400' },
    { value: 'Negative', dot: 'bg-red-500' },
  ]

  return (
    <div className="h-full overflow-y-auto bg-white border-r border-gray-200">
      <div className="px-6 py-5 border-b border-gray-100">
        <h1 className="text-lg font-semibold text-gray-900">Log HCP Interaction</h1>
      </div>

      <div className="px-6 py-5 space-y-5">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-400">
          Interaction Details
        </h2>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <FieldLabel>HCP Name</FieldLabel>
            <ReadOnlyText value={interaction.hcp_name} placeholder="Search or select HCP..." />
          </div>
          <div>
            <FieldLabel>Interaction Type</FieldLabel>
            <div className="pointer-events-none">
              <select
                tabIndex={-1}
                value={interaction.interaction_type ?? ''}
                onChange={() => {}}
                className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 cursor-default focus:outline-none appearance-none"
              >
                <option value="">Select type...</option>
                <option value="Meeting">Meeting</option>
                <option value="Call">Call</option>
                <option value="Conference">Conference</option>
              </select>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <FieldLabel>Date</FieldLabel>
            <input
              type="date"
              readOnly
              tabIndex={-1}
              value={interaction.date ?? ''}
              onChange={() => {}}
              className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 cursor-default focus:outline-none"
            />
          </div>
          <div>
            <FieldLabel>Time</FieldLabel>
            <input
              type="time"
              readOnly
              tabIndex={-1}
              value={interaction.time ?? ''}
              onChange={() => {}}
              className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 cursor-default focus:outline-none"
            />
          </div>
        </div>

        <div>
          <FieldLabel>Attendees</FieldLabel>
          <ReadOnlyText value={interaction.attendees} placeholder="Enter names or search..." />
        </div>

        <div>
          <FieldLabel>Topics Discussed</FieldLabel>
          <textarea
            readOnly
            tabIndex={-1}
            rows={3}
            value={interaction.topics ?? ''}
            placeholder="Enter key discussion points..."
            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 cursor-default focus:outline-none resize-none"
          />
          <button
            type="button"
            tabIndex={-1}
            className="pointer-events-none mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-blue-600"
          >
            <Mic size={12} />
            Summarize from Voice Note (Requires Consent)
          </button>
        </div>

        <div className="border border-gray-200 rounded-md p-4 space-y-4">
          <h3 className="text-sm font-semibold text-gray-700">
            Materials Shared / Samples Distributed
          </h3>

          <div>
            <FieldLabel>Materials Shared</FieldLabel>
            <div className="flex items-center gap-2">
              <div className="flex-1 min-h-9 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 flex flex-wrap gap-1 items-center">
                {interaction.materials_shared.length === 0 ? (
                  <span className="text-gray-400">No materials added</span>
                ) : (
                  interaction.materials_shared.map((m) => (
                    <span
                      key={m}
                      className="inline-block rounded-full bg-blue-50 text-blue-700 text-xs px-2 py-0.5"
                    >
                      {m}
                    </span>
                  ))
                )}
              </div>
              <button
                type="button"
                tabIndex={-1}
                className="pointer-events-none inline-flex items-center gap-1 rounded-md border border-gray-300 px-2.5 py-1.5 text-xs text-gray-500"
              >
                <Search size={12} />
                Search/Add
              </button>
            </div>
          </div>

          <div>
            <FieldLabel>Samples Distributed</FieldLabel>
            <div className="flex items-center gap-2">
              <div className="flex-1 min-h-9 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 flex flex-wrap gap-1 items-center">
                {interaction.samples_distributed.length === 0 ? (
                  <span className="text-gray-400">No samples added</span>
                ) : (
                  interaction.samples_distributed.map((s) => (
                    <span
                      key={s}
                      className="inline-block rounded-full bg-emerald-50 text-emerald-700 text-xs px-2 py-0.5"
                    >
                      {s}
                    </span>
                  ))
                )}
              </div>
              <button
                type="button"
                tabIndex={-1}
                className="pointer-events-none inline-flex items-center gap-1 rounded-md border border-gray-300 px-2.5 py-1.5 text-xs text-gray-500"
              >
                <PlusCircle size={12} />
                Add Sample
              </button>
            </div>
          </div>
        </div>

        <div>
          <FieldLabel>Observed/Inferred HCP Sentiment</FieldLabel>
          <div className="pointer-events-none flex items-center gap-5">
            {sentimentOptions.map((opt) => (
              <label key={opt.value} className="flex items-center gap-1.5 text-sm text-gray-700">
                <input
                  type="radio"
                  tabIndex={-1}
                  name="sentiment"
                  checked={interaction.sentiment === opt.value}
                  onChange={() => {}}
                  className="accent-blue-600"
                />
                <span className={`inline-block w-2 h-2 rounded-full ${opt.dot}`} />
                {opt.value}
              </label>
            ))}
          </div>
        </div>

        <div>
          <FieldLabel>Outcomes</FieldLabel>
          <textarea
            readOnly
            tabIndex={-1}
            rows={2}
            value={interaction.outcomes ?? ''}
            placeholder="Key outcomes or agreements..."
            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 cursor-default focus:outline-none resize-none"
          />
        </div>

        <div>
          <FieldLabel>Follow-up Actions</FieldLabel>
          <textarea
            readOnly
            tabIndex={-1}
            rows={3}
            value={interaction.follow_up_actions.join('\n')}
            placeholder="Follow-up actions will appear here..."
            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 cursor-default focus:outline-none resize-none"
          />
        </div>
      </div>
    </div>
  )
}
