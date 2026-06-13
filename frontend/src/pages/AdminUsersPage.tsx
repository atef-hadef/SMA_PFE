import { useEffect, useMemo, useState } from 'react'
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
  TechnicalDetailsPanel,
  type BadgeTone,
} from '../components/common'
import { adminUsers as fallbackUsers } from '../data/adminUsersData'
import { deactivateUser, getUsers } from '../services/adminService'
import type { AdminUserRecord } from '../services/adminService'
import { useAuth } from '../auth/useAuth'

type UserRow = {
  id: string
  name: string
  email: string
  role: string
  department: string
  status: 'active' | 'inactive'
  statusLabel: string
  lastLogin: string
  isAdmin: boolean
  isManager: boolean
}

const DEACTIVATE_REASON = 'Désactivation administrée via FlowPilot AI'

function formatDateTime(date: string | null) {
  if (!date) return 'Jamais'
  const parsed = new Date(date)
  if (Number.isNaN(parsed.getTime())) return 'Jamais'
  return new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(parsed)
}

function getRoleTone(role: string): BadgeTone {
  const lower = role.toLowerCase()
  if (lower.includes('admin')) return 'red'
  if (lower.includes('manager')) return 'orange'
  if (lower.includes('crm')) return 'purple'
  if (lower.includes('hr')) return 'blue'
  return 'slate'
}

function mapUserToRow(user: AdminUserRecord): UserRow {
  const status: UserRow['status'] = user.status === 'active' ? 'active' : 'inactive'
  const lower = user.role.toLowerCase()
  return {
    id: user.id,
    name: user.name,
    email: user.email,
    role: user.role,
    department: user.department,
    status,
    statusLabel: status === 'active' ? 'Actif' : 'Inactif',
    lastLogin: formatDateTime(user.last_login),
    isAdmin: lower.includes('admin'),
    isManager: lower.includes('manager'),
  }
}

function mapFallbackUser(user: (typeof fallbackUsers)[number]): UserRow {
  const status: UserRow['status'] = user.status === 'success' ? 'active' : 'inactive'
  const lower = user.role.toLowerCase()
  return {
    id: user.id,
    name: user.name,
    email: user.email,
    role: user.role,
    department: user.department,
    status,
    statusLabel: status === 'active' ? 'Actif' : 'Inactif',
    lastLogin: user.lastLogin,
    isAdmin: lower === 'admin',
    isManager: lower === 'manager',
  }
}

function AdminUsersPage() {
  const { hasPermission } = useAuth()
  const canManageUsers = hasPermission('admin.users.manage')
  const [rows, setRows] = useState<UserRow[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isUsingFallback, setIsUsingFallback] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState('')
  const [actionError, setActionError] = useState('')
  const [search, setSearch] = useState('')

  useEffect(() => {
    let isMounted = true
    async function loadUsers() {
      setIsLoading(true)
      try {
        const response = await getUsers()
        if (!isMounted) return
        const mapped = response.items.map(mapUserToRow)
        setRows(mapped)
        setSelectedId(mapped[0]?.id ?? null)
        setIsUsingFallback(false)
      } catch {
        if (!isMounted) return
        const mapped = fallbackUsers.map(mapFallbackUser)
        setRows(mapped)
        setSelectedId(mapped[0]?.id ?? null)
        setIsUsingFallback(true)
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }
    void loadUsers()
    return () => {
      isMounted = false
    }
  }, [])

  const filtered = useMemo(() => {
    const normalized = search.trim().toLowerCase()
    if (!normalized) return rows
    return rows.filter((row) =>
      [row.name, row.email, row.role, row.department].join(' ').toLowerCase().includes(normalized),
    )
  }, [rows, search])

  const summary = useMemo(
    () => ({
      total: rows.length,
      active: rows.filter((row) => row.status === 'active').length,
      inactive: rows.filter((row) => row.status === 'inactive').length,
      adminsAndManagers: rows.filter((row) => row.isAdmin || row.isManager).length,
    }),
    [rows],
  )

  const selected = rows.find((row) => row.id === selectedId) ?? rows[0]

  async function handleDeactivate(userId: string) {
    setActionMessage('')
    setActionError('')
    if (!canManageUsers) {
      setActionError('Votre role ne permet pas de gerer les utilisateurs.')
      return
    }
    if (isUsingFallback) {
      setActionError('La désactivation est désactivée en mode hors ligne.')
      return
    }
    try {
      await deactivateUser(userId, DEACTIVATE_REASON)
      setActionMessage('Utilisateur désactivé avec succès.')
      setRows((current) =>
        current.map((row) =>
          row.id === userId ? { ...row, status: 'inactive', statusLabel: 'Inactif' } : row,
        ),
      )
    } catch {
      setActionError('La désactivation n’a pas pu être effectuée.')
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Administration"
        title="Utilisateurs"
        subtitle="Gestion centralisée des comptes, rôles et états d’accès à la plateforme FlowPilot AI."
        statusLabel={`${summary.total} utilisateurs`}
        statusTone="info"
      />

      {isLoading ? <LoadingState message="Chargement des utilisateurs..." /> : null}
      {isUsingFallback ? (
        <ErrorState
          tone="warning"
          title="Données en direct indisponibles"
          message="Affichage d’exemples hors ligne. Les actions administratives sont désactivées."
        />
      ) : null}
      {actionMessage ? (
        <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm font-medium text-emerald-200">
          {actionMessage}
        </div>
      ) : null}
      {actionError ? (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm font-medium text-rose-200">
          {actionError}
        </div>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Total utilisateurs"
          value={String(summary.total)}
          tone="emerald"
          icon="users"
          helper="Comptes enregistrés"
        />
        <KpiCard
          label="Actifs"
          value={String(summary.active)}
          tone="emerald"
          icon="check"
          helper="Connexion récente"
        />
        <KpiCard
          label="Inactifs"
          value={String(summary.inactive)}
          tone="slate"
          icon="clock"
          helper="Sans activité"
        />
        <KpiCard
          label="Admins & managers"
          value={String(summary.adminsAndManagers)}
          tone="amber"
          icon="star"
          helper="Accès privilégiés"
        />
      </section>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <AppCard
          eyebrow="Annuaire"
          title="Liste des utilisateurs"
          description="Consultez les rôles, départements et activités récentes."
          actions={
            <div className="relative">
              <Icon
                name="search"
                size={14}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
              />
              <input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Rechercher..."
                className="w-56 rounded-lg border border-slate-800 bg-slate-950/80 py-2 pl-8 pr-3 text-xs text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/20"
              />
            </div>
          }
          bodyClassName=""
        >
          <div className="overflow-x-auto">
            {filtered.length === 0 ? (
              <div className="p-6">
                <EmptyState
                  icon="users"
                  title={rows.length === 0 ? 'Aucun utilisateur configuré' : 'Aucun utilisateur'}
                  description={
                    rows.length === 0
                      ? 'Ajoutez ou synchronisez les utilisateurs pour gérer les accès à la plateforme.'
                      : 'Aucun compte ne correspond à la recherche.'
                  }
                />
              </div>
            ) : (
              <table className="min-w-full text-left text-sm">
                <thead className="bg-slate-950/70 text-[11px] uppercase tracking-[0.14em] text-slate-400">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Nom</th>
                    <th className="px-5 py-3 font-semibold">Email</th>
                    <th className="px-5 py-3 font-semibold">Rôle</th>
                    <th className="px-5 py-3 font-semibold">Département</th>
                    <th className="px-5 py-3 font-semibold">Statut</th>
                    <th className="px-5 py-3 font-semibold">Dernière activité</th>
                    <th className="px-5 py-3 font-semibold text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {filtered.map((user) => (
                    <tr
                      key={user.id}
                      className={`cursor-pointer transition hover:bg-slate-900/70 ${
                        user.id === selected?.id ? 'bg-slate-900/60' : ''
                      }`}
                      onClick={() => setSelectedId(user.id)}
                    >
                      <td className="px-5 py-4">
                        <p className="font-semibold text-white">{user.name}</p>
                      </td>
                      <td className="px-5 py-4 text-slate-300">{user.email}</td>
                      <td className="px-5 py-4">
                        <PriorityBadge label={user.role} tone={getRoleTone(user.role)} size="sm" />
                      </td>
                      <td className="px-5 py-4 text-slate-300">{user.department}</td>
                      <td className="px-5 py-4">
                        <StatusBadge
                          label={user.statusLabel}
                          status={user.status === 'active' ? 'success' : 'neutral'}
                          size="sm"
                        />
                      </td>
                      <td className="px-5 py-4 text-slate-300">{user.lastLogin}</td>
                      <td className="px-5 py-4 text-right">
                        <ActionButton
                          label="Désactiver"
                          variant="secondary"
                          size="sm"
                          onClick={() => void handleDeactivate(user.id)}
                          disabled={user.status === 'inactive' || isUsingFallback || !canManageUsers}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </AppCard>

        <AppCard
          eyebrow="Fiche"
          title={selected?.name ?? 'Aucun utilisateur'}
          description={selected?.email ?? 'Sélectionnez un utilisateur pour afficher sa fiche.'}
          actions={
            selected ? (
              <StatusBadge
                label={selected.statusLabel}
                status={selected.status === 'active' ? 'success' : 'neutral'}
              />
            ) : null
          }
        >
          {selected ? (
            <div className="space-y-4">
              <dl className="grid gap-3">
                <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                  <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Rôle</dt>
                  <dd className="mt-1 font-semibold text-white">{selected.role}</dd>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                  <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                    Département
                  </dt>
                  <dd className="mt-1 font-semibold text-white">{selected.department}</dd>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                  <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                    Dernière activité
                  </dt>
                  <dd className="mt-1 font-semibold text-white">{selected.lastLogin}</dd>
                </div>
              </dl>

              <ActionButton
                label="Désactiver le compte"
                variant="danger"
                onClick={() => void handleDeactivate(selected.id)}
                disabled={isUsingFallback || selected.status === 'inactive' || !canManageUsers}
              />

              <TechnicalDetailsPanel title="Traçabilité">
                <dl className="space-y-1 text-sm text-slate-300">
                  <div>
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                      Identifiant
                    </dt>
                    <dd className="break-words">{selected.id}</dd>
                  </div>
                  <div>
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Email</dt>
                    <dd className="break-words">{selected.email}</dd>
                  </div>
                </dl>
              </TechnicalDetailsPanel>
            </div>
          ) : null}
        </AppCard>
      </div>
    </div>
  )
}

export default AdminUsersPage
