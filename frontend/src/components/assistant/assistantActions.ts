import type { SuggestedAction } from '../../services/assistantService'

const SAFE_ACTIONS: SuggestedAction['action_type'][] = [
  'navigate',
  'query',
  'refresh',
  'filter',
  'open_details',
  'open_modal',
]

function assistantActionRequiresConfirmation(action: SuggestedAction) {
  if (action.payload['requires_confirmation'] === true || action.payload['requiresConfirmation'] === true) {
    return true
  }
  return !SAFE_ACTIONS.includes(action.action_type)
}

function createIdempotencyKey(action: SuggestedAction) {
  const base = `${action.action_type}:${action.label}:${Date.now()}`
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `${base}:${crypto.randomUUID()}`
  }
  return `${base}:${Math.random().toString(36).slice(2)}`
}

export { assistantActionRequiresConfirmation, createIdempotencyKey }
