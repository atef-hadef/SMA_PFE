import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import AssistantChartRenderer from '../components/assistant/AssistantChartRenderer'
import OpenUIRenderer from '../components/assistant/OpenUIRenderer'
import { assistantActionRequiresConfirmation } from '../components/assistant/assistantActions'
import { Icon, type IconName } from '../components/common'
import {
  sendAssistantMessage,
  type AssistantChatResponse,
  type AssistantHistoryMessage,
  type AssistantIntent,
  type SuggestedAction,
} from '../services/assistantService'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type MessageRole = 'user' | 'assistant'

type ChatMessage = {
  id: string
  role: MessageRole
  text: string
  response?: AssistantChatResponse
  isLoading?: boolean
  loadingPhase?: number
  error?: string
}

// ---------------------------------------------------------------------------
// Intent metadata — labels, tones, titles, insights
// ---------------------------------------------------------------------------

const INTENT_LABELS: Record<string, string> = {
  crm_summary: 'Analyse CRM',
  crm_priority_analysis: 'Priorités CRM',
  crm_status_distribution: 'Statuts CRM',
  crm_conversion_analysis: 'Conversion CRM',
  crm_followup_recommendations: 'Relances CRM',
  crm_draft_review_summary: 'Brouillons CRM',
  crm_value_analysis: 'Valeur pipeline',
  crm_comparison: 'Comparaison CRM',
  leave_summary: 'Analyse congés',
  leave_status_distribution: 'Statuts congés',
  leave_pending_approvals: 'Approbations manager',
  leave_block_reasons: 'Blocages congés',
  leave_balance_block_analysis: 'Solde congés',
  leave_overlap_block_analysis: 'Chevauchements',
  leave_approval_rate: "Taux d'approbation",
  business_summary: 'Résumé métier',
  today_actions: 'Actions du jour',
  automation_health: 'Automatisations',
  general: 'Assistant',
  out_of_scope: 'Hors périmètre',
  unknown: 'Non reconnu',
  // legacy
  crm_query: 'CRM',
  leave_query: 'Congés',
}

const INTENT_BADGE_TONE: Record<string, string> = {
  crm_summary: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  crm_priority_analysis: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  crm_status_distribution: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  crm_conversion_analysis: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  crm_followup_recommendations: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  crm_draft_review_summary: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  crm_value_analysis: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  crm_comparison: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  leave_summary: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  leave_status_distribution: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  leave_pending_approvals: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  leave_block_reasons: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
  leave_balance_block_analysis: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  leave_overlap_block_analysis: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  leave_approval_rate: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  business_summary: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  today_actions: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  automation_health: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
  general: 'bg-slate-700/40 text-slate-300 border-slate-700',
  out_of_scope: 'bg-slate-700/40 text-slate-400 border-slate-700',
  unknown: 'bg-slate-700/40 text-slate-400 border-slate-700',
  crm_query: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  leave_query: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
}

const INTENT_INSIGHTS: Record<string, string> = {
  crm_priority_analysis: "Cette analyse identifie les leads qui nécessitent un traitement commercial prioritaire.",
  crm_status_distribution: "Cette vue montre comment les leads sont répartis dans le pipeline commercial.",
  crm_conversion_analysis: "Cette analyse mesure l'efficacité du pipeline CRM à convertir les leads en clients.",
  crm_followup_recommendations: "Ces recommandations identifient les prospects actifs qui nécessitent une action commerciale.",
  crm_draft_review_summary: "Ces brouillons ont été générés par l'IA et attendent une validation humaine avant envoi.",
  crm_value_analysis: "Cette analyse évalue la valeur commerciale potentielle du pipeline CRM.",
  crm_summary: "Vue d'ensemble complète du pipeline CRM avec les indicateurs clés.",
  crm_comparison: "Cette comparaison met en regard l'activité CRM de cette semaine et de la semaine précédente, variations calculées côté serveur.",
  leave_status_distribution: "Cette vue montre la répartition des demandes de congé selon leur état actuel.",
  leave_pending_approvals: "Ces demandes nécessitent une décision managériale pour avancer dans le processus.",
  leave_block_reasons: "Cette analyse explique pourquoi certaines demandes ne sont pas transmises au manager ou à Odoo.",
  leave_balance_block_analysis: "Ces demandes ont été bloquées car les jours demandés dépassent le solde disponible.",
  leave_overlap_block_analysis: "Ces demandes ont été bloquées en raison d'un conflit de dates avec d'autres congés.",
  leave_approval_rate: "Cet indicateur mesure l'efficacité du processus d'approbation des congés.",
  leave_summary: "Vue d'ensemble complète des demandes de congé avec les indicateurs clés.",
  business_summary: "Vue consolidée des actions importantes sur les deux processus métier : CRM et Congés.",
  today_actions: "Liste des éléments prioritaires nécessitant une attention immédiate aujourd'hui.",
  automation_health: "Vue de santé des automatisations à partir du monitoring des exécutions.",
  general: "Je suis FlowPilot AI, votre assistant business pour le CRM et les demandes de congé.",
  out_of_scope: "Cet assistant est spécialisé sur les processus CRM et Demandes de congé uniquement.",
  unknown: "Je n'ai pas pu identifier le sujet de votre question.",
}

// ---------------------------------------------------------------------------
// Loading messages — rotated for professional feel
// ---------------------------------------------------------------------------

const LOADING_MESSAGES = [
  "Analyse des données autorisées...",
  "Calcul des indicateurs depuis PostgreSQL...",
  "Préparation de la meilleure vue métier...",
  "Vérification des sources et actions possibles...",
]

const QUICK_PROMPTS = [
  'Combien de hot leads avons-nous ?',
  'Donne-moi un résumé CRM de cette semaine.',
  "Quelle est la santé des automatisations ?",
  'Liste les hot leads qui nécessitent une action.',
]

// ---------------------------------------------------------------------------
// User message bubble
// ---------------------------------------------------------------------------

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div
        className="max-w-[60%] rounded-xl border border-[rgba(16,185,129,0.2)] px-4 py-2.5 text-[14px] text-[#e6edf3] shadow-sm"
        style={{ backgroundColor: 'rgba(16,185,129,0.12)' }}
      >
        <p className="leading-6 whitespace-pre-wrap">{text}</p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Loading bubble
// ---------------------------------------------------------------------------

function LoadingBubble({ phase }: { phase: number }) {
  const msg = LOADING_MESSAGES[phase % LOADING_MESSAGES.length]
  return (
    <div className="flex justify-start gap-3">
      <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-emerald-500/30 bg-emerald-500/10">
        <Icon name="spark" size={16} className="text-emerald-300" />
      </div>
      <div className="flex items-center gap-3 rounded-2xl rounded-tl-sm border border-slate-700/60 bg-slate-900/80 px-4 py-3 shadow-sm">
        <span className="flex gap-1">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-bounce"
              style={{ animationDelay: `${i * 0.18}s` }}
            />
          ))}
        </span>
        <span className="text-xs text-slate-400">{msg}</span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Error bubble
// ---------------------------------------------------------------------------

function ErrorBubble({ message }: { message: string }) {
  return (
    <div className="flex justify-start gap-3">
      <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-rose-500/30 bg-rose-500/10">
        <Icon name="alert" size={16} className="text-rose-300" />
      </div>
      <div className="max-w-[85%] overflow-hidden rounded-2xl rounded-tl-sm border border-rose-500/30 bg-rose-950/20 shadow-sm">
        <div className="flex items-center gap-2 border-b border-rose-500/20 px-4 py-2.5">
          <Icon name="alert" size={13} className="shrink-0 text-rose-400" />
          <p className="text-xs font-semibold text-rose-300">Erreur de connexion</p>
        </div>
        <div className="px-4 py-3">
          <p className="text-sm text-rose-200/80">{message}</p>
          <p className="mt-2 text-xs text-slate-500">
            Vérifiez que le backend FastAPI est démarré sur le port 8000.
          </p>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Helpers — highlighted answer text + humanized source labels + action icons
// ---------------------------------------------------------------------------

/** Inline-highlight business numbers (e.g. "3 leads", "5 demandes") without dangerouslySetInnerHTML. */
function HighlightedAnswer({ text }: { text: string }) {
  const regex = /(\d+(?:[.,]\d+)?)\s*(lead|leads|prospect|prospects|client|clients|demande|demandes|cong[eé]|cong[eé]s|brouillon|brouillons|e[-\s]?mail|emails?)/gi
  const parts: ReactNode[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null
  let key = 0
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index))
    }
    parts.push(
      <strong key={`hl-${key++}`} className="font-semibold text-emerald-300">
        {match[0]}
      </strong>,
    )
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex))
  return <p className="text-[15px] leading-7 text-slate-100">{parts}</p>
}

/** Map a raw source title (often a DB table name) to a friendly label + icon name. */
function sourceLabel(rawTitle: string): { label: string; icon: 'crm' | 'leave' | 'file' | 'spark' } {
  const t = rawTitle.toLowerCase()
  if (t.includes('crm_email_draft') || t.includes('email_draft') || t.includes('brouillon')) {
    return { label: "Brouillons d'e-mail", icon: 'file' }
  }
  if (t.includes('crm_lead') || t.includes('crm') || t.includes('lead')) {
    return { label: 'Données CRM', icon: 'crm' }
  }
  if (t.includes('leave_request') || t.includes('leave') || t.includes('cong')) {
    return { label: 'Demandes de congé', icon: 'leave' }
  }
  if (t.includes('openrouter') || t.includes('modèle') || t.includes('modele')) {
    return { label: 'Modèle IA', icon: 'spark' }
  }
  return { label: rawTitle, icon: 'file' }
}

/** Pick a contextual icon for each suggested action, based on label keywords. */
function actionIconName(label: string): IconName {
  const l = label.toLowerCase()
  if (l.includes('valider') || l.includes('approuv')) return 'check'
  if (l.includes('priorit') || l.includes('chaud') || l.includes('haute')) return 'target'
  if (l.includes('brouillon') || l.includes('e-mail') || l.includes('email')) return 'mail'
  if (l.includes('cong')) return 'calendar'
  if (l.includes('pipeline') || l.includes('crm')) return 'crm'
  if (l.includes('rapport') || l.includes('analyse')) return 'trending-up'
  if (l.includes('traiter') || l.includes('aujourd')) return 'activity'
  return 'chevron-right'
}

// ---------------------------------------------------------------------------
// Assistant analysis card — restructured
// ---------------------------------------------------------------------------

function AssistantAnalysisCard({
  response,
  onAction,
}: {
  response: AssistantChatResponse
  onAction: (action: SuggestedAction) => void
}) {
  const navigate = useNavigate()
  const [openuiFailed, setOpenuiFailed] = useState(false)
  const intent = response.intent as AssistantIntent
  const label = INTENT_LABELS[intent] ?? intent
  const badgeTone = INTENT_BADGE_TONE[intent] ?? INTENT_BADGE_TONE['unknown']
  const insight = INTENT_INSIGHTS[intent] ?? null
  const hasViz = response.visualizations.length > 0
  const hasActions = response.suggested_actions.length > 0
  const hasSources = response.sources.length > 0
  const isOutOfScope = intent === 'out_of_scope' || intent === 'unknown'

  function handleAction(action: SuggestedAction) {
    if (assistantActionRequiresConfirmation(action)) {
      const confirmed = window.confirm(
        `Confirmer l'action "${action.label}" ? Aucune action externe ne sera lancée sans votre accord.`,
      )
      if (!confirmed) return
    }

    if (action.action_type === 'navigate' && typeof action.payload['route'] === 'string') {
      navigate(action.payload['route'])
    } else if (action.action_type === 'open_details' || action.action_type === 'open_modal') {
      const route = typeof action.payload['route'] === 'string' ? action.payload['route'] : null
      const targetId = typeof action.payload['target_id'] === 'string' ? action.payload['target_id'] : null
      if (route) navigate(route)
      else if (targetId) navigate(`/crm-leads/${targetId}`)
    } else if (action.action_type === 'refresh') {
      onAction({ label: 'Rafraîchir', action_type: 'query', payload: { message: 'Rafraîchis cette analyse' } })
    } else if (action.action_type === 'query') {
      onAction(action)
    } else {
      window.alert(
        "Cette action nécessite un endpoint sécurisé spécifique. Elle n'a pas été exécutée automatiquement.",
      )
    }
  }

  const canRenderOpenUI =
    response.display_mode === 'openui' &&
    typeof response.openui_content === 'string' &&
    response.openui_content.trim().length > 0 &&
    !openuiFailed

  return (
    <div className="flex w-full justify-start gap-3">
      {/* Avatar */}
      <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-emerald-500/30 bg-emerald-500/10">
        <Icon name="spark" size={16} className="text-emerald-300" />
      </div>

      {/* Stack — wide */}
      <div className="min-w-0 flex-1 space-y-3">
        {canRenderOpenUI ? (
          <OpenUIRenderer
            content={response.openui_content ?? ''}
            suggestedActions={response.suggested_actions}
            onAction={handleAction}
            onInvalidContent={() => setOpenuiFailed(true)}
          />
        ) : (
          <>
        {/* Main answer card */}
        <div className="overflow-hidden rounded-2xl rounded-tl-sm border border-slate-700/60 bg-slate-900/80 shadow-sm">
          {/* Header — just the intent badge, no FlowPilot AI text */}
          <div className="border-b border-slate-700/40 px-5 py-2.5">
            <span
              className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${badgeTone}`}
            >
              {label}
            </span>
          </div>

          {/* Answer with highlighted numbers */}
          <div className="px-5 py-4">
            <HighlightedAnswer text={response.answer} />

            {/* Inline insight */}
            {insight && !isOutOfScope ? (
              <p className="mt-2 flex items-start gap-1.5 text-xs italic leading-5 text-slate-500">
                <span aria-hidden>💡</span>
                <span>{insight}</span>
              </p>
            ) : null}
          </div>

          {/* Sources — humanized */}
          {hasSources ? (
            <div className="flex flex-wrap items-center gap-2 border-t border-slate-700/30 px-5 py-2.5">
              <span className="text-[10px] uppercase tracking-wider text-slate-600">Source</span>
              {response.sources.map((src, i) => {
                const meta = sourceLabel(src.title)
                return (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1.5 rounded-md border border-slate-700/60 bg-slate-800/40 px-2 py-0.5 text-[11px] text-slate-400"
                  >
                    <Icon name={meta.icon} size={10} className="text-slate-500" />
                    {meta.label}
                  </span>
                )
              })}
            </div>
          ) : null}
        </div>

        {/* Visualizations */}
        {hasViz ? (
          <AssistantChartRenderer visualizations={response.visualizations} />
        ) : null}

        {/* Actions */}
        {hasActions ? (
          <div className="rounded-2xl border border-slate-700/50 bg-slate-900/50 px-5 py-4">
            <p className="mb-2.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Actions recommandées
            </p>
            <div className="flex flex-wrap gap-2">
              {response.suggested_actions.map((action, i) => (
                <button
                  key={i}
                  onClick={() => handleAction(action)}
                  className="group inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800/60 px-3.5 py-2 text-sm font-medium text-slate-200 transition-all duration-200 hover:border-emerald-500/40 hover:bg-emerald-500/10 hover:text-emerald-200"
                >
                  <Icon name={actionIconName(action.label)} size={14} className="text-emerald-300" />
                  <span>{action.label}</span>
                  <span
                    aria-hidden
                    className="ml-1 text-xs text-slate-500 transition-transform group-hover:translate-x-0.5 group-hover:text-emerald-400"
                  >
                    →
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : null}
          </>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Message dispatcher
// ---------------------------------------------------------------------------

function MessageItem({
  message,
  onAction,
}: {
  message: ChatMessage
  onAction: (action: SuggestedAction) => void
}) {
  if (message.role === 'user') return <UserBubble text={message.text} />
  if (message.isLoading) return <LoadingBubble phase={message.loadingPhase ?? 0} />
  if (message.error) return <ErrorBubble message={message.error} />
  if (message.response) return <AssistantAnalysisCard response={message.response} onAction={onAction} />
  return null
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

let messageCounter = 0
function nextId() {
  return `msg-${++messageCounter}`
}

function AssistantPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [isSending, setIsSending] = useState(false)
  const [loadingPhase, setLoadingPhase] = useState(0)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const loadingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (isSending) {
      loadingTimerRef.current = setInterval(() => {
        setLoadingPhase((p) => p + 1)
      }, 1800)
    } else {
      if (loadingTimerRef.current) clearInterval(loadingTimerRef.current)
    }
    return () => {
      if (loadingTimerRef.current) clearInterval(loadingTimerRef.current)
    }
  }, [isSending])

  async function sendMessage(text: string) {
    const trimmed = text.trim()
    if (!trimmed || isSending) return

    setInput('')
    setLoadingPhase(0)
    setIsSending(true)

    const userMsgId = nextId()
    const loadingMsgId = nextId()

    // Snapshot of the last few turns BEFORE we mutate state — used by the
    // LLM fallback to ground itself on the current conversation.
    const history: AssistantHistoryMessage[] = messages
      .filter((m) => !m.isLoading && !m.error)
      .map((m) => ({
        role: m.role,
        content: m.role === 'assistant' ? m.response?.answer ?? m.text : m.text,
      }))
      .filter((m) => m.content.trim().length > 0)
      .slice(-6)

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: 'user', text: trimmed },
      { id: loadingMsgId, role: 'assistant', text: '', isLoading: true, loadingPhase: 0 },
    ])

    try {
      const response = await sendAssistantMessage({
        message: trimmed,
        conversation_id: conversationId ?? undefined,
        conversation_history: history,
      })

      if (response.conversation_id) setConversationId(response.conversation_id)

      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsgId
            ? { ...m, isLoading: false, text: response.answer, response }
            : m,
        ),
      )
    } catch (err) {
      const errorText =
        err instanceof Error
          ? err.message
          : "L'assistant est temporairement indisponible. Veuillez réessayer."

      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsgId
            ? { ...m, isLoading: false, text: '', error: errorText }
            : m,
        ),
      )
    } finally {
      setIsSending(false)
      inputRef.current?.focus()
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    void sendMessage(input)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void sendMessage(input)
    }
  }

  function handleSuggestedQuery(action: SuggestedAction) {
    if (typeof action.payload['message'] === 'string') {
      void sendMessage(action.payload['message'])
    }
  }

  function startNewConversation() {
    setMessages([])
    setConversationId(null)
    setInput('')
    inputRef.current?.focus()
  }

  const isEmpty = messages.length === 0

  return (
    <div className="flex h-full flex-col bg-slate-950/30">
      {/* Slim top bar: title + status + suggestion chips + new-chat */}
      <div className="shrink-0 border-b border-slate-800 bg-slate-950/70 px-4 py-2.5 backdrop-blur-md sm:px-6">
        <div className="flex items-center gap-3">
          <div className="flex shrink-0 items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-linear-to-br from-emerald-500 to-indigo-500 shadow-sm shadow-emerald-500/20">
              <Icon name="spark" size={15} className="text-white" />
            </div>
            <span className="text-sm font-bold text-white">Assistant IA</span>
            <span className="hidden items-center gap-1.5 rounded-[20px] border border-[rgba(16,185,129,0.25)] bg-[rgba(16,185,129,0.1)] px-2 py-0.5 text-[10px] font-medium text-[#10b981] sm:inline-flex">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
              En ligne
            </span>
          </div>

          <div
            className="flex min-w-0 flex-1 gap-2 overflow-x-auto [&::-webkit-scrollbar]:hidden"
            style={{ scrollbarWidth: 'none' }}
          >
            {QUICK_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => void sendMessage(prompt)}
                disabled={isSending}
                className="shrink-0 rounded-[20px] border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.05)] px-3 py-1 text-[11px] font-medium text-[#8b949e] transition-all duration-200 hover:border-[rgba(16,185,129,0.3)] hover:bg-[rgba(16,185,129,0.1)] hover:text-[#10b981] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {prompt}
              </button>
            ))}
          </div>

          {!isEmpty ? (
            <button
              type="button"
              onClick={startNewConversation}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900/70 px-2.5 py-1.5 text-[11px] font-semibold text-slate-300 transition hover:border-emerald-500/40 hover:text-emerald-200"
            >
              <Icon name="plus" size={12} />
              <span className="hidden sm:inline">Nouvelle analyse</span>
            </button>
          ) : null}
        </div>
      </div>

      {/* Messages — full-width scroll area, content centered */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {isEmpty ? (
          <div className="h-full px-4 py-6 sm:px-6">
            <WelcomeScreen onPrompt={(p) => void sendMessage(p)} />
          </div>
        ) : (
          <div className="space-y-6 py-6">
            {messages.map((msg) => {
              // User questions and dashboard answers use the full content width so the
              // right-aligned question bubble lines up with the dashboard below it.
              // Plain text answers stay in a readable centered column.
              const fullWidth =
                msg.role === 'user' || (msg.role === 'assistant' && msg.response?.display_mode === 'openui')
              return (
                <div key={msg.id} className={fullWidth ? 'w-full px-4 sm:px-6' : 'mx-auto w-full max-w-4xl px-4 sm:px-6'}>
                  <MessageItem message={{ ...msg, loadingPhase }} onAction={handleSuggestedQuery} />
                </div>
              )
            })}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input bar — full-width surface, input centered */}
      <div className="shrink-0 border-t border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] px-4 py-3 sm:px-6">
        <form onSubmit={handleSubmit} className="w-full">
          <div className="flex min-h-[56px] items-end gap-3 rounded-2xl border border-[rgba(255,255,255,0.12)] bg-[rgba(255,255,255,0.04)] px-5 py-4 transition focus-within:border-[rgba(16,185,129,0.5)] focus-within:shadow-[0_0_0_3px_rgba(16,185,129,0.08)]">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Demandez une métrique, une liste, une comparaison ou un dashboard CRM..."
              rows={1}
              disabled={isSending}
              className="flex-1 resize-none self-center bg-transparent text-[15px] text-[#e6edf3] outline-none placeholder:text-[#484f58] disabled:opacity-50"
              style={{ maxHeight: '160px' }}
            />
            <button
              type="submit"
              disabled={!input.trim() || isSending}
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-linear-to-br from-emerald-500 to-emerald-600 text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Envoyer"
            >
              {isSending ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              ) : (
                <Icon name="send" size={17} />
              )}
            </button>
          </div>
          <p className="mt-2 text-center text-[11px] text-[#484f58]">
            Entrée pour envoyer · Maj+Entrée pour saut de ligne
          </p>
        </form>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Welcome screen
// ---------------------------------------------------------------------------

const WELCOME_SUGGESTIONS: { icon: IconName; label: string; query: string; detail: string; tint: string }[] = [
  { icon: 'target', label: 'Hot leads', query: 'Combien de hot leads avons-nous ?', detail: 'Réponse courte avec KPI', tint: 'bg-emerald-500/15 text-emerald-300' },
  { icon: 'crm', label: 'Résumé CRM', query: 'Donne-moi un résumé CRM de cette semaine.', detail: 'Dashboard commercial', tint: 'bg-sky-500/15 text-sky-300' },
  { icon: 'workflow', label: 'Automatisations', query: "Quelle est la santé des automatisations ?", detail: 'Alertes opérationnelles', tint: 'bg-violet-500/15 text-violet-300' },
  { icon: 'file', label: "Brouillons d'e-mail", query: 'Quels brouillons attendent une validation ?', detail: 'Liste et actions sécurisées', tint: 'bg-amber-500/15 text-amber-300' },
]

function WelcomeScreen({ onPrompt }: { onPrompt: (p: string) => void }) {
  return (
    <div className="mx-auto flex h-full min-h-[440px] w-full max-w-2xl flex-col items-center justify-center px-4 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-linear-to-br from-emerald-500 to-indigo-500 shadow-lg shadow-emerald-500/20">
        <Icon name="spark" size={26} className="text-white" />
      </div>
      <h2 className="mt-5 text-[22px] font-semibold text-[#f0f6fc]">FlowPilot AI</h2>
      <p className="mt-2 max-w-md text-sm text-[#7d8590]">
        Analysez vos données CRM, congés et automatisations en temps réel.
      </p>

      <div className="mt-8 grid w-full max-w-[480px] grid-cols-2 gap-3">
        {WELCOME_SUGGESTIONS.map((s) => (
          <button
            key={s.label}
            onClick={() => onPrompt(s.query)}
            className="group flex items-start gap-3 rounded-xl border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.04)] p-3.5 text-left transition-all duration-200 hover:border-[rgba(16,185,129,0.3)] hover:bg-[rgba(16,185,129,0.06)]"
          >
            <span className={`flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-lg ${s.tint}`}>
              <Icon name={s.icon} size={15} />
            </span>
            <span className="min-w-0">
              <span className="block text-[13px] font-medium text-white">{s.label}</span>
              <span className="mt-0.5 block text-[11px] text-[#7d8590]">{s.detail}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}

export default AssistantPage
