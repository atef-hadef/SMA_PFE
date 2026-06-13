type LeaveStatus =
  | 'pending'
  | 'manager_review_required'
  | 'approved'
  | 'rejected'
  | 'cancelled'
  | 'odoo_sync_failed'
  | string

type Recommendation = 'approve' | 'reject' | 'review' | string
type RiskLevel = 'low' | 'medium' | 'high' | string

type BadgeTone = 'green' | 'orange' | 'red' | 'blue' | 'slate'

const statusLabels: Record<string, string> = {
  pending: "En attente d'analyse",
  manager_review_required: 'Validation manager requise',
  approved: 'Approuvée',
  rejected: 'Refusée',
  cancelled: 'Annulée',
  odoo_sync_failed: 'Erreur de synchronisation Odoo',
}

const recommendationLabels: Record<string, string> = {
  approve: 'Approbation recommandée',
  review: 'Vérification manager recommandée',
  reject: 'Refus recommandé',
  unknown: 'Analyse indisponible',
}

const riskLabels: Record<string, string> = {
  low: 'Faible',
  medium: 'Moyen',
  high: 'Élevé',
  unknown: 'Non évalué',
}

function formatLeaveStatus(status: LeaveStatus) {
  return statusLabels[status] ?? statusLabels.pending
}

function getLeaveStatusTone(status: LeaveStatus): BadgeTone {
  if (status === 'approved') return 'green'
  if (status === 'rejected' || status === 'odoo_sync_failed') return 'red'
  if (status === 'manager_review_required') return 'orange'
  if (status === 'cancelled') return 'slate'
  return 'blue'
}

function formatRecommendation(recommendation: Recommendation | null | undefined) {
  return recommendationLabels[recommendation ?? 'unknown'] ?? recommendationLabels.unknown
}

function formatRiskLevel(riskLevel: RiskLevel | null | undefined) {
  return riskLabels[riskLevel ?? 'unknown'] ?? riskLabels.unknown
}

function getRiskTone(riskLevel: RiskLevel | null | undefined, conflict = false): BadgeTone {
  if (riskLevel === 'high') return 'red'
  if (riskLevel === 'medium' || conflict) return 'orange'
  if (riskLevel === 'low') return 'green'
  return 'slate'
}

function getRecommendationTone(recommendation: Recommendation | null | undefined): BadgeTone {
  if (recommendation === 'approve') return 'green'
  if (recommendation === 'reject') return 'red'
  if (recommendation === 'review') return 'orange'
  return 'slate'
}

function formatFrenchDate(value: string) {
  return new Intl.DateTimeFormat('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(new Date(`${value}T00:00:00`))
}

function formatLeavePeriod(startDate: string, endDate: string) {
  return `du ${formatFrenchDate(startDate)} au ${formatFrenchDate(endDate)}`
}

export type { BadgeTone, LeaveStatus, Recommendation, RiskLevel }
export {
  formatFrenchDate,
  formatLeavePeriod,
  formatLeaveStatus,
  formatRecommendation,
  formatRiskLevel,
  getLeaveStatusTone,
  getRecommendationTone,
  getRiskTone,
}
