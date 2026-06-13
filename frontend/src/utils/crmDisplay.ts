import type { CrmLeadRecord } from '../services/crmService'

type DisplayLead = Omit<Partial<CrmLeadRecord>, 'priority' | 'status'> & {
  priority?: string | null
  status?: string | null
  crm_display_state?: (CrmLeadRecord['crm_display_state'] & { next_action_label?: string | null }) | null
}

type CrmDashboardBucket =
  | 'lead_to_qualify'
  | 'communication_to_generate'
  | 'communication_to_review'
  | 'communication_awaiting_decision'
  | 'communication_ready_to_send'
  | 'automation_in_progress'
  | 'waiting_response'
  | 'conversion_to_confirm'
  | 'follow_up_or_close'
  | 'follow_up_required'
  | 'automation_issue'
  | 'welcome_to_prepare'
  | 'welcome_to_review'
  | 'welcome_ready_to_send'
  | 'onboarding_follow_up'

type CrmUiState = {
  stateKey: string
  lifecycleLabel: string
  nextActionLabel: string
  dashboardBucket: CrmDashboardBucket
  needsHumanAction: boolean
  priorityActionTitle: string
  priorityActionDescription: string
  listNextActionLabel: string
  detailsNextActionLabel: string
  latestEventLabel: string
  badgeLabel: string
}

const UI_STATE_BY_KEY: Record<string, Omit<CrmUiState, 'stateKey' | 'listNextActionLabel' | 'detailsNextActionLabel'>> = {
  lead_collected: {
    lifecycleLabel: 'Lead',
    nextActionLabel: 'Relire la recommandation IA et qualifier le lead',
    dashboardBucket: 'lead_to_qualify',
    needsHumanAction: true,
    priorityActionTitle: 'Qualifier le lead CRM',
    priorityActionDescription: 'Un lead doit être relu et qualifié avant la prochaine étape commerciale.',
    latestEventLabel: 'Lead collecté',
    badgeLabel: 'Qualification',
  },
  lead_analyzed: {
    lifecycleLabel: 'Lead',
    nextActionLabel: 'Relire la recommandation IA et qualifier le lead',
    dashboardBucket: 'lead_to_qualify',
    needsHumanAction: true,
    priorityActionTitle: 'Qualifier le lead CRM',
    priorityActionDescription: 'La recommandation IA doit être relue avant qualification.',
    latestEventLabel: 'Analyse IA terminée',
    badgeLabel: 'Qualification',
  },
  prospect_qualified: {
    lifecycleLabel: 'Prospect',
    nextActionLabel: 'Générer un brouillon de communication',
    dashboardBucket: 'communication_to_generate',
    needsHumanAction: true,
    priorityActionTitle: 'Préparer une communication commerciale',
    priorityActionDescription: 'Un prospect qualifié attend une première communication commerciale.',
    latestEventLabel: 'Prospect qualifié',
    badgeLabel: 'Communication',
  },
  draft_missing: {
    lifecycleLabel: 'Prospect',
    nextActionLabel: 'Générer un brouillon de communication',
    dashboardBucket: 'communication_to_generate',
    needsHumanAction: true,
    priorityActionTitle: 'Préparer une communication commerciale',
    priorityActionDescription: 'Un prospect qualifié attend une première communication commerciale.',
    latestEventLabel: 'Brouillon manquant',
    badgeLabel: 'Communication',
  },
  draft_generated: {
    lifecycleLabel: 'Prospect',
    nextActionLabel: 'Relire le brouillon de communication',
    dashboardBucket: 'communication_to_review',
    needsHumanAction: true,
    priorityActionTitle: 'Relire une communication générée par l’IA',
    priorityActionDescription: 'Une communication doit être relue avant décision humaine.',
    latestEventLabel: 'Brouillon généré',
    badgeLabel: 'À relire',
  },
  edited: {
    lifecycleLabel: 'Prospect',
    nextActionLabel: 'Relire le brouillon de communication',
    dashboardBucket: 'communication_to_review',
    needsHumanAction: true,
    priorityActionTitle: 'Relire une communication générée par l’IA',
    priorityActionDescription: 'Une communication doit être relue avant décision humaine.',
    latestEventLabel: 'Brouillon modifié',
    badgeLabel: 'À relire',
  },
  draft_reviewed: {
    lifecycleLabel: 'Prospect',
    nextActionLabel: 'Approuver ou rejeter le brouillon relu',
    dashboardBucket: 'communication_awaiting_decision',
    needsHumanAction: true,
    priorityActionTitle: 'Décider sur un brouillon relu',
    priorityActionDescription: 'Un brouillon relu attend une décision humaine : approbation ou rejet.',
    latestEventLabel: 'Brouillon relu',
    badgeLabel: 'Décision',
  },
  draft_approved: {
    lifecycleLabel: 'Prospect',
    nextActionLabel: 'Envoyer l’email approuvé',
    dashboardBucket: 'communication_ready_to_send',
    needsHumanAction: true,
    priorityActionTitle: 'Envoyer une communication approuvée',
    priorityActionDescription: 'Une communication approuvée est prête pour l’envoi email automatisé.',
    latestEventLabel: 'Brouillon approuvé',
    badgeLabel: 'Prêt à envoyer',
  },
  email_sending: {
    lifecycleLabel: 'Prospect',
    nextActionLabel: 'Envoi de l’email en cours',
    dashboardBucket: 'automation_in_progress',
    needsHumanAction: false,
    priorityActionTitle: 'Suivre l’envoi en cours',
    priorityActionDescription: 'L’envoi email automatisé est en cours.',
    latestEventLabel: 'Envoi en cours',
    badgeLabel: 'En cours',
  },
  email_sent_waiting_response: {
    lifecycleLabel: 'Prospect',
    nextActionLabel: 'Attendre ou enregistrer la réponse du prospect',
    dashboardBucket: 'waiting_response',
    needsHumanAction: true,
    priorityActionTitle: 'Suivre la réponse du prospect',
    priorityActionDescription: 'L’email commercial a été envoyé. Attendez la réponse ou enregistrez-la dès réception.',
    latestEventLabel: 'Email envoyé',
    badgeLabel: 'Réponse attendue',
  },
  waiting_response: {
    lifecycleLabel: 'Prospect',
    nextActionLabel: 'Attendre ou enregistrer la réponse du prospect',
    dashboardBucket: 'waiting_response',
    needsHumanAction: true,
    priorityActionTitle: 'Suivre la réponse du prospect',
    priorityActionDescription: 'L’email commercial a été envoyé. Attendez la réponse ou enregistrez-la dès réception.',
    latestEventLabel: 'Réponse attendue',
    badgeLabel: 'Réponse attendue',
  },
  positive_response_recorded: {
    lifecycleLabel: 'Prospect',
    nextActionLabel: 'Confirmer la conversion en client',
    dashboardBucket: 'conversion_to_confirm',
    needsHumanAction: true,
    priorityActionTitle: 'Confirmer la conversion client',
    priorityActionDescription: 'Une réponse positive a été enregistrée. Une validation humaine est nécessaire.',
    latestEventLabel: 'Réponse positive enregistrée',
    badgeLabel: 'Conversion',
  },
  conversion_ready: {
    lifecycleLabel: 'Prospect',
    nextActionLabel: 'Confirmer la conversion en client',
    dashboardBucket: 'conversion_to_confirm',
    needsHumanAction: true,
    priorityActionTitle: 'Confirmer la conversion client',
    priorityActionDescription: 'Une réponse positive a été enregistrée. Une validation humaine est nécessaire.',
    latestEventLabel: 'Conversion prête',
    badgeLabel: 'Conversion',
  },
  negative_response_recorded: {
    lifecycleLabel: 'Prospect',
    nextActionLabel: 'Planifier une relance ou clôturer l’opportunité',
    dashboardBucket: 'follow_up_or_close',
    needsHumanAction: true,
    priorityActionTitle: 'Traiter une réponse négative',
    priorityActionDescription: 'Le prospect n’est pas intéressé ou nécessite une décision de relance.',
    latestEventLabel: 'Réponse négative enregistrée',
    badgeLabel: 'Relance',
  },
  not_interested: {
    lifecycleLabel: 'Prospect',
    nextActionLabel: 'Planifier une relance ou clôturer l’opportunité',
    dashboardBucket: 'follow_up_or_close',
    needsHumanAction: true,
    priorityActionTitle: 'Traiter une réponse négative',
    priorityActionDescription: 'Le prospect n’est pas intéressé ou nécessite une décision de relance.',
    latestEventLabel: 'Réponse négative enregistrée',
    badgeLabel: 'Relance',
  },
  neutral_response_recorded: {
    lifecycleLabel: 'Prospect',
    nextActionLabel: 'Répondre à la demande d’information ou planifier une relance',
    dashboardBucket: 'follow_up_required',
    needsHumanAction: true,
    priorityActionTitle: 'Répondre à une demande d’information',
    priorityActionDescription: 'Une réponse neutre nécessite une action commerciale.',
    latestEventLabel: 'Réponse à examiner',
    badgeLabel: 'À traiter',
  },
  follow_up_required: {
    lifecycleLabel: 'Prospect',
    nextActionLabel: 'Planifier une relance commerciale',
    dashboardBucket: 'follow_up_required',
    needsHumanAction: true,
    priorityActionTitle: 'Planifier une relance commerciale',
    priorityActionDescription: 'Une relance commerciale doit être planifiée et suivie.',
    latestEventLabel: 'Relance nécessaire',
    badgeLabel: 'Relance',
  },
  failed: {
    lifecycleLabel: 'Prospect',
    nextActionLabel: 'Corriger l’erreur ou réessayer l’envoi',
    dashboardBucket: 'automation_issue',
    needsHumanAction: true,
    priorityActionTitle: 'Corriger un problème d’automatisation',
    priorityActionDescription: 'Un envoi CRM automatisé a échoué et nécessite une correction.',
    latestEventLabel: 'Échec de l’envoi',
    badgeLabel: 'Problème',
  },
  conversion_pending: {
    lifecycleLabel: 'Prospect',
    nextActionLabel: 'Attendre la fin du workflow CRM_03 (conversion en cours)',
    dashboardBucket: 'automation_in_progress',
    needsHumanAction: false,
    priorityActionTitle: 'Conversion client en cours',
    priorityActionDescription:
      'La conversion vers le statut client est en cours côté workflow CRM_03. Aucune action humaine n’est requise tant que le brouillon de bienvenue n’est pas généré.',
    latestEventLabel: 'Conversion en cours',
    badgeLabel: 'Conversion en cours',
  },
  customer_converted: {
    lifecycleLabel: 'Client',
    nextActionLabel: 'Générer ou relire l’email de bienvenue',
    dashboardBucket: 'welcome_to_prepare',
    needsHumanAction: true,
    priorityActionTitle: 'Préparer l’email de bienvenue',
    priorityActionDescription: 'Le client est converti. La communication de bienvenue doit être préparée ou relue.',
    latestEventLabel: 'Client converti',
    badgeLabel: 'Bienvenue',
  },
  welcome_draft_generated: {
    lifecycleLabel: 'Client',
    nextActionLabel: 'Relire l’email de bienvenue',
    dashboardBucket: 'welcome_to_review',
    needsHumanAction: true,
    priorityActionTitle: 'Relire l’email de bienvenue',
    priorityActionDescription: 'L’email de bienvenue doit être relu avant décision humaine.',
    latestEventLabel: 'Brouillon de bienvenue généré',
    badgeLabel: 'Bienvenue',
  },
  welcome_draft_reviewed: {
    lifecycleLabel: 'Client',
    nextActionLabel: 'Relire l’email de bienvenue',
    dashboardBucket: 'welcome_to_review',
    needsHumanAction: true,
    priorityActionTitle: 'Relire l’email de bienvenue',
    priorityActionDescription: 'L’email de bienvenue doit être relu avant décision humaine.',
    latestEventLabel: 'Brouillon de bienvenue relu',
    badgeLabel: 'Bienvenue',
  },
  welcome_draft_approved: {
    lifecycleLabel: 'Client',
    nextActionLabel: 'Envoyer l’email de bienvenue approuvé',
    dashboardBucket: 'welcome_ready_to_send',
    needsHumanAction: true,
    priorityActionTitle: 'Envoyer l’email de bienvenue approuvé',
    priorityActionDescription: 'L’email de bienvenue approuvé est prêt à être envoyé.',
    latestEventLabel: 'Brouillon de bienvenue approuvé',
    badgeLabel: 'Prêt à envoyer',
  },
  welcome_email_sent: {
    lifecycleLabel: 'Client',
    nextActionLabel: 'Suivi onboarding client',
    dashboardBucket: 'onboarding_follow_up',
    needsHumanAction: false,
    priorityActionTitle: 'Suivre l’onboarding client',
    priorityActionDescription: 'Le client a reçu l’email de bienvenue. Le suivi onboarding peut continuer.',
    latestEventLabel: 'Email de bienvenue envoyé',
    badgeLabel: 'Onboarding',
  },
}

function normalize(value?: string | null) {
  return value?.trim().toLowerCase() || ''
}

function titleFromParts(value?: string | null) {
  if (!value) return 'Non renseigné'

  const trimmedValue = value.trim()
  if (!trimmedValue) return 'Non renseigné'

  return trimmedValue
    .split(/[-_]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(' ')
}

export function formatCrmDate(value?: string | null, fallback = 'Non renseigné') {
  if (!value) return fallback

  const parsedDate = new Date(value)
  if (Number.isNaN(parsedDate.getTime())) return fallback

  return new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsedDate)
}

export function formatCrmCurrency(value?: string | number | null) {
  if (value === null || value === undefined || value === '') return 'Non renseigné'

  const numericValue =
    typeof value === 'number'
      ? value
      : Number(String(value).replace(/[^\d.-]/g, ''))

  if (Number.isNaN(numericValue)) return String(value)

  return `${new Intl.NumberFormat('fr-FR', {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0,
  }).format(numericValue)} TND`
}

export function getCrmStatusLabel(status?: string | null) {
  const normalizedStatus = normalize(status)

  if (normalizedStatus === 'active_customer') return 'Client actif'
  if (normalizedStatus === 'inactive_customer') return 'Client inactif'
  if (normalizedStatus === 'loyal_customer') return 'Client fidèle'
  if (normalizedStatus === 'vip_customer' || normalizedStatus === 'vip') return 'Client VIP'
  if (normalizedStatus === 'customer' || normalizedStatus === 'client') return 'Client'
  if (normalizedStatus === 'conversion_pending') return 'Conversion en cours'
  if (normalizedStatus === 'prospect') return 'Prospect'
  if (normalizedStatus === 'lead' || normalizedStatus === 'new') return 'Lead'
  if (normalizedStatus === 'hot') return 'Lead'
  if (normalizedStatus === 'warm') return 'Prospect'
  if (normalizedStatus === 'cold') return 'Lead'

  return titleFromParts(status)
}

export function getCrmPriorityLabel(priority?: string | null, fallbackStatus?: string | null) {
  const normalizedPriority = normalize(priority || fallbackStatus)

  if (normalizedPriority === 'high' || normalizedPriority === 'hot') return 'Élevée'
  if (normalizedPriority === 'medium' || normalizedPriority === 'warm') return 'Moyenne'
  if (normalizedPriority === 'low' || normalizedPriority === 'cold') return 'Faible'
  if (normalizedPriority === 'urgent') return 'Urgente'

  return titleFromParts(priority || fallbackStatus)
}

export function getCrmSourceLabel(source?: string | null) {
  const normalizedSource = normalize(source)

  if (normalizedSource === 'website_form' || normalizedSource === 'website form' || normalizedSource === 'website') {
    return 'Formulaire web'
  }
  if (normalizedSource === 'manual') return 'Saisie manuelle'
  if (normalizedSource === 'email') return 'Email'
  if (normalizedSource === 'referral') return 'Recommandation'
  if (normalizedSource === 'unknown') return 'Inconnu'

  return titleFromParts(source)
}

export function getCrmIntentLabel(intent?: string | null) {
  const normalizedIntent = normalize(intent)

  if (normalizedIntent === 'purchase' || normalizedIntent === 'purchase_ready') return 'Achat'
  if (normalizedIntent === 'information') return 'Information'
  if (normalizedIntent === 'support') return 'Support'
  if (normalizedIntent === 'unknown') return 'Inconnu'

  return titleFromParts(intent)
}

export function getCrmUrgencyLabel(urgency?: string | null) {
  const normalizedUrgency = normalize(urgency)

  if (normalizedUrgency === 'high') return 'Élevée'
  if (normalizedUrgency === 'medium') return 'Moyenne'
  if (normalizedUrgency === 'low') return 'Faible'
  if (normalizedUrgency === 'urgent') return 'Urgente'
  if (normalizedUrgency === 'unknown') return 'Inconnu'

  return titleFromParts(urgency)
}

export function getCrmSentimentLabel(sentiment?: string | null) {
  const normalizedSentiment = normalize(sentiment)

  if (normalizedSentiment === 'positive') return 'Positif'
  if (normalizedSentiment === 'neutral') return 'Neutre'
  if (normalizedSentiment === 'negative') return 'Négatif'
  if (normalizedSentiment === 'unknown') return 'Inconnu'

  return titleFromParts(sentiment)
}

export function getCrmDraftStatusLabel(status?: string | null) {
  const normalizedStatus = normalize(status)

  if (normalizedStatus === 'draft_generated') return 'Brouillon généré'
  if (normalizedStatus === 'edited') return 'Modifié'
  if (normalizedStatus === 'reviewed') return 'Relu'
  if (normalizedStatus === 'approved') return 'Approuvé'
  if (normalizedStatus === 'sending') return 'Envoi en cours'
  if (normalizedStatus === 'sent') return 'Envoyé'
  if (normalizedStatus === 'failed') return 'Échec'
  if (normalizedStatus === 'rejected') return 'Rejeté'

  return titleFromParts(status)
}

export function getCrmBusinessStateLabel(lead: DisplayLead) {
  const displayStage = lead.crm_display_state?.display_stage
  if (displayStage) return getCrmStatusLabel(displayStage)

  return getCrmStatusLabel(lead.customer_status || lead.status)
}

export function getCrmBusinessStage(lead: DisplayLead) {
  // Priority order:
  // 1. crm_display_state.display_stage — backend-computed authoritative human stage
  // 2. crm_display_state.lifecycle_stage — backend lifecycle enum
  // 3. customer_status — persisted status field
  // 4. status — raw lead status
  // 5. UI lifecycle label from getCrmUiState
  // NOTE: display_stage takes priority over lifecycle_stage because the backend
  // can have a stale lifecycle_stage (e.g. "lead") while display_stage already
  // reflects the real business stage (e.g. "Prospect") based on current_state.

  function mapRaw(raw: string) {
    if (!raw) return ''
    if (raw === 'warm') return 'prospect'
    if (raw.includes('prospect')) return 'prospect'
    if (raw.includes('lead') && !raw.includes('vip') && !raw.includes('client') && !raw.includes('customer')) return 'lead'
    if (raw.includes('vip') || raw.includes('loyal') || raw.includes('fid') || raw.includes('fidèle')) return 'vip_customer'
    if (raw.includes('inactive') || raw.includes('inactif')) return 'inactive_customer'
    if (raw.includes('active') || raw.includes('actif')) return 'active_customer'
    if (raw.includes('client') || raw.includes('customer') || raw.includes('converted')) return 'customer'
    return ''
  }

  // 1. display_stage is the most reliable: it's what the backend computed as the
  //    human-visible stage. Use it first.
  const displayStage = normalize(lead.crm_display_state?.display_stage)
  const mappedDisplay = mapRaw(displayStage)
  if (mappedDisplay) return mappedDisplay

  // 2. lifecycle_stage enum
  const lifecycleStage = normalize(lead.crm_display_state?.lifecycle_stage)
  const mappedLifecycle = mapRaw(lifecycleStage)
  if (mappedLifecycle) return mappedLifecycle

  // 3. customer_status persisted field
  const customerStatus = normalize(lead.customer_status)
  const mappedCustomerStatus = mapRaw(customerStatus)
  if (mappedCustomerStatus) return mappedCustomerStatus

  // 4. raw status field
  const rawStatus = normalize(lead.status)
  const mappedStatus = mapRaw(rawStatus)
  if (mappedStatus) return mappedStatus

  // 5. fallback to UI lifecycle label
  const uiLabel = normalize(getCrmUiState(lead).lifecycleLabel)
  const mappedUi = mapRaw(uiLabel)
  if (mappedUi) return mappedUi

  return 'unknown'
}

export function normalizeCrmNextActionText(value?: string | null) {
  const normalizedAction = normalize(value)

  if (!normalizedAction) return ''
  if (normalizedAction.includes('approve or reject reviewed draft')) return 'Approuver ou rejeter le brouillon relu'
  if (normalizedAction.includes('draft reviewed')) return 'Brouillon relu'
  if (normalizedAction.includes('no urgent welcome action')) return 'Suivi onboarding client'
  if (normalizedAction.includes('no urgent email action')) return 'Aucune action email urgente'
  if (normalizedAction.includes('contact the lead')) return 'Contacter le lead pour clarifier le besoin'
  if (normalizedAction.includes('schedule a demo')) return 'Générer un brouillon de communication'
  if (
    normalizedAction.includes('email sent. wait for prospect response or schedule follow-up') ||
    normalizedAction.includes('email sent. wait for prospect response or schedule follow up')
  ) {
    return 'Email envoyé. Attendre la réponse du prospect ou planifier une relance.'
  }
  if (
    normalizedAction.includes('wait for response') ||
    normalizedAction.includes('wait for prospect') ||
    normalizedAction.includes('waiting response') ||
    normalizedAction.includes('waiting for response')
  ) {
    return 'Attendre la réponse du prospect'
  }
  if (normalizedAction.includes('review generated') && normalizedAction.includes('draft')) {
    return 'Relire le brouillon de communication avant envoi'
  }
  if (normalizedAction.includes('positive response') || normalizedAction.includes('conversion evidence')) {
    return 'Confirmer la conversion en client'
  }
  if (normalizedAction.includes('not interested') || normalizedAction.includes('negative response')) {
    return 'Planifier une relance ou clôturer l’opportunité'
  }
  if (normalizedAction.includes('follow-up') || normalizedAction.includes('follow up')) {
    return 'Planifier une relance commerciale'
  }
  if (normalizedAction.includes('welcome email sent')) return 'Suivi onboarding client'
  if (normalizedAction.includes('welcome') && normalizedAction.includes('approved')) {
    return 'Envoyer l’email de bienvenue approuvé'
  }
  if (normalizedAction.includes('approved') && normalizedAction.includes('email')) return 'Envoyer l’email approuvé'
  if (normalizedAction.includes('failed')) return 'Corriger l’erreur ou réessayer l’envoi'

  return value || ''
}

function getFallbackStateKey(lead: DisplayLead) {
  const displayState = lead.crm_display_state
  const rawAction = normalize(displayState?.computed_next_action || lead.next_action)
  const latestDraftStatus = normalize(displayState?.latest_draft_status)
  const responseState = displayState?.response_state
  const status = normalize(lead.customer_status || lead.status)

  if (displayState?.current_state) return displayState.current_state
  if (isCrmFinalCustomerOnboarding(lead)) return 'welcome_email_sent'
  if (responseState && UI_STATE_BY_KEY[responseState]) return responseState
  if (latestDraftStatus === 'reviewed') return 'draft_reviewed'
  if (latestDraftStatus === 'approved') return displayState?.latest_draft_type === 'welcome' ? 'welcome_draft_approved' : 'draft_approved'
  if (latestDraftStatus === 'sent') return displayState?.latest_draft_type === 'welcome' ? 'welcome_email_sent' : 'email_sent_waiting_response'
  if (latestDraftStatus === 'failed') return 'failed'
  if (latestDraftStatus === 'draft_generated' || latestDraftStatus === 'edited') {
    return displayState?.latest_draft_type === 'welcome' ? 'welcome_draft_generated' : 'draft_generated'
  }
  if (rawAction.includes('approve or reject reviewed draft')) return 'draft_reviewed'
  if (rawAction.includes('approved') && rawAction.includes('welcome')) return 'welcome_draft_approved'
  if (rawAction.includes('approved')) return 'draft_approved'
  if (rawAction.includes('review generated') || (rawAction.includes('review') && rawAction.includes('draft'))) return 'draft_generated'
  if (rawAction.includes('positive response') || rawAction.includes('conversion evidence')) return 'conversion_ready'
  if (rawAction.includes('negative response') || rawAction.includes('not interested')) return 'negative_response_recorded'
  if (rawAction.includes('neutral response')) return 'neutral_response_recorded'
  if (rawAction.includes('follow-up') || rawAction.includes('follow up')) return 'follow_up_required'
  if (rawAction.includes('failed')) return 'failed'
  if (status.includes('customer')) return 'customer_converted'
  if (status.includes('prospect') || status === 'warm') return 'draft_missing'

  return 'lead_collected'
}

export function getCrmUiState(lead: DisplayLead): CrmUiState {
  const stateKey = getFallbackStateKey(lead)
  const baseState = UI_STATE_BY_KEY[stateKey] || UI_STATE_BY_KEY.lead_collected
  const lifecycleLabel =
    stateKey === 'failed'
      ? getCrmBusinessStateLabel(lead)
      : baseState.lifecycleLabel
  const nextActionLabel = baseState.nextActionLabel || normalizeCrmNextActionText(lead.next_action)

  return {
    ...baseState,
    stateKey,
    lifecycleLabel,
    nextActionLabel,
    listNextActionLabel: nextActionLabel,
    detailsNextActionLabel: nextActionLabel,
  }
}

export function getCrmNextActionLabel(lead: DisplayLead) {
  return getCrmUiState(lead).nextActionLabel
}

export function getCrmCategoryLabel(lead: DisplayLead) {
  if (lead.customer_category) return titleFromParts(lead.customer_category)

  const status = getCrmBusinessStateLabel(lead)
  if (!status.toLowerCase().includes('client')) return 'À qualifier'

  const numericValue =
    typeof lead.estimated_value === 'number'
      ? lead.estimated_value
      : Number(String(lead.estimated_value || '').replace(/[^\d.-]/g, ''))
  const priority = normalize(lead.priority || lead.status)

  if ((!Number.isNaN(numericValue) && numericValue >= 10000) || priority === 'high' || priority === 'hot') {
    return 'VIP'
  }

  return 'Standard'
}

export function getCrmActivityStatusLabel(lead: DisplayLead) {
  if (lead.is_active === true) return 'Actif'
  if (lead.is_active === false) return 'Inactif'

  const status = getCrmBusinessStateLabel(lead)
  if (!status.toLowerCase().includes('client')) return 'À qualifier'
  if (!lead.last_contact_at) return 'Non renseigné'

  const lastContactDate = new Date(lead.last_contact_at)
  if (Number.isNaN(lastContactDate.getTime())) return 'Non renseigné'

  const elapsedDays = Math.floor((Date.now() - lastContactDate.getTime()) / (1000 * 60 * 60 * 24))

  if (elapsedDays <= 90) return 'Actif'
  if (elapsedDays > 180) return 'Inactif'

  return 'Non renseigné'
}

export function isCrmFinalCustomerOnboarding(lead: DisplayLead) {
  const displayState = lead.crm_display_state

  return Boolean(
    displayState?.current_state === 'welcome_email_sent' ||
      displayState?.welcome_email_sent ||
      (getCrmBusinessStateLabel(lead).toLowerCase().includes('client') &&
        normalize(displayState?.latest_draft_type) === 'welcome' &&
        normalize(displayState?.latest_draft_status) === 'sent') ||
      normalize(displayState?.computed_next_action).includes('no urgent welcome action') ||
      normalize(lead.next_action).includes('no urgent welcome action'),
  )
}

export function isCrmDraftWaitingForReview(lead: DisplayLead) {
  return getCrmUiState(lead).dashboardBucket === 'communication_to_review' ||
    getCrmUiState(lead).dashboardBucket === 'welcome_to_review'
}

export function isCrmAutomationIssue(lead: DisplayLead) {
  return getCrmUiState(lead).dashboardBucket === 'automation_issue'
}

export function isCrmConversionReady(lead: DisplayLead) {
  return getCrmUiState(lead).dashboardBucket === 'conversion_to_confirm'
}

export function isCrmFollowUpNeeded(lead: DisplayLead) {
  const bucket = getCrmUiState(lead).dashboardBucket

  return bucket === 'follow_up_or_close' || bucket === 'follow_up_required' || bucket === 'waiting_response'
}

export function isCrmHotLead(lead: DisplayLead) {
  if (isCrmFinalCustomerOnboarding(lead)) return false
  if (getCrmBusinessStateLabel(lead).toLowerCase().includes('client')) return false

  const priority = normalize(lead.priority || lead.status)

  return priority === 'high' || priority === 'hot'
}

export function isCrmLeadNeedingAction(lead: DisplayLead) {
  return getCrmUiState(lead).needsHumanAction
}

export function getCrmOwnerLabel(owner?: string | null) {
  const normalizedOwner = normalize(owner)

  if (!normalizedOwner || normalizedOwner === 'not assigned' || normalizedOwner === 'not_assigned') {
    return 'Non affecté'
  }

  if (normalizedOwner === 'crm manager') return 'Responsable CRM'

  return owner || 'Non affecté'
}
