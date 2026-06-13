import { useLocation } from 'react-router-dom'
import Icon from '../components/common/Icon'
import ThemeToggle from '../components/common/ThemeToggle'

const pageTitles: Record<string, { title: string; subtitle: string }> = {
  '/dashboard': {
    title: 'Centre de commande',
    subtitle: 'Vue consolidée CRM et demandes de congé',
  },
  '/crm-leads': {
    title: 'CRM intelligent',
    subtitle: 'Qualification IA, scoring commercial et supervision humaine',
  },
  '/crm-lead-details': {
    title: 'Fiche client',
    subtitle: 'Workspace CRM complet pour un lead ou un client',
  },
  '/leave-requests': {
    title: 'Demandes de congé',
    subtitle: 'Soumission, analyse IA et synchronisation SIRH',
  },
  '/manager-approvals': {
    title: 'Validations manager',
    subtitle: 'Inbox des décisions RH assistées par l’IA',
  },
  '/workflow-monitoring': {
    title: 'Automatisations',
    subtitle: 'Supervision des processus métier automatisés',
  },
  '/ai-agents': {
    title: 'Agents IA',
    subtitle: 'Assistants métier FlowPilot AI',
  },
  '/admin/users': {
    title: 'Utilisateurs',
    subtitle: 'Gestion des comptes et accès à la plateforme',
  },
  '/admin/roles-permissions': {
    title: 'Rôles & permissions',
    subtitle: 'Matrice des autorisations par module métier',
  },
}

function TopHeader() {
  const { pathname } = useLocation()
  // The assistant is a full-screen chat surface — it renders its own slim header.
  if (pathname === '/assistant') return null
  const meta = pageTitles[pathname] ?? pageTitles['/dashboard']

  return (
    <header className="sticky top-0 z-30 flex h-[70px] items-center justify-between border-b border-slate-800 bg-slate-950/70 px-6 backdrop-blur-md md:px-8">
      <div className="min-w-0">
        <h2 className="truncate text-base font-bold text-white md:text-lg">{meta.title}</h2>
        <p className="mt-0.5 truncate text-xs text-slate-400 md:text-sm">{meta.subtitle}</p>
      </div>

      <div className="flex items-center gap-2 md:gap-3">
        <ThemeToggle />
        <button
          type="button"
          aria-label="Notifications"
          className="relative rounded-lg border border-transparent p-2 text-slate-400 transition hover:border-slate-700 hover:bg-slate-800/70 hover:text-slate-100"
        >
          <Icon name="bell" size={20} />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-rose-500" />
        </button>
        <button
          type="button"
          aria-label="Paramètres"
          className="rounded-lg border border-transparent p-2 text-slate-400 transition hover:border-slate-700 hover:bg-slate-800/70 hover:text-slate-100"
        >
          <Icon name="settings" size={20} />
        </button>
      </div>
    </header>
  )
}

export default TopHeader
