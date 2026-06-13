import type { TableRow } from '../components/common'

type LeaveCard = {
  label: string
  value: string
  trend?: string
}

type LeaveInsight = {
  title: string
  description: string
  status: TableRow['status']
}

type LeaveRequestFormField = {
  label: string
  placeholder: string
}

const leaveBalanceCards: LeaveCard[] = [
  { label: 'Solde congé annuel', value: '18 jours', trend: '6 utilisés cette année' },
  { label: 'Solde congé maladie', value: '7 jours', trend: '2 utilisés cette année' },
  { label: 'Jours de télétravail disponibles', value: '12 jours', trend: 'Conforme à la politique RH' },
  { label: 'Demandes en attente', value: '3', trend: 'En attente de validation' },
]

const aiLeaveInsights: LeaveInsight[] = [
  {
    title: 'Recommandation : approuver la courte absence',
    description: 'La demande respecte le solde disponible et ne chevauche pas une période critique.',
    status: 'success',
  },
  {
    title: 'Explication : risque de couverture modéré',
    description: 'Deux membres de l’équipe sont déjà absents la semaine prochaine, la couverture doit être vérifiée.',
    status: 'warning',
  },
  {
    title: 'Contrôle de politique RH validé',
    description: 'Le type de congé sélectionné respecte les règles RH actuelles.',
    status: 'info',
  },
]

const myLeaveRequests: TableRow[] = [
  {
    id: 'lr-1',
    process: 'Congé annuel - du 22/04 au 24/04',
    owner: 'En attente du manager',
    status: 'warning',
  },
  {
    id: 'lr-2',
    process: 'Congé maladie - 10/03',
    owner: 'Approuvé par les RH',
    status: 'success',
  },
  {
    id: 'lr-3',
    process: 'Télétravail - 28/03',
    owner: 'Refusé par le manager',
    status: 'danger',
  },
]

const leaveRequestFormFields: LeaveRequestFormField[] = [
  { label: 'Type de congé', placeholder: 'Sélectionner un type de congé' },
  { label: 'Date de début', placeholder: 'Choisir la date de début' },
  { label: 'Date de fin', placeholder: 'Choisir la date de fin' },
]

export type { LeaveCard, LeaveInsight, LeaveRequestFormField }
export { aiLeaveInsights, leaveBalanceCards, leaveRequestFormFields, myLeaveRequests }
