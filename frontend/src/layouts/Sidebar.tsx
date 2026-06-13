import { NavLink, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import Icon, { type IconName } from '../components/common/Icon'
import ThemeToggle from '../components/common/ThemeToggle'

type NavItem = {
  id: string
  label: string
  path: string
  icon: IconName
  permissions: string[]
}

const primaryNav: NavItem[] = [
  {
    id: 'dashboard',
    label: 'Tableau de bord',
    path: '/dashboard',
    icon: 'dashboard',
    permissions: ['dashboard.view'],
  },
  {
    id: 'assistant',
    label: 'Assistant IA',
    path: '/assistant',
    icon: 'spark',
    permissions: ['dashboard.view'],
  },
  {
    id: 'crm-leads',
    label: 'CRM intelligent',
    path: '/crm-leads',
    icon: 'crm',
    permissions: ['crm.leads.view'],
  },
  {
    id: 'crm-tasks',
    label: 'Tâches & relances',
    path: '/crm-tasks',
    icon: 'clock',
    permissions: ['crm.tasks.view'],
  },
  {
    id: 'crm-deals',
    label: 'Pipeline deals',
    path: '/crm-deals',
    icon: 'target',
    permissions: ['crm.deals.view'],
  },
  {
    id: 'leave-requests',
    label: 'Demandes de conge',
    path: '/leave-requests',
    icon: 'leave',
    permissions: ['leave.request.create', 'leave.request.view_own'],
  },
  {
    id: 'manager-approvals',
    label: 'Validations manager',
    path: '/manager-approvals',
    icon: 'check',
    permissions: ['leave.request.approve', 'leave.request.view_all'],
  },
  {
    id: 'workflow-monitoring',
    label: 'Automatisations',
    path: '/workflow-monitoring',
    icon: 'workflow',
    permissions: ['workflow.monitor.view', 'workflow.executions.view'],
  },
  {
    id: 'ai-agents',
    label: 'Agents IA',
    path: '/ai-agents',
    icon: 'bot',
    permissions: ['agents.view'],
  },
]

const adminNav: NavItem[] = [
  {
    id: 'admin-users',
    label: 'Utilisateurs',
    path: '/admin/users',
    icon: 'users',
    permissions: ['admin.users.manage'],
  },
  {
    id: 'admin-roles',
    label: 'Roles & permissions',
    path: '/admin/roles-permissions',
    icon: 'lock',
    permissions: ['admin.roles.manage'],
  },
]

function initialsFromName(name: string) {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join('') || 'FP'
  )
}

function Sidebar() {
  const location = useLocation()
  const { hasAnyPermission, logout, user } = useAuth()

  const filteredPrimary = primaryNav.filter((item) => hasAnyPermission(item.permissions))
  const filteredAdmin = adminNav.filter((item) => hasAnyPermission(item.permissions))

  return (
    <aside className="sticky top-0 hidden h-screen w-64 shrink-0 border-r border-slate-800 bg-slate-950/70 backdrop-blur-md md:flex md:flex-col">
      <div className="flex h-[70px] shrink-0 items-center gap-3 border-b border-slate-800 px-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-linear-to-br from-emerald-500 to-emerald-600 font-bold text-white shadow-lg shadow-emerald-500/20">
          FP
        </div>
        <div className="min-w-0">
          <h1 className="truncate text-sm font-bold text-white">FlowPilot AI</h1>
          <p className="truncate text-xs text-slate-400">Centre d'operations</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-4 py-6">
        {filteredPrimary.map((item) => {
          const isActive =
            location.pathname === item.path ||
            (item.id === 'crm-leads' && location.pathname === '/crm-lead-details')

          return (
            <NavLink
              key={item.id}
              to={item.path}
              className={() =>
                `flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                  isActive
                    ? 'border border-emerald-500/30 bg-emerald-500/15 text-emerald-200 shadow-sm shadow-emerald-900/20'
                    : 'border border-transparent text-slate-400 hover:bg-slate-800/70 hover:text-slate-100'
                }`
              }
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </NavLink>
          )
        })}

        {filteredAdmin.length > 0 ? (
          <div className="mt-8 space-y-1">
            <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
              Administration
            </p>
            {filteredAdmin.map((item) => {
              const isActive = location.pathname === item.path
              return (
                <NavLink
                  key={item.id}
                  to={item.path}
                  className={() =>
                    `flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                      isActive
                        ? 'border border-emerald-500/30 bg-emerald-500/15 text-emerald-200'
                        : 'border border-transparent text-slate-400 hover:bg-slate-800/70 hover:text-slate-100'
                    }`
                  }
                >
                  <Icon name={item.icon} />
                  <span>{item.label}</span>
                </NavLink>
              )
            })}
          </div>
        ) : null}
      </nav>

      <div className="shrink-0 border-t border-slate-800 px-4 py-4">
        <div className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-linear-to-br from-emerald-400 to-sky-500 text-xs font-black text-slate-950">
            {initialsFromName(user?.full_name ?? 'FlowPilot')}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-white">{user?.full_name}</p>
            <p className="truncate text-[11px] text-slate-400">{user?.role_name}</p>
          </div>
          <ThemeToggle
            size={16}
            className="rounded-lg border border-transparent p-1.5 text-slate-500 transition hover:border-slate-700 hover:bg-slate-800 hover:text-slate-100"
          />
          <button
            type="button"
            onClick={() => void logout()}
            aria-label="Deconnexion"
            title="Deconnexion"
            className="rounded-lg border border-transparent p-1.5 text-slate-500 transition hover:border-slate-700 hover:bg-slate-800 hover:text-slate-100"
          >
            <Icon name="close" size={16} />
          </button>
        </div>
      </div>
    </aside>
  )
}

export default Sidebar
