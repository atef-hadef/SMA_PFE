import { useEffect, useRef, useState } from 'react'
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
  roles?: string[]
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
    id: 'data-science',
    label: 'Data Science',
    path: '/data-science',
    icon: 'trending-up',
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
    id: 'activities',
    label: 'Activités récentes',
    path: '/activities',
    icon: 'clock',
    permissions: ['dashboard.view'],
    roles: ['role_admin', 'role_manager', 'role_hr'],
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
    id: 'leave-allocations',
    label: 'Allocation Congés',
    path: '/leave-allocations',
    icon: 'settings',
    permissions: ['leave.request.hr_validate'],
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

const ROLE_LABELS_FR: Record<string, string> = {
  role_admin: 'Admin',
  role_manager: 'Manager',
  role_sales: 'Commercial',
  role_hr: 'RH',
  role_employee: 'Employé',
  role_ai_supervisor: 'Superviseur IA',
}

function Sidebar() {
  const location = useLocation()
  const { hasAnyPermission, logout, user } = useAuth()

  const [menuOpen, setMenuOpen] = useState(false)
  const footerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    function handleClickOutside(event: MouseEvent) {
      if (footerRef.current && !footerRef.current.contains(event.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [menuOpen])

  const roleLabel = ROLE_LABELS_FR[user?.role_id ?? ''] ?? user?.role_name ?? ''

  const filteredPrimary = primaryNav.filter((item) =>
    item.roles ? item.roles.includes(user?.role_id ?? '') : hasAnyPermission(item.permissions),
  )
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

      <div ref={footerRef} className="relative shrink-0 border-t border-slate-800 px-4 py-4">
        {menuOpen ? (
          <div
            role="menu"
            className="absolute bottom-full left-4 right-4 mb-2 overflow-hidden rounded-lg border border-slate-800 bg-slate-900 shadow-xl shadow-slate-950/50"
          >
            <button
              type="button"
              role="menuitem"
              onClick={() => setMenuOpen(false)}
              className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm text-slate-300 transition hover:bg-slate-800"
            >
              <span aria-hidden>👤</span> Mon profil
            </button>
            <button
              type="button"
              role="menuitem"
              onClick={() => setMenuOpen(false)}
              className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm text-slate-300 transition hover:bg-slate-800"
            >
              <span aria-hidden>⚙️</span> Mes préférences
            </button>
            <div className="my-1 border-t border-slate-800" />
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setMenuOpen(false)
                void logout()
              }}
              className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm font-medium text-rose-300 transition hover:bg-rose-500/10"
            >
              <span aria-hidden>🚪</span> Déconnexion
            </button>
          </div>
        ) : null}

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            className="flex min-w-0 flex-1 items-center gap-3 rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2.5 text-left transition hover:bg-slate-800/80"
          >
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500 text-xs font-black text-white">
              {initialsFromName(user?.full_name ?? 'TAC-TIC')}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-semibold text-white">{user?.full_name}</p>
              <p className="truncate text-[11px] text-slate-400">{roleLabel}</p>
            </div>
            <Icon
              name="chevron-down"
              size={16}
              className={`shrink-0 text-slate-500 transition ${menuOpen ? 'rotate-180' : ''}`}
            />
          </button>
          <ThemeToggle
            size={16}
            className="shrink-0 rounded-lg border border-transparent p-1.5 text-slate-500 transition hover:border-slate-700 hover:bg-slate-800 hover:text-slate-100"
          />
        </div>
      </div>
    </aside>
  )
}

export default Sidebar
