import type { CrmLeadRecord } from '../services/crmService'
import {
  getCrmUiState,
  isCrmConversionReady,
  isCrmFollowUpNeeded,
  isCrmHotLead,
  getCrmBusinessStage,
} from './crmDisplay'
import { formatCrmCurrency } from './crmDisplay'

type CrmMetrics = {
  totalLeads: number
  prospects: number
  customers: number
  activeCustomers: number
  inactiveCustomers: number
  vipCustomers: number
  hotLeads: number
  draftsToReview: number
  estimatedValueTotal: number
  estimatedTotalValue: number
  estimatedTotal: string
  prospectsToFollow: number
  prospectsReadyToConvert: number
  followUpProspects: number
  nextAction: string
}



function getEstimatedValue(lead: CrmLeadRecord) {
  const numeric = Number(String(lead.estimated_value ?? '').replace(/[^0-9.-]/g, ''))
  return Number.isNaN(numeric) ? 0 : numeric
}

export function computeCrmMetrics(leads: CrmLeadRecord[]): CrmMetrics {
  const totalLeads = leads.length
  const uiStates = leads.map(getCrmUiState)
  const firstAction = uiStates.find((s) => s.needsHumanAction)?.listNextActionLabel || ''

  const prospects = leads.filter((lead) => getCrmBusinessStage(lead) === 'prospect').length

  const customers = leads.filter((lead) => {
    const stage = getCrmBusinessStage(lead)
    return (
      stage === 'customer' ||
      stage === 'active_customer' ||
      stage === 'inactive_customer' ||
      stage === 'vip_customer'
    )
  }).length

  const activeCustomers = leads.filter((lead) => getCrmBusinessStage(lead) === 'active_customer').length

  const inactiveCustomers = leads.filter((lead) => getCrmBusinessStage(lead) === 'inactive_customer').length

  const vipCustomers = leads.filter((lead) => getCrmBusinessStage(lead) === 'vip_customer').length

  const hotLeads = leads.filter(isCrmHotLead).length

  const draftsToReview = uiStates.filter(
    (state) => state.dashboardBucket === 'communication_to_review' || state.dashboardBucket === 'welcome_to_review',
  ).length

  const followUpProspects = leads.filter(isCrmFollowUpNeeded).length
  const prospectsReadyToConvert = leads.filter(isCrmConversionReady).length

  const estimatedValueTotal = leads.reduce((sum, lead) => sum + getEstimatedValue(lead), 0)

  return {
    totalLeads,
    prospects,
    customers,
    activeCustomers,
    inactiveCustomers,
    vipCustomers,
    hotLeads,
    draftsToReview,
    estimatedValueTotal,
    estimatedTotal: formatCrmCurrency(estimatedValueTotal),
    estimatedTotalValue: estimatedValueTotal,
    prospectsToFollow: followUpProspects,
    prospectsReadyToConvert,
    followUpProspects,
    nextAction: firstAction || 'Aucune action requise',
  }
}

export type { CrmMetrics }
