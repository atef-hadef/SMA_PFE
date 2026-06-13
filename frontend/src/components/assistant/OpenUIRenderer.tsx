import { Component, useEffect, useState, type ReactNode } from 'react'
import { Renderer, type ActionEvent, type OpenUIError, type ParseResult } from '@openuidev/react-lang'
import type { SuggestedAction } from '../../services/assistantService'
import { flowPilotOpenUILibrary } from './openuiLibrary'

type OpenUIRendererProps = {
  content: string
  isStreaming?: boolean
  suggestedActions?: SuggestedAction[]
  onAction?: (action: SuggestedAction) => void
  onInvalidContent?: () => void
}

type ErrorBoundaryProps = {
  children: ReactNode
  onError: () => void
}

class OpenUIErrorBoundary extends Component<ErrorBoundaryProps, { hasError: boolean }> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error: unknown) {
    console.error('[openui] render failed', error instanceof Error ? error.message : 'unknown error')
    this.props.onError()
  }

  render() {
    if (this.state.hasError) return null
    return this.props.children
  }
}

function toSuggestedAction(event: ActionEvent, fallbackActions: SuggestedAction[]): SuggestedAction {
  const params = event.params ?? {}
  const label = typeof params.label === 'string' ? params.label : event.humanFriendlyMessage
  const actionType = typeof event.type === 'string' ? event.type : 'query'
  const matched = fallbackActions.find((action) => action.label === label)
  if (matched) return matched

  return {
    label,
    action_type: normalizeActionType(actionType),
    payload: {
      route: typeof params.route === 'string' ? params.route : undefined,
      target_id: typeof params.targetId === 'string' ? params.targetId : undefined,
      message: typeof params.message === 'string' ? params.message : event.humanFriendlyMessage,
      requires_confirmation: params.requiresConfirmation === true,
    },
  }
}

function normalizeActionType(actionType: string): SuggestedAction['action_type'] {
  if (actionType === 'navigate') return 'navigate'
  if (actionType === 'query') return 'query'
  if (actionType === 'open_details') return 'open_modal'
  return 'trigger_agent'
}

function hasRenderableRoot(result: ParseResult | null) {
  return Boolean(result?.root)
}

function OpenUIRenderer({
  content,
  isStreaming = false,
  suggestedActions = [],
  onAction,
  onInvalidContent,
}: OpenUIRendererProps) {
  const [hasRoot, setHasRoot] = useState(false)
  const trimmed = content.trim()

  useEffect(() => {
    if (!trimmed) onInvalidContent?.()
  }, [trimmed, onInvalidContent])

  if (!trimmed) return null

  function handleOpenUIErrors(errors: OpenUIError[]) {
    if (errors.length === 0) return
    console.error('[openui] parse/runtime issue', errors.map((error) => error.code).join(', '))
  }

  function handleParseResult(result: ParseResult | null) {
    const nextHasRoot = hasRenderableRoot(result)
    setHasRoot(nextHasRoot)
    if (!isStreaming && !nextHasRoot) onInvalidContent?.()
  }

  return (
    <OpenUIErrorBoundary onError={() => onInvalidContent?.()}>
      <div className="min-w-0 flex-1">
        <Renderer
          response={trimmed}
          library={flowPilotOpenUILibrary}
          isStreaming={isStreaming}
          onParseResult={handleParseResult}
          onError={handleOpenUIErrors}
          onAction={(event) => onAction?.(toSuggestedAction(event, suggestedActions))}
          queryLoader={
            <div className="rounded-xl border border-slate-700/60 bg-slate-900/70 px-4 py-3 text-xs text-slate-400">
              Chargement des données...
            </div>
          }
        />
        {!hasRoot && isStreaming ? (
          <div className="rounded-xl border border-slate-700/60 bg-slate-900/70 px-4 py-3 text-xs text-slate-400">
            Préparation de la visualisation...
          </div>
        ) : null}
      </div>
    </OpenUIErrorBoundary>
  )
}

export default OpenUIRenderer
