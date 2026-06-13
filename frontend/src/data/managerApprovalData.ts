import type { TableRow } from '../components/common'

type ApprovalMetric = {
  label: string
  value: string
  trend?: string
}

type SelectedRequest = {
  employee: string
  team: string
  leaveType: string
  dates: string
  duration: string
  balanceBefore: string
  balanceAfter: string
  urgency: string
}

type ConflictItem = {
  label: string
  detail: string
}

type RecommendationItem = {
  title: string
  description: string
  status: TableRow['status']
}

const approvalMetrics: ApprovalMetric[] = [
  { label: 'Demandes équipe en attente', value: '6', trend: '2 urgentes' },
  { label: 'Niveau de risque sélectionné', value: 'Moyen', trend: 'Impact de couverture identifié' },
  { label: 'Solde moyen restant', value: '11 jours', trend: 'Sur l’équipe' },
]

const pendingTeamRequests: TableRow[] = [
  {
    id: 'm-1',
    process: 'Congé annuel - Sarah N.',
    owner: 'Équipe produit',
    status: 'warning',
  },
  {
    id: 'm-2',
    process: 'Télétravail - Daniel K.',
    owner: 'Operations',
    status: 'info',
  },
  {
    id: 'm-3',
    process: 'Congé maladie - Amina R.',
    owner: 'Support client',
    status: 'warning',
  },
]

const selectedRequest: SelectedRequest = {
  employee: 'Sarah N.',
  team: 'Équipe produit',
  leaveType: 'Congé annuel',
  dates: 'du 22/04 au 24/04',
  duration: '3 jours',
  balanceBefore: '18 jours',
  balanceAfter: '15 jours',
  urgency: 'Priorité standard',
}

const conflictInformation: ConflictItem[] = [
  {
    label: 'Couverture équipe',
    detail: 'Un membre de l’équipe est déjà en congé sur la même période.',
  },
  {
    label: 'Livraison critique',
    detail: 'La demande chevauche une fenêtre de livraison produit.',
  },
  {
    label: 'Conformité RH',
    detail: 'Le solde de congé est valide et la demande respecte la politique RH.',
  },
]

const aiRecommendations: RecommendationItem[] = [
  {
    title: 'Recommandation : vérifier avant approbation',
    description: 'La demande est valide, mais la couverture équipe doit être confirmée avant approbation.',
    status: 'warning',
  },
  {
    title: 'Explication : risque opérationnel modéré',
    description: 'Un chevauchement court avec une livraison augmente le besoin de coordination.',
    status: 'info',
  },
  {
    title: 'Contrôle de politique RH validé',
    description: 'Le solde de congé et la durée demandée restent dans les seuils autorisés.',
    status: 'success',
  },
]

export type { ApprovalMetric, ConflictItem, RecommendationItem, SelectedRequest }
export { aiRecommendations, approvalMetrics, conflictInformation, pendingTeamRequests, selectedRequest }
