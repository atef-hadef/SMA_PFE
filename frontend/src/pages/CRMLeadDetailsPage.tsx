import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  ActionButton,
  AppCard,
  EmptyState,
  ErrorState,
  Icon,
  KpiCard,
  LoadingState,
  PageHeader,
  PriorityBadge,
  StatusBadge,
} from '../components/common'
import type { ActionButtonVariant } from '../components/common/ActionButton'
import type { AppCardTone } from '../components/common/AppCard'
import type { IconName } from '../components/common/Icon'
import type { StatusType } from '../components/common/StatusBadge'
import { useAuth } from '../auth/useAuth'
import {
  approveEmailDraft,
  convertLeadToCustomer,
  generateCommunicationDraft,
  getCrmLeadById,
  getLeadDrafts,
  rejectEmailDraft,
  reviewEmailDraft,
  sendApprovedEmailDraft,
  updateEmailDraft,
} from '../services/crmService'
import {
  createCrmDeal,
  createCrmTask,
  listCrmDeals,
  listCrmTasks,
} from '../services/crmTasksDealsService'
import type {
  CrmDealItem,
  CrmDealStage,
  CrmTaskItem,
  CrmTaskPriority,
} from '../services/crmTasksDealsService'
import type {
  CrmEmailDraftItem,
  CrmInteractionHistoryItem,
  CrmLeadDetail,
} from '../services/crmService'
import {
  formatCrmCurrency,
  formatCrmDate,
  getCrmBusinessStateLabel,
  getCrmDraftStatusLabel,
} from '../utils/crmDisplay'

const DEFAULT_LEAD_ID = 'lead_001'
const STAGE_LABELS: Record<CrmDealStage, string> = {
  discovery: 'Découverte',
  proposal: 'Proposition',
  negotiation: 'Négociation',
  closing: 'Closing',
  won: 'Gagné',
  lost: 'Perdu',
}
const STAGE_TONES: Record<CrmDealStage, StatusType> = {
  discovery: 'info',
  proposal: 'warning',
  negotiation: 'warning',
  closing: 'warning',
  won: 'success',
  lost: 'danger',
}

function getLeadIdFromSearch(search: string) {
  return new URLSearchParams(search).get('leadId') || DEFAULT_LEAD_ID
}

function getStatusTone(status?: string | null): StatusType {
  const value = (status || '').toLowerCase()
  if (value.includes('customer') || value.includes('vip')) return 'success'
  if (value.includes('prospect')) return 'warning'
  return 'info'
}

function getScoreTone(score?: number | null): StatusType {
  if (score === null || score === undefined) return 'neutral'
  if (score >= 70) return 'success'
  if (score >= 41) return 'warning'
  return 'danger'
}

function getDraftStatusTone(status?: string | null): StatusType {
  const value = (status || '').toLowerCase()
  if (value === 'approved' || value === 'sent') return 'success'
  if (value === 'sending') return 'info'
  if (value === 'rejected' || value === 'failed') return 'danger'
  if (value === 'reviewed' || value === 'edited' || value === 'draft_generated') return 'warning'
  return 'neutral'
}

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback
}

// Met une majuscule au début de chaque mot (ex. "atef ben hadef" -> "Atef Ben Hadef").
function toTitleCase(value?: string | null): string {
  if (!value) return ''
  return value.toLowerCase().replace(/(^|[\s'-])(\p{L})/gu, (_, sep, char) => sep + char.toUpperCase())
}

// Convertit le HTML d'un brouillon en texte simple lisible pour l'édition.
function stripHtml(html: string): string {
  return html
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#039;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .trim()
}

// Reconvertit le texte simple édité en HTML : un <p> par paragraphe, <br> par saut de ligne.
function textToHtml(text: string): string {
  const escape = (value: string) =>
    value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return text
    .trim()
    .split(/\n{2,}/)
    .map((para) => `<p>${escape(para.trim()).replace(/\n/g, '<br>')}</p>`)
    .filter((para) => para !== '<p></p>')
    .join('\n')
}

// Traduction des libellés d'interaction calculés par le backend (business_label).
// On s'appuie uniquement sur ce champ structuré : le texte `summary` brut contient
// des champs techniques (Status:, Subject:, Body:…) qui ne doivent jamais être affichés.
const INTERACTION_LABEL_FR: Record<string, string> = {
  'Communication draft generated': 'Brouillon email généré',
  'Welcome draft generated': 'Brouillon de bienvenue généré',
  'Draft approved': 'Brouillon email approuvé',
  'Draft reviewed': 'Brouillon email relu',
  'Draft rejected': 'Brouillon email rejeté',
  'Draft edited': 'Brouillon email modifié',
  'Draft updated': 'Brouillon email mis à jour',
  'Communication reviewed': 'Communication relue',
  'Email sent': 'Email envoyé',
  'Email sending failed': "Échec de l'envoi de l'email",
  'Customer converted': 'Client converti',
  'Lead collected': 'Lead collecté',
  'AI analysis completed': 'Analyse IA terminée',
  'Lead scored': 'Lead qualifié',
  'Routing decision made': 'Lead assigné',
  'Email reply': 'Réponse email du prospect',
  'Phone call': 'Appel téléphonique',
  Meeting: 'Rendez-vous',
  WhatsApp: 'Message WhatsApp',
  'Manual note': 'Note manuelle ajoutée',
}

function getLastInteractionSummary(
  interactions: CrmInteractionHistoryItem[] | undefined,
): { label: string; date: string } | null {
  if (!interactions || interactions.length === 0) return null
  const sorted = [...interactions].sort(
    (a, b) => new Date(b.interaction_date).getTime() - new Date(a.interaction_date).getTime(),
  )
  const last = sorted[0]
  // Libellé propre dérivé du champ structuré business_label, jamais du summary brut.
  const label = (last.business_label && INTERACTION_LABEL_FR[last.business_label]) || 'Activité CRM'
  return {
    label,
    date: formatCrmDate(last.interaction_date),
  }
}

function isPendingValidationDraft(draft: CrmEmailDraftItem) {
  return ['draft_generated', 'edited', 'reviewed'].includes(draft.status)
}

function getActiveDraft(
  lead: CrmLeadDetail,
  drafts: CrmEmailDraftItem[],
): CrmEmailDraftItem | null {
  const targetId = lead.crm_display_state?.latest_draft_id
  if (targetId) {
    const match = drafts.find((draft) => draft.id === targetId)
    if (match) return match
  }
  const pending = drafts.find(isPendingValidationDraft)
  if (pending) return pending
  return drafts[0] || null
}

function getLatestSentDraft(drafts: CrmEmailDraftItem[]): CrmEmailDraftItem | null {
  const sent = drafts
    .filter((draft) => draft.status === 'sent' || draft.status === 'sending')
    .sort((a, b) => {
      const aDate = new Date(a.sent_at || a.updated_at).getTime()
      const bDate = new Date(b.sent_at || b.updated_at).getTime()
      return bDate - aDate
    })
  return sent[0] || null
}

type StatePlanAction = {
  label: string
  iconName: IconName
  variant: ActionButtonVariant
  onClick: () => void
  disabled?: boolean
  pendingKey?: string
}

type StatePlanContextItem = { label: string; value: string }

type StatePlan = {
  title: string
  description: string
  tone: AppCardTone
  workflowBadge?: { label: string; status: StatusType }
  contextItems?: StatePlanContextItem[]
  primary?: StatePlanAction
  secondary?: StatePlanAction
  tertiary?: StatePlanAction
}

type StatePlanContext = {
  can: (perm: string) => boolean
  pendingAction: string | null
  activeDraft: CrmEmailDraftItem | null
  latestSentDraft: CrmEmailDraftItem | null
  lastInteractionLabel: string | null
  onGenerateDraft: () => void
  onViewDraft: (draftId: string) => void
  onEditDraft: (draft: CrmEmailDraftItem) => void
  onReviewDraft: (draftId: string) => void
  onApproveDraft: (draftId: string) => void
  onRejectDraft: (draftId: string) => void
  onSendDraft: (draftId: string) => void
  onConfirmCustomer: () => void
  onCreateTask: () => void
  onCreateDeal: () => void
  onRefresh: () => void
}

function getEffectiveState(lead: CrmLeadDetail): string {
  const display = lead.crm_display_state
  if (!display) {
    const customerStatus = (lead.customer_status || lead.status || '').toLowerCase()
    if (customerStatus.includes('customer') || customerStatus.includes('vip')) return 'customer_converted'
    if (customerStatus.includes('prospect')) return 'prospect_qualified'
    return 'lead_collected'
  }
  if (display.conversion_pending) return 'conversion_pending'
  return display.current_state
}

function getWorkflowBadgeForState(state: string): StatePlan['workflowBadge'] {
  switch (state) {
    case 'lead_collected':
      return { label: 'WF 01 · Analyse IA en cours', status: 'info' }
    case 'lead_analyzed':
    case 'prospect_qualified':
      return { label: 'WF 01 · Lead Intake terminé', status: 'success' }
    case 'draft_missing':
      return { label: 'Action déclenche WF 02 — Communication Draft', status: 'info' }
    case 'draft_generated':
    case 'edited':
      return { label: 'WF 02 · Brouillon généré', status: 'success' }
    case 'draft_reviewed':
      return { label: "Approbation prépare WF 04 — Approved Email Send", status: 'info' }
    case 'draft_approved':
      return { label: 'Envoi déclenche WF 04 — Approved Email Send Gmail', status: 'info' }
    case 'email_sending':
      return { label: 'WF 04 · Envoi en cours', status: 'info' }
    case 'email_sent_waiting_response':
      return { label: 'WF 04 · Email envoyé avec succès', status: 'success' }
    case 'positive_response_recorded':
    case 'conversion_ready':
      return { label: 'Confirmation déclenche WF 03 — Human Conversion + Welcome', status: 'info' }
    case 'conversion_pending':
    case 'customer_converted':
      return { label: 'WF 03 · Human Conversion en cours', status: 'info' }
    case 'welcome_draft_generated':
      return { label: 'WF 03 · Brouillon de bienvenue généré', status: 'success' }
    case 'welcome_draft_approved':
      return { label: 'Envoi déclenche WF 04 (bienvenue)', status: 'info' }
    case 'welcome_email_sent':
      return { label: 'WF 03 · Onboarding démarré', status: 'success' }
    case 'failed':
      return { label: 'WF 04 · Échec — relance possible', status: 'danger' }
    default:
      return undefined
  }
}

function buildStatePlan(
  lead: CrmLeadDetail,
  _drafts: CrmEmailDraftItem[],
  ctx: StatePlanContext,
): StatePlan {
  const state = getEffectiveState(lead)
  const display = lead.crm_display_state
  const workflowBadge = getWorkflowBadgeForState(state)
  const activeDraft = ctx.activeDraft
  const latestSentDraft = ctx.latestSentDraft

  const draftContext: StatePlanContextItem[] = activeDraft
    ? [
        { label: 'Objet du brouillon', value: activeDraft.subject || 'Sans objet' },
        {
          label: 'Type',
          value:
            activeDraft.draft_type === 'welcome' ? 'Email de bienvenue' : 'Email commercial',
        },
        { label: 'Mis à jour le', value: formatCrmDate(activeDraft.updated_at) },
      ]
    : []

  const sentContext: StatePlanContextItem[] = latestSentDraft
    ? [
        { label: 'Objet', value: latestSentDraft.subject || 'Sans objet' },
        {
          label: 'Envoyé le',
          value: latestSentDraft.sent_at ? formatCrmDate(latestSentDraft.sent_at) : '—',
        },
      ]
    : []

  const generateDraftAction = (label: string, variant: ActionButtonVariant = 'primary'): StatePlanAction => ({
    label,
    iconName: 'mail',
    variant,
    onClick: ctx.onGenerateDraft,
    disabled: !ctx.can('crm.drafts.generate') || ctx.pendingAction === 'generate_draft',
    pendingKey: 'generate_draft',
  })

  const createTaskAction = (label: string, variant: ActionButtonVariant = 'secondary'): StatePlanAction => ({
    label,
    iconName: 'check',
    variant,
    onClick: ctx.onCreateTask,
    disabled: !ctx.can('crm.tasks.manage'),
  })

  const createDealAction = (label: string, variant: ActionButtonVariant = 'secondary'): StatePlanAction => ({
    label,
    iconName: 'target',
    variant,
    onClick: ctx.onCreateDeal,
    disabled: !ctx.can('crm.deals.manage'),
  })

  const refreshAction = (label: string): StatePlanAction => ({
    label,
    iconName: 'reload',
    variant: 'secondary',
    onClick: ctx.onRefresh,
  })

  switch (state) {
    case 'lead_collected':
    case 'lead_analyzed':
      return {
        title: 'Lead à qualifier',
        description:
          display?.business_summary_text ||
          "Le lead vient d'arriver. L'IA a analysé le contexte. Préparez la première communication commerciale.",
        tone: 'info',
        workflowBadge,
        contextItems: [
          { label: 'Score IA', value: `${lead.score}/100` },
          { label: 'Sentiment', value: lead.sentiment || '—' },
          { label: 'Urgence', value: lead.urgency || '—' },
        ],
        primary: generateDraftAction('Générer email commercial'),
        secondary: createTaskAction('Créer tâche de qualification'),
      }

    case 'prospect_qualified':
    case 'draft_missing':
      return {
        title: 'Préparer le premier email',
        description:
          display?.business_summary_text ||
          'Le prospect est qualifié. Générez le brouillon de communication initiale via le workflow IA.',
        tone: 'info',
        workflowBadge,
        contextItems: [
          { label: 'Score IA', value: `${lead.score}/100` },
          { label: 'Sentiment', value: lead.sentiment || '—' },
        ],
        primary: generateDraftAction('Générer email commercial'),
        secondary: createTaskAction('Créer tâche'),
      }

    case 'draft_generated':
    case 'edited':
      return {
        title: 'Brouillon à relire',
        description:
          "L'IA a généré un brouillon de communication (WF 02). Vérifiez le contenu avant approbation.",
        tone: 'warning',
        workflowBadge,
        contextItems: draftContext,
        primary: activeDraft
          ? {
              label: 'Voir le brouillon',
              iconName: 'eye',
              variant: 'primary',
              onClick: () => ctx.onViewDraft(activeDraft.id),
            }
          : generateDraftAction('Générer un nouveau brouillon'),
        secondary:
          activeDraft && ctx.can('crm.drafts.review')
            ? {
                label: 'Marquer comme relu',
                iconName: 'check',
                variant: 'secondary',
                onClick: () => ctx.onReviewDraft(activeDraft.id),
                disabled: ctx.pendingAction === `review_${activeDraft.id}`,
              }
            : undefined,
        tertiary:
          activeDraft && ctx.can('crm.drafts.review')
            ? {
                label: 'Modifier',
                iconName: 'file',
                variant: 'ghost',
                onClick: () => ctx.onEditDraft(activeDraft),
              }
            : undefined,
      }

    case 'draft_reviewed':
      return {
        title: 'Approuver ou rejeter le brouillon',
        description:
          "Le brouillon a été relu. Décidez maintenant : l'approbation prépare l'envoi automatisé via WF 04.",
        tone: 'warning',
        workflowBadge,
        contextItems: draftContext,
        primary:
          activeDraft && ctx.can('crm.email.approve')
            ? {
                label: 'Approuver',
                iconName: 'check',
                variant: 'primary',
                onClick: () => ctx.onApproveDraft(activeDraft.id),
                disabled: ctx.pendingAction === `approve_${activeDraft.id}`,
              }
            : undefined,
        secondary:
          activeDraft && ctx.can('crm.drafts.review')
            ? {
                label: 'Rejeter',
                iconName: 'close',
                variant: 'danger',
                onClick: () => ctx.onRejectDraft(activeDraft.id),
                disabled: ctx.pendingAction === `reject_${activeDraft.id}`,
              }
            : undefined,
        tertiary:
          activeDraft && ctx.can('crm.drafts.review')
            ? {
                label: 'Modifier',
                iconName: 'file',
                variant: 'ghost',
                onClick: () => ctx.onEditDraft(activeDraft),
              }
            : undefined,
      }

    case 'draft_approved':
      return {
        title: 'Email prêt à être envoyé',
        description:
          "Le brouillon est approuvé. L'envoi déclenche WF 04 (Approved Email Send Gmail).",
        tone: 'success',
        workflowBadge,
        contextItems: draftContext,
        primary:
          activeDraft && ctx.can('crm.email.send')
            ? {
                label: "Envoyer maintenant",
                iconName: 'send',
                variant: 'urgent',
                onClick: () => ctx.onSendDraft(activeDraft.id),
                disabled: ctx.pendingAction === `send_${activeDraft.id}`,
              }
            : undefined,
        secondary: activeDraft
          ? {
              label: 'Voir le brouillon',
              iconName: 'eye',
              variant: 'ghost',
              onClick: () => ctx.onViewDraft(activeDraft.id),
            }
          : undefined,
      }

    case 'email_sending':
      return {
        title: 'Envoi en cours',
        description:
          "Le workflow WF 04 est en cours d'exécution. La page se mettra à jour à la réception du callback.",
        tone: 'info',
        workflowBadge,
        contextItems: draftContext,
        primary: refreshAction('Actualiser'),
      }

    case 'email_sent_waiting_response':
      return {
        title: 'Email envoyé · attente de réponse',
        description:
          "L'email a bien été envoyé. Attendez la réponse du prospect, ou créez une tâche de relance.",
        tone: 'info',
        workflowBadge,
        contextItems: sentContext,
        primary: createTaskAction('Créer tâche de relance', 'primary'),
        secondary: generateDraftAction('Générer un email de relance', 'secondary'),
      }

    case 'positive_response_recorded':
    case 'conversion_ready':
      return {
        title: 'Confirmer la conversion en client',
        description:
          "Le prospect a confirmé son intérêt. La confirmation humaine déclenche WF 03 (Human Conversion + email de bienvenue).",
        tone: 'success',
        workflowBadge,
        contextItems: [
          ...(ctx.lastInteractionLabel
            ? [{ label: 'Dernier signal', value: ctx.lastInteractionLabel }]
            : []),
          { label: 'Score IA', value: `${lead.score}/100` },
        ],
        primary: ctx.can('crm.customer.convert')
          ? {
              label: 'Confirmer comme client',
              iconName: 'star',
              variant: 'urgent',
              onClick: ctx.onConfirmCustomer,
              disabled: ctx.pendingAction === 'confirm_customer',
            }
          : undefined,
        secondary: createDealAction('Créer un deal'),
        tertiary: createTaskAction('Créer une tâche', 'ghost'),
      }

    case 'conversion_pending':
      return {
        title: 'Conversion client en cours',
        description:
          "WF 03 a été déclenché. Le brouillon de bienvenue arrivera automatiquement à la fin du workflow. Aucune action manuelle n'est requise pour le moment.",
        tone: 'info',
        workflowBadge,
        contextItems: [
          { label: 'Statut backend', value: 'conversion_pending' },
          ...(ctx.lastInteractionLabel
            ? [{ label: 'Dernier événement', value: ctx.lastInteractionLabel }]
            : []),
        ],
        primary: refreshAction('Actualiser'),
      }

    case 'customer_converted':
      return {
        title: "Préparer l'email de bienvenue",
        description:
          "Le client est converti. Générez ou attendez le brouillon de bienvenue automatique (WF 03).",
        tone: 'success',
        workflowBadge,
        primary: ctx.can('crm.drafts.generate')
          ? generateDraftAction("Générer email de bienvenue")
          : refreshAction('Actualiser'),
        secondary: createDealAction('Créer un deal'),
      }

    case 'welcome_draft_generated':
      return {
        title: 'Brouillon de bienvenue à relire',
        description:
          "WF 03 a généré l'email de bienvenue. Relisez-le avant approbation et envoi.",
        tone: 'warning',
        workflowBadge,
        contextItems: draftContext,
        primary: activeDraft
          ? {
              label: 'Voir le brouillon',
              iconName: 'eye',
              variant: 'primary',
              onClick: () => ctx.onViewDraft(activeDraft.id),
            }
          : undefined,
        secondary:
          activeDraft && ctx.can('crm.drafts.review')
            ? {
                label: 'Marquer comme relu',
                iconName: 'check',
                variant: 'secondary',
                onClick: () => ctx.onReviewDraft(activeDraft.id),
                disabled: ctx.pendingAction === `review_${activeDraft.id}`,
              }
            : undefined,
        tertiary:
          activeDraft && ctx.can('crm.drafts.review')
            ? {
                label: 'Modifier',
                iconName: 'file',
                variant: 'ghost',
                onClick: () => ctx.onEditDraft(activeDraft),
              }
            : undefined,
      }

    case 'welcome_draft_approved':
      return {
        title: 'Email de bienvenue prêt à envoyer',
        description:
          "Le brouillon de bienvenue est approuvé. L'envoi déclenche WF 04 (Approved Email Send).",
        tone: 'success',
        workflowBadge,
        contextItems: draftContext,
        primary:
          activeDraft && ctx.can('crm.email.send')
            ? {
                label: "Envoyer l'email de bienvenue",
                iconName: 'send',
                variant: 'urgent',
                onClick: () => ctx.onSendDraft(activeDraft.id),
                disabled: ctx.pendingAction === `send_${activeDraft.id}`,
              }
            : undefined,
        secondary: activeDraft
          ? {
              label: 'Voir le brouillon',
              iconName: 'eye',
              variant: 'ghost',
              onClick: () => ctx.onViewDraft(activeDraft.id),
            }
          : undefined,
      }

    case 'welcome_email_sent':
      return {
        title: 'Onboarding client',
        description:
          "L'email de bienvenue a été envoyé. Préparez la phase d'onboarding (tâches, deals, suivi).",
        tone: 'success',
        workflowBadge,
        contextItems: sentContext,
        primary: createTaskAction("Créer tâche d'onboarding", 'primary'),
        secondary: createDealAction('Créer un deal'),
      }

    case 'negative_response_recorded':
      return {
        title: 'Réponse négative enregistrée',
        description:
          "Le prospect n'est pas intéressé pour le moment. Planifiez une relance ou clôturez l'opportunité.",
        tone: 'warning',
        contextItems: ctx.lastInteractionLabel
          ? [{ label: 'Dernier signal', value: ctx.lastInteractionLabel }]
          : undefined,
        primary: createTaskAction('Créer tâche de relance', 'primary'),
        secondary: generateDraftAction('Générer email de réactivation', 'secondary'),
      }

    case 'neutral_response_recorded':
    case 'follow_up_required':
      return {
        title: 'Action de suivi nécessaire',
        description:
          "La réponse nécessite une clarification ou une relance commerciale.",
        tone: 'warning',
        contextItems: ctx.lastInteractionLabel
          ? [{ label: 'Dernier signal', value: ctx.lastInteractionLabel }]
          : undefined,
        primary: createTaskAction('Créer tâche de relance', 'primary'),
        secondary: generateDraftAction("Générer email d'information", 'secondary'),
      }

    case 'failed':
      return {
        title: "Envoi en échec",
        description:
          "Le workflow WF 04 a échoué. Vérifiez les logs et relancez l'envoi.",
        tone: 'danger',
        workflowBadge,
        contextItems: draftContext,
        primary:
          activeDraft && ctx.can('crm.email.send')
            ? {
                label: "Réessayer l'envoi",
                iconName: 'reload',
                variant: 'urgent',
                onClick: () => ctx.onSendDraft(activeDraft.id),
                disabled: ctx.pendingAction === `send_${activeDraft.id}`,
              }
            : undefined,
        secondary: activeDraft
          ? {
              label: 'Voir le brouillon',
              iconName: 'eye',
              variant: 'ghost',
              onClick: () => ctx.onViewDraft(activeDraft.id),
            }
          : undefined,
      }

    default:
      return {
        title: 'Aucune action urgente',
        description: display?.business_summary_text || 'Aucune action prioritaire détectée pour ce lead.',
        tone: 'muted',
        workflowBadge,
        primary: createTaskAction('Créer une tâche'),
        secondary: createDealAction('Créer un deal'),
      }
  }
}

type DraftEditState = {
  draftId: string
  subject: string
  body: string
}

type CreateTaskState = {
  title: string
  due_date: string
  priority: CrmTaskPriority
}

type CreateDealState = {
  title: string
  amount: string
  probability_percent: number
}

type ConfirmCustomerState = {
  validation_reason: string
  evidence_source: string
  next_action: string
  conversion_note: string
}

function CRMLeadDetailsPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuth()
  const leadId = useMemo(() => getLeadIdFromSearch(location.search), [location.search])

  const [lead, setLead] = useState<CrmLeadDetail | null>(null)
  const [drafts, setDrafts] = useState<CrmEmailDraftItem[]>([])
  const [tasks, setTasks] = useState<CrmTaskItem[]>([])
  const [deals, setDeals] = useState<CrmDealItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionInfo, setActionInfo] = useState<string | null>(null)
  const [pendingAction, setPendingAction] = useState<string | null>(null)

  const [editing, setEditing] = useState<DraftEditState | null>(null)
  const [expandedDraftId, setExpandedDraftId] = useState<string | null>(null)
  const [viewingDraftId, setViewingDraftId] = useState<string | null>(null)
  const [taskForm, setTaskForm] = useState<CreateTaskState | null>(null)
  const [dealForm, setDealForm] = useState<CreateDealState | null>(null)
  const [confirmCustomer, setConfirmCustomer] = useState<ConfirmCustomerState | null>(null)

  const permissions = useMemo(() => user?.permissions ?? [], [user])
  const can = useCallback((perm: string) => permissions.includes(perm), [permissions])

  const refresh = useCallback(async () => {
    setIsLoading(true)
    setLoadError(null)
    try {
      const [leadData, draftsData, tasksData, dealsData] = await Promise.all([
        getCrmLeadById(leadId),
        getLeadDrafts(leadId).catch(() => [] as CrmEmailDraftItem[]),
        listCrmTasks({ leadId }).catch(() => ({ count: 0, items: [] as CrmTaskItem[] })),
        listCrmDeals({ leadId }).catch(() => ({ count: 0, items: [] as CrmDealItem[] })),
      ])
      setLead(leadData)
      setDrafts(draftsData)
      setTasks(tasksData.items)
      setDeals(dealsData.items)
    } catch (error) {
      setLoadError(getErrorMessage(error, 'Impossible de charger le lead.'))
    } finally {
      setIsLoading(false)
    }
  }, [leadId])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const openTaskForm = useCallback(() => {
    const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 16)
    setTaskForm({ title: '', due_date: tomorrow, priority: 'medium' })
  }, [])
  const openDealForm = useCallback(() => {
    setDealForm({ title: '', amount: '', probability_percent: 20 })
  }, [])
  const openConfirmCustomerForm = useCallback(() => {
    setConfirmCustomer({
      validation_reason: 'Le prospect a confirmé son intérêt',
      evidence_source: 'Réponse email',
      next_action: 'Préparer la communication de bienvenue',
      conversion_note: '',
    })
  }, [])
  const handleViewDraft = useCallback((draftId: string) => setViewingDraftId(draftId), [])

  const sortedDrafts = useMemo(
    () =>
      [...drafts].sort(
        (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
      ),
    [drafts],
  )
  const pendingDrafts = useMemo(
    () => sortedDrafts.filter(isPendingValidationDraft),
    [sortedDrafts],
  )
  const otherDrafts = useMemo(
    () => sortedDrafts.filter((draft) => !isPendingValidationDraft(draft)),
    [sortedDrafts],
  )
  const sortedTasks = useMemo(
    () =>
      [...tasks]
        .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
        .slice(0, 3),
    [tasks],
  )
  const lastInteraction = useMemo(
    () => (lead ? getLastInteractionSummary(lead.interaction_history) : null),
    [lead],
  )

  const handleAsync = useCallback(
    async (key: string, action: () => Promise<unknown>, successMessage: string) => {
      setPendingAction(key)
      setActionError(null)
      setActionInfo(null)
      try {
        await action()
        setActionInfo(successMessage)
        await refresh()
      } catch (error) {
        setActionError(getErrorMessage(error, 'Action impossible.'))
      } finally {
        setPendingAction(null)
      }
    },
    [refresh],
  )

  const handleGenerateDraft = () =>
    handleAsync(
      'generate_draft',
      () => generateCommunicationDraft(leadId),
      'Brouillon de communication demandé.',
    )

  const handleReview = (draftId: string) =>
    handleAsync(`review_${draftId}`, () => reviewEmailDraft(draftId), 'Brouillon marqué comme relu.')

  const handleApprove = (draftId: string) =>
    handleAsync(`approve_${draftId}`, () => approveEmailDraft(draftId), 'Brouillon approuvé.')

  const handleReject = (draftId: string) => {
    const reason = window.prompt('Raison du rejet ?', '')
    if (!reason) return
    return handleAsync(
      `reject_${draftId}`,
      () => rejectEmailDraft(draftId, reason),
      'Brouillon rejeté.',
    )
  }

  const handleSend = (draftId: string) =>
    handleAsync(
      `send_${draftId}`,
      () => sendApprovedEmailDraft(draftId),
      'Envoi du brouillon déclenché.',
    )

  const handleSaveEdit = () => {
    if (!editing) return
    const payload = { subject: editing.subject, body: textToHtml(editing.body) }
    void handleAsync(
      `update_${editing.draftId}`,
      async () => {
        await updateEmailDraft(editing.draftId, payload)
        setEditing(null)
      },
      'Brouillon mis à jour.',
    )
  }

  const handleCreateTask = () => {
    if (!taskForm || !user) return
    void handleAsync(
      'create_task',
      async () => {
        await createCrmTask({
          title: taskForm.title,
          due_date: new Date(taskForm.due_date).toISOString(),
          priority: taskForm.priority,
          lead_id: leadId,
          owner_user_id: user.id,
        })
        setTaskForm(null)
      },
      'Tâche créée.',
    )
  }

  const handleCreateDeal = () => {
    if (!dealForm || !user) return
    void handleAsync(
      'create_deal',
      async () => {
        await createCrmDeal({
          lead_id: leadId,
          owner_user_id: user.id,
          title: dealForm.title,
          amount: dealForm.amount ? Number(dealForm.amount) : null,
          probability_percent: dealForm.probability_percent,
        })
        setDealForm(null)
      },
      'Deal créé.',
    )
  }

  const handleConfirmCustomer = () => {
    if (!confirmCustomer || !user) return
    void handleAsync(
      'confirm_customer',
      async () => {
        await convertLeadToCustomer(leadId, {
          human_validated: true,
          validation_reason: confirmCustomer.validation_reason,
          evidence_source: confirmCustomer.evidence_source,
          next_action: confirmCustomer.next_action,
          conversion_note: confirmCustomer.conversion_note,
          requested_by: user.id,
        })
        setConfirmCustomer(null)
      },
      'Conversion client demandée.',
    )
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="CRM · Lead Details"
          title="Chargement du lead"
          subtitle="Récupération des données commerciales en cours."
        />
        <LoadingState fullHeight />
      </div>
    )
  }

  if (loadError || !lead) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="CRM · Lead Details"
          title="Lead introuvable"
          subtitle="Le lead demandé n'a pas pu être chargé."
        />
        <ErrorState
          title="Impossible de charger ce lead"
          message={loadError || 'Lead inexistant.'}
          actionLabel="Réessayer"
          onAction={() => void refresh()}
        />
      </div>
    )
  }

  const statusLabel = getCrmBusinessStateLabel(lead)
  const statusTone = getStatusTone(lead.customer_status || lead.status)
  const scoreTone = getScoreTone(lead.score)
  const activeDraft = getActiveDraft(lead, sortedDrafts)
  const latestSentDraft = getLatestSentDraft(sortedDrafts)
  const viewingDraft = viewingDraftId
    ? sortedDrafts.find((draft) => draft.id === viewingDraftId) ?? null
    : null

  const statePlan = buildStatePlan(lead, sortedDrafts, {
    can,
    pendingAction,
    activeDraft,
    latestSentDraft,
    lastInteractionLabel: lastInteraction?.label || null,
    onGenerateDraft: () => void handleGenerateDraft(),
    onViewDraft: handleViewDraft,
    onEditDraft: (draft) =>
      setEditing({ draftId: draft.id, subject: draft.subject || '', body: stripHtml(draft.body || '') }),
    onReviewDraft: (draftId) => void handleReview(draftId),
    onApproveDraft: (draftId) => void handleApprove(draftId),
    onRejectDraft: (draftId) => void handleReject(draftId),
    onSendDraft: (draftId) => void handleSend(draftId),
    onConfirmCustomer: openConfirmCustomerForm,
    onCreateTask: openTaskForm,
    onCreateDeal: openDealForm,
    onRefresh: () => void refresh(),
  })

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="CRM · Lead Details"
        title={toTitleCase(lead.name)}
        subtitle={`${lead.company} · ${lead.email}${lead.phone ? ` · ${lead.phone}` : ''}`}
        statusLabel={statusLabel}
        statusTone={statusTone}
        actions={
          <ActionButton
            label={
              <span className="inline-flex items-center gap-1.5">
                <Icon name="chevron-right" size={14} /> Retour aux leads
              </span>
            }
            variant="ghost"
            onClick={() => navigate('/crm-leads')}
          />
        }
      />

      {actionError ? (
        <ErrorState
          title="Action en échec"
          message={actionError}
          actionLabel="Fermer"
          onAction={() => setActionError(null)}
        />
      ) : null}
      {actionInfo ? (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm font-medium text-emerald-100">
          {actionInfo}
        </div>
      ) : null}

      <section className="grid gap-4 md:grid-cols-3">
        <KpiCard
          label="Score IA"
          value={`${lead.score}/100`}
          helper={
            scoreTone === 'success'
              ? 'Hot Lead'
              : scoreTone === 'warning'
                ? 'À qualifier'
                : 'Lead froid'
          }
          tone={scoreTone === 'success' ? 'emerald' : scoreTone === 'warning' ? 'amber' : 'rose'}
          icon="spark"
        />
        <KpiCard
          label="Statut"
          value={statusLabel}
          helper={lead.crm_display_state?.display_stage || '—'}
          tone={statusTone === 'success' ? 'emerald' : statusTone === 'warning' ? 'amber' : 'sky'}
          icon="client"
        />
        <KpiCard
          label="Dernier contact"
          value={lastInteraction ? lastInteraction.date : 'Aucun contact récent'}
          helper={lastInteraction ? lastInteraction.label : undefined}
          tone="slate"
          icon="clock"
        />
      </section>

      <LeadNeedCard lead={lead} />

      <NextStepCard plan={statePlan} />

      <section className="grid gap-4 lg:grid-cols-3">
        <AppCard title="Identité" eyebrow="Lead" className="lg:col-span-2">
          <div className="grid gap-3 px-5 py-4 sm:grid-cols-2">
            <InfoRow label="Nom" value={toTitleCase(lead.name)} />
            <InfoRow label="Entreprise" value={lead.company} />
            <InfoRow label="Email" value={lead.email} />
            <InfoRow label="Téléphone" value={lead.phone || '—'} />
            <InfoRow label="Source" value={lead.source} />
            <InfoRow
              label="Valeur estimée"
              value={lead.estimated_value ? formatCrmCurrency(lead.estimated_value) : 'Non renseignée'}
            />
          </div>
        </AppCard>

        <AppCard title="Outils rapides" eyebrow="Toujours disponibles">
          <div className="flex flex-col gap-2 px-5 py-4">
            <ActionButton
              label={
                <span className="inline-flex items-center gap-2">
                  <Icon name="check" size={14} /> Créer tâche
                </span>
              }
              variant="secondary"
              fullWidth
              disabled={!can('crm.tasks.manage')}
              onClick={openTaskForm}
            />
            <ActionButton
              label={
                <span className="inline-flex items-center gap-2">
                  <Icon name="target" size={14} /> Créer deal
                </span>
              }
              variant="secondary"
              fullWidth
              disabled={!can('crm.deals.manage')}
              onClick={openDealForm}
            />
            <ActionButton
              label={
                <span className="inline-flex items-center gap-2">
                  <Icon name="reload" size={14} /> Actualiser
                </span>
              }
              variant="ghost"
              fullWidth
              onClick={() => void refresh()}
            />
          </div>
        </AppCard>
      </section>

      {pendingDrafts.length > 0 ? (
        <AppCard
          title="Brouillons en attente de validation"
          eyebrow="À traiter"
          description="Approuvez, modifiez ou rejetez les brouillons générés par l'IA."
          tone="warning"
          actions={<StatusBadge label={`${pendingDrafts.length} à traiter`} status="warning" />}
        >
          <div className="divide-y divide-slate-800">
            {pendingDrafts.map((draft) => (
              <PendingDraftRow
                key={draft.id}
                draft={draft}
                isExpanded={expandedDraftId === draft.id}
                onToggle={() =>
                  setExpandedDraftId(expandedDraftId === draft.id ? null : draft.id)
                }
                isPending={(key: string) => pendingAction === `${key}_${draft.id}`}
                onEdit={() =>
                  setEditing({
                    draftId: draft.id,
                    subject: draft.subject || '',
                    body: stripHtml(draft.body || ''),
                  })
                }
                onReview={() => void handleReview(draft.id)}
                onApprove={() => void handleApprove(draft.id)}
                onReject={() => void handleReject(draft.id)}
                onSend={() => void handleSend(draft.id)}
                canReview={can('crm.drafts.review')}
                canApprove={can('crm.email.approve')}
                canSend={can('crm.email.send')}
              />
            ))}
          </div>
        </AppCard>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-2">
        <AppCard
          title="Emails envoyés / approuvés"
          eyebrow="Communications"
          actions={
            <StatusBadge
              label={`${otherDrafts.length}`}
              status={otherDrafts.length === 0 ? 'neutral' : 'info'}
            />
          }
        >
          {otherDrafts.length === 0 ? (
            <div className="px-5 py-4">
              <EmptyState
                title="Aucun email"
                description="Aucun brouillon n'a encore été approuvé ou envoyé."
                icon="mail"
              />
            </div>
          ) : (
            <ul className="divide-y divide-slate-800">
              {otherDrafts.slice(0, 5).map((draft) => (
                <li key={draft.id} className="px-5 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-white">
                        {draft.subject || 'Sans objet'}
                      </p>
                      <p className="mt-1 text-xs text-slate-400">
                        {draft.sent_at
                          ? `Envoyé le ${formatCrmDate(draft.sent_at)}`
                          : `Mis à jour le ${formatCrmDate(draft.updated_at)}`}
                      </p>
                      <DraftActivityLines draft={draft} />
                    </div>
                    <StatusBadge
                      label={getCrmDraftStatusLabel(draft.status)}
                      status={getDraftStatusTone(draft.status)}
                      size="sm"
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </AppCard>

        <AppCard
          title="Tâches liées"
          eyebrow="3 dernières"
          actions={<StatusBadge label={`${tasks.length}`} status="info" />}
        >
          {sortedTasks.length === 0 ? (
            <div className="px-5 py-4">
              <EmptyState
                title="Aucune tâche"
                description="Aucune tâche n'est encore liée à ce lead."
                icon="check"
              />
            </div>
          ) : (
            <ul className="divide-y divide-slate-800">
              {sortedTasks.map((task) => (
                <li key={task.id} className="px-5 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-white">{task.title}</p>
                      <p className="mt-1 text-xs text-slate-400">
                        Échéance · {formatCrmDate(task.due_date)}
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <PriorityBadge
                        label={
                          task.priority === 'high'
                            ? 'Haute'
                            : task.priority === 'low'
                              ? 'Basse'
                              : 'Moyenne'
                        }
                        tone={
                          task.priority === 'high'
                            ? 'red'
                            : task.priority === 'low'
                              ? 'slate'
                              : 'orange'
                        }
                      />
                      <StatusBadge
                        label={
                          task.status === 'done'
                            ? 'Terminée'
                            : task.status === 'cancelled'
                              ? 'Annulée'
                              : task.is_overdue
                                ? 'En retard'
                                : 'En cours'
                        }
                        status={
                          task.status === 'done'
                            ? 'success'
                            : task.status === 'cancelled'
                              ? 'neutral'
                              : task.is_overdue
                                ? 'danger'
                                : 'info'
                        }
                        size="sm"
                      />
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </AppCard>
      </section>

      <AppCard
        title="Deals liés"
        eyebrow="Pipeline"
        actions={<StatusBadge label={`${deals.length}`} status="info" />}
      >
        {deals.length === 0 ? (
          <div className="px-5 py-4">
            <EmptyState
              title="Aucun deal"
              description="Aucun deal n'est encore lié à ce lead."
              icon="target"
            />
          </div>
        ) : (
          <ul className="divide-y divide-slate-800">
            {deals.map((deal) => (
              <li key={deal.id} className="px-5 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-white">{deal.title}</p>
                    <p className="mt-1 text-xs text-slate-400">
                      {deal.amount ? formatCrmCurrency(deal.amount) : 'Montant non défini'} ·{' '}
                      {deal.probability_percent}% de probabilité
                    </p>
                  </div>
                  <StatusBadge
                    label={STAGE_LABELS[deal.stage]}
                    status={STAGE_TONES[deal.stage]}
                    size="sm"
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </AppCard>

      {viewingDraft ? (
        <Modal title="Aperçu du brouillon" onClose={() => setViewingDraftId(null)}>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Objet</p>
            <p className="mt-1 text-sm font-semibold text-white">
              {viewingDraft.subject || 'Sans objet'}
            </p>
          </div>
          <div className="max-h-[60vh] overflow-auto rounded-lg border border-slate-800 bg-slate-950 px-4 py-3 text-sm leading-6 text-slate-200 [&_a]:text-sky-300 [&_a]:underline [&_p]:mb-3">
            <div dangerouslySetInnerHTML={{ __html: viewingDraft.body || '<em>(corps vide)</em>' }} />
          </div>
          <div className="flex justify-end pt-2">
            <ActionButton label="Fermer" variant="ghost" onClick={() => setViewingDraftId(null)} />
          </div>
        </Modal>
      ) : null}

      {editing ? (
        <Modal title="Modifier le brouillon" onClose={() => setEditing(null)}>
          <Field label="Objet">
            <input
              value={editing.subject}
              onChange={(event) => setEditing({ ...editing, subject: event.target.value })}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
            />
          </Field>
          <Field label="Corps">
            <textarea
              value={editing.body}
              onChange={(event) => setEditing({ ...editing, body: event.target.value })}
              rows={10}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
            />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <ActionButton label="Annuler" variant="ghost" onClick={() => setEditing(null)} />
            <ActionButton
              label="Enregistrer"
              variant="primary"
              disabled={pendingAction === `update_${editing.draftId}`}
              onClick={handleSaveEdit}
            />
          </div>
        </Modal>
      ) : null}

      {taskForm ? (
        <Modal title="Créer une tâche" onClose={() => setTaskForm(null)}>
          <Field label="Titre">
            <input
              value={taskForm.title}
              onChange={(event) => setTaskForm({ ...taskForm, title: event.target.value })}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
            />
          </Field>
          <Field label="Échéance">
            <input
              type="datetime-local"
              value={taskForm.due_date}
              onChange={(event) => setTaskForm({ ...taskForm, due_date: event.target.value })}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
            />
          </Field>
          <Field label="Priorité">
            <select
              value={taskForm.priority}
              onChange={(event) =>
                setTaskForm({ ...taskForm, priority: event.target.value as CrmTaskPriority })
              }
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
            >
              <option value="low">Basse</option>
              <option value="medium">Moyenne</option>
              <option value="high">Haute</option>
            </select>
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <ActionButton label="Annuler" variant="ghost" onClick={() => setTaskForm(null)} />
            <ActionButton
              label="Créer"
              variant="primary"
              disabled={!taskForm.title.trim() || pendingAction === 'create_task'}
              onClick={handleCreateTask}
            />
          </div>
        </Modal>
      ) : null}

      {dealForm ? (
        <Modal title="Créer un deal" onClose={() => setDealForm(null)}>
          <Field label="Intitulé du deal">
            <input
              value={dealForm.title}
              onChange={(event) => setDealForm({ ...dealForm, title: event.target.value })}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
            />
          </Field>
          <Field label="Montant (TND)">
            <input
              type="number"
              value={dealForm.amount}
              onChange={(event) => setDealForm({ ...dealForm, amount: event.target.value })}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
            />
          </Field>
          <Field label="Probabilité (%)">
            <input
              type="number"
              min={0}
              max={100}
              value={dealForm.probability_percent}
              onChange={(event) =>
                setDealForm({
                  ...dealForm,
                  probability_percent: Math.max(
                    0,
                    Math.min(100, Number(event.target.value) || 0),
                  ),
                })
              }
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
            />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <ActionButton label="Annuler" variant="ghost" onClick={() => setDealForm(null)} />
            <ActionButton
              label="Créer"
              variant="primary"
              disabled={!dealForm.title.trim() || pendingAction === 'create_deal'}
              onClick={handleCreateDeal}
            />
          </div>
        </Modal>
      ) : null}

      {confirmCustomer ? (
        <Modal title="Confirmer comme client" onClose={() => setConfirmCustomer(null)}>
          <Field label="Raison de la conversion">
            <input
              value={confirmCustomer.validation_reason}
              onChange={(event) =>
                setConfirmCustomer({ ...confirmCustomer, validation_reason: event.target.value })
              }
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
            />
          </Field>
          <Field label="Source de la preuve">
            <select
              value={confirmCustomer.evidence_source}
              onChange={(event) =>
                setConfirmCustomer({ ...confirmCustomer, evidence_source: event.target.value })
              }
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
            >
              <option>Réponse email</option>
              <option>Appel téléphonique</option>
              <option>Réunion</option>
              <option>Message WhatsApp</option>
              <option>Note manuelle</option>
            </select>
          </Field>
          <Field label="Prochaine action">
            <input
              value={confirmCustomer.next_action}
              onChange={(event) =>
                setConfirmCustomer({ ...confirmCustomer, next_action: event.target.value })
              }
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
            />
          </Field>
          <Field label="Note (optionnelle)">
            <textarea
              value={confirmCustomer.conversion_note}
              onChange={(event) =>
                setConfirmCustomer({ ...confirmCustomer, conversion_note: event.target.value })
              }
              rows={3}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
            />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <ActionButton
              label="Annuler"
              variant="ghost"
              onClick={() => setConfirmCustomer(null)}
            />
            <ActionButton
              label="Confirmer"
              variant="urgent"
              disabled={pendingAction === 'confirm_customer'}
              onClick={handleConfirmCustomer}
            />
          </div>
        </Modal>
      ) : null}
    </div>
  )
}

type InfoRowProps = { label: string; value: string }
function InfoRow({ label, value }: InfoRowProps) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 truncate text-sm text-slate-200">{value}</p>
    </div>
  )
}

type PendingDraftRowProps = {
  draft: CrmEmailDraftItem
  isExpanded: boolean
  onToggle: () => void
  isPending: (key: string) => boolean
  onEdit: () => void
  onReview: () => void
  onApprove: () => void
  onReject: () => void
  onSend: () => void
  canReview: boolean
  canApprove: boolean
  canSend: boolean
}

function PendingDraftRow({
  draft,
  isExpanded,
  onToggle,
  isPending,
  onEdit,
  onReview,
  onApprove,
  onReject,
  onSend,
  canReview,
  canApprove,
  canSend,
}: PendingDraftRowProps) {
  const canBeReviewed = ['draft_generated', 'edited'].includes(draft.status)
  const canBeApproved = draft.status === 'reviewed'
  const canBeSent = draft.status === 'approved' || draft.status === 'failed'

  return (
    <div className="px-5 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-white">
            {draft.subject || 'Brouillon sans objet'}
          </p>
          <p className="mt-1 text-xs text-slate-400">
            {draft.draft_type === 'welcome' ? 'Email de bienvenue' : 'Email commercial'} ·{' '}
            mis à jour le {formatCrmDate(draft.updated_at)}
          </p>
        </div>
        <StatusBadge
          label={getCrmDraftStatusLabel(draft.status)}
          status={getDraftStatusTone(draft.status)}
          size="sm"
        />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <ActionButton
          label={isExpanded ? 'Masquer' : 'Voir'}
          variant="ghost"
          size="sm"
          onClick={onToggle}
        />
        <ActionButton
          label="Modifier"
          variant="secondary"
          size="sm"
          disabled={!canReview}
          onClick={onEdit}
        />
        {canBeReviewed ? (
          <ActionButton
            label="Marquer relu"
            variant="secondary"
            size="sm"
            disabled={!canReview || isPending('review')}
            onClick={onReview}
          />
        ) : null}
        {canBeApproved ? (
          <ActionButton
            label="Approuver"
            variant="primary"
            size="sm"
            disabled={!canApprove || isPending('approve')}
            onClick={onApprove}
          />
        ) : null}
        <ActionButton
          label="Rejeter"
          variant="danger"
          size="sm"
          disabled={!canReview || isPending('reject')}
          onClick={onReject}
        />
        {canBeSent ? (
          <ActionButton
            label="Envoyer"
            variant="urgent"
            size="sm"
            disabled={!canSend || isPending('send')}
            onClick={onSend}
          />
        ) : null}
        {draft.status === 'sending' ? (
          <span
            className="inline-flex items-center gap-1.5 rounded-full border border-sky-500/40 bg-sky-500/10 px-2.5 py-1 text-xs font-semibold text-sky-200"
            title="L'envoi automatisé est en cours. Attendez le retour du workflow."
          >
            <Icon name="clock" size={12} /> Envoi en cours…
          </span>
        ) : null}
        {draft.status === 'sent' ? (
          <span
            className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-200"
            title={draft.sent_at ? `Envoyé le ${formatCrmDate(draft.sent_at)}` : 'Envoyé'}
          >
            <Icon name="check" size={12} /> Envoyé
          </span>
        ) : null}
      </div>
      <DraftActivityLines draft={draft} />
      {isExpanded ? (
        <div className="mt-3 max-h-72 overflow-auto rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs leading-5 text-slate-300 [&_a]:text-sky-300 [&_a]:underline [&_p]:mb-2">
          <div dangerouslySetInnerHTML={{ __html: draft.body || '<em>(corps vide)</em>' }} />
        </div>
      ) : null}
    </div>
  )
}

function DraftActivityLines({ draft }: { draft: CrmEmailDraftItem }) {
  // Auditable trail of who touched this draft. Falls back to the raw user_id
  // when the backend could not resolve the name (e.g. deleted user).
  const entries: { label: string; actor: string; at: string | null | undefined }[] = []
  const actorName = (name?: string | null, id?: string | null) =>
    name?.trim() || id?.trim() || null

  const editedActor = actorName(draft.edited_by_name, draft.edited_by)
  if (editedActor && draft.status === 'edited') {
    entries.push({ label: 'Modifié par', actor: editedActor, at: draft.updated_at })
  }
  const reviewedActor = actorName(draft.reviewed_by_name, draft.reviewed_by)
  if (reviewedActor && draft.reviewed_at) {
    entries.push({ label: 'Relu par', actor: reviewedActor, at: draft.reviewed_at })
  }
  const approvedActor = actorName(draft.approved_by_name, draft.approved_by)
  if (approvedActor && draft.approved_at) {
    entries.push({ label: 'Approuvé par', actor: approvedActor, at: draft.approved_at })
  }
  const rejectedActor = actorName(draft.rejected_by_name, draft.rejected_by)
  if (rejectedActor && draft.rejected_at) {
    entries.push({ label: 'Rejeté par', actor: rejectedActor, at: draft.rejected_at })
  }

  if (entries.length === 0) return null

  return (
    <ul className="mt-3 space-y-0.5 border-l-2 border-slate-800 pl-3 text-[11px] text-slate-500">
      {entries.map((entry) => (
        <li key={`${entry.label}-${entry.actor}`}>
          <span className="font-medium text-slate-400">{entry.label}</span>{' '}
          <span className="text-slate-300">{entry.actor}</span>
          {entry.at ? <span> · {formatCrmDate(entry.at)}</span> : null}
        </li>
      ))}
    </ul>
  )
}

type ModalProps = { title: string; onClose: () => void; children: ReactNode }
function Modal({ title, onClose, children }: ModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4">
      <div className="w-full max-w-2xl rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
          <h2 className="text-base font-semibold text-white">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
            aria-label="Fermer"
          >
            <Icon name="close" size={16} />
          </button>
        </div>
        <div className="space-y-4 px-5 py-4">{children}</div>
      </div>
    </div>
  )
}

type LeadNeedCardProps = { lead: CrmLeadDetail }

function LeadNeedCard({ lead }: LeadNeedCardProps) {
  const message = (lead.message || '').trim()
  const aiSummary = (lead.ai_summary || '').trim()
  const recommended = (lead.recommended_action || '').trim()
  const intention = (lead.intention || '').trim()
  const productService = (lead.product_service || '').trim()

  const hasAnyContent = Boolean(message || aiSummary || recommended || intention || productService)
  if (!hasAnyContent) {
    return (
      <AppCard title="Besoin du client" eyebrow="Contexte commercial" tone="muted">
        <p className="px-5 py-4 text-sm italic text-slate-400">
          Aucune information de besoin n'a encore été capturée pour ce lead.
        </p>
      </AppCard>
    )
  }

  return (
    <AppCard
      title="Besoin du client"
      eyebrow="Contexte commercial"
      description="Ce que le client a demandé + ce que l'IA en a compris."
    >
      <div className="space-y-4 px-5 py-4">
        {message ? (
          <NeedSection
            label="Message reçu"
            iconName="mail"
            tone="info"
            text={message}
          />
        ) : null}
        {aiSummary ? (
          <NeedSection
            label="Résumé IA du besoin"
            iconName="spark"
            tone="success"
            text={aiSummary}
          />
        ) : null}
        {recommended ? (
          <NeedSection
            label="Recommandation IA"
            iconName="target"
            tone="warning"
            text={recommended}
          />
        ) : null}
        {(intention || productService) ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {intention ? (
              <div className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Intention
                </p>
                <p className="mt-1 text-sm text-slate-100">{intention}</p>
              </div>
            ) : null}
            {productService ? (
              <div className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Produit / service ciblé
                </p>
                <p className="mt-1 text-sm text-slate-100">{productService}</p>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </AppCard>
  )
}

type NeedSectionProps = {
  label: string
  iconName: IconName
  tone: 'info' | 'success' | 'warning'
  text: string
}

function NeedSection({ label, iconName, tone, text }: NeedSectionProps) {
  const borderToneClass = {
    info: 'border-sky-500/30 bg-sky-500/5',
    success: 'border-emerald-500/30 bg-emerald-500/5',
    warning: 'border-amber-500/30 bg-amber-500/5',
  }[tone]
  const iconToneClass = {
    info: 'text-sky-300',
    success: 'text-emerald-300',
    warning: 'text-amber-300',
  }[tone]
  return (
    <div className={`rounded-lg border px-4 py-3 ${borderToneClass}`}>
      <div className="flex items-center gap-2">
        <Icon name={iconName} size={14} className={iconToneClass} />
        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-300">
          {label}
        </p>
      </div>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-100">{text}</p>
    </div>
  )
}

type NextStepCardProps = { plan: StatePlan }

function NextStepCard({ plan }: NextStepCardProps) {
  return (
    <AppCard
      title={plan.title}
      eyebrow="Prochaine étape"
      description={plan.description}
      tone={plan.tone}
      actions={
        plan.workflowBadge ? (
          <StatusBadge label={plan.workflowBadge.label} status={plan.workflowBadge.status} />
        ) : undefined
      }
    >
      <div className="space-y-4 px-5 py-4">
        {plan.contextItems && plan.contextItems.length > 0 ? (
          <dl className="grid gap-3 sm:grid-cols-3">
            {plan.contextItems.map((item) => (
              <div key={item.label} className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2">
                <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  {item.label}
                </dt>
                <dd className="mt-1 truncate text-sm text-slate-100">{item.value}</dd>
              </div>
            ))}
          </dl>
        ) : null}
        {plan.primary || plan.secondary || plan.tertiary ? (
          <div className="flex flex-wrap gap-2">
            {plan.primary ? <PlanActionButton action={plan.primary} /> : null}
            {plan.secondary ? <PlanActionButton action={plan.secondary} /> : null}
            {plan.tertiary ? <PlanActionButton action={plan.tertiary} /> : null}
          </div>
        ) : (
          <p className="text-xs italic text-slate-500">
            Aucune action manuelle requise pour le moment.
          </p>
        )}
      </div>
    </AppCard>
  )
}

function PlanActionButton({ action }: { action: StatePlanAction }) {
  return (
    <ActionButton
      label={
        <span className="inline-flex items-center gap-2">
          <Icon name={action.iconName} size={14} /> {action.label}
        </span>
      }
      variant={action.variant}
      disabled={action.disabled}
      onClick={action.onClick}
    />
  )
}

type FieldProps = { label: string; children: ReactNode }
function Field({ label, children }: FieldProps) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </span>
      {children}
    </label>
  )
}

export default CRMLeadDetailsPage
