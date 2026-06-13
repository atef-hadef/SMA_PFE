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
import { rolesList as fallbackRoles } from '../data/rolesPermissionsData'
import { getRoles, updateRolePermissions } from '../services/adminService'
import type { AdminRoleRecord } from '../services/adminService'
import { useAuth } from '../auth/useAuth'

type PermissionAction =
  | 'view'
  | 'viewOwn'
  | 'viewAll'
  | 'create'
  | 'update'
  | 'interact'
  | 'generate'
  | 'review'
  | 'approve'
  | 'reject'
  | 'send'
  | 'convert'
  | 'retry'
  | 'run'
  | 'manage'
  | 'hrValidate'

type PermissionGroupDef = {
  module: string
  category:
    | 'General'
    | 'CRM'
    | 'Conges'
    | 'Cong\u00E9s'
    | 'Cong\u00C3\u00A9s'
    | 'CongÃ©s'
    | 'Automatisations'
    | 'Agents IA'
    | 'Administration'
  permissions: Partial<Record<PermissionAction, string>>
}

type PermissionRow = {
  module: string
  category: PermissionGroupDef['category']
  permissions: Partial<Record<PermissionAction, string>>
  enabled: Partial<Record<PermissionAction, boolean>>
}

type RoleOption = {
  id: string
  name: string
  description: string
  users: number
  department: string
  tone: BadgeTone
}

const PERMISSION_ACTIONS: PermissionAction[] = [
  'view',
  'viewOwn',
  'viewAll',
  'create',
  'update',
  'interact',
  'generate',
  'review',
  'approve',
  'reject',
  'send',
  'convert',
  'retry',
  'run',
  'manage',
  'hrValidate',
]

const PERMISSION_ACTION_LABELS: Record<PermissionAction, string> = {
  view: 'Consulter',
  viewOwn: 'Voir soi',
  viewAll: 'Voir tout',
  create: 'Soumettre',
  update: 'Modifier',
  interact: 'Interaction',
  generate: 'Generer',
  review: 'Relire',
  approve: 'Valider',
  reject: 'Refuser',
  send: 'Envoyer',
  convert: 'Convertir',
  retry: 'Relancer',
  run: 'Executer',
  hrValidate: 'Valider RH',
  manage: 'Gérer',
}

const PERMISSION_CODE_LABELS: Record<string, string> = {
  'dashboard.view': 'Voir le tableau de bord',
  'label.admin.users.manage': 'Gerer utilisateurs',
  'label.admin.roles.manage': 'Gerer roles et permissions',
  'crm.leads.view': 'Consulter les leads CRM',
  'crm.leads.create': 'Creer des leads CRM',
  'crm.leads.update': 'Modifier les leads CRM',
  'crm.interactions.create': 'Ajouter des interactions CRM',
  'crm.drafts.generate': 'Generer des brouillons CRM',
  'crm.drafts.review': 'Relire les brouillons CRM',
  'crm.email.approve': 'Approuver les emails CRM',
  'crm.email.send': 'Envoyer les emails CRM',
  'crm.customer.convert': 'Convertir en client',
  'crm.vip.manage': 'Gerer les clients VIP',
  'leave.request.create': 'Creer une demande de conge',
  'leave.request.view_own': 'Voir ses demandes',
  'leave.request.view_all': 'Voir toutes les demandes',
  'leave.request.approve': 'Approuver les demandes',
  'leave.request.reject': 'Refuser les demandes',
  'leave.request.hr_validate': 'Validation RH',
  'workflow.monitor.view': 'Voir le monitoring workflow',
  'workflow.executions.view': 'Voir les executions workflow',
  'workflow.executions.retry': 'Relancer les executions workflow',
  'agents.view': 'Voir les agents IA',
  'label.agents.run': 'Executer les agents IA',
  'crm.read': 'Consulter CRM',
  'crm.create': 'Créer une fiche CRM',
  'crm.update': 'Modifier CRM',
  'crm.approve_draft': 'Valider brouillons CRM',
  'crm.manage': 'Administrer CRM',
  'leave.read': 'Consulter congés',
  'leave.create': 'Soumettre demande congé',
  'leave.submit': 'Soumettre demande congé',
  'leave.approve': 'Approuver congés',
  'leave.reject': 'Refuser congés',
  'workflow.read': 'Consulter automatisations',
  'workflows.read': 'Consulter automatisations',
  'workflow.retry': 'Relancer automatisations',
  'workflows.retry': 'Relancer automatisations',
  'agents.read': 'Consulter agents IA',
  'agents.run': 'Exécuter agents IA',
  'admin.users.read': 'Consulter utilisateurs',
  'admin.users.manage': 'Gérer utilisateurs',
  'admin.users': 'Gérer utilisateurs',
  'admin.roles.read': 'Consulter rôles',
  'admin.roles.manage': 'Gérer rôles',
  'admin.roles': 'Gérer rôles',
}

function getPermissionLabel(code: string) {
  return PERMISSION_CODE_LABELS[code] ?? 'Autorisation métier'
}

const PERMISSION_MATRIX: PermissionGroupDef[] = [
  {
    module: 'Tableau de bord',
    category: 'General',
    permissions: { view: 'dashboard.view' },
  },
  {
    module: 'Leads & prospects',
    category: 'CRM',
    permissions: { view: 'crm.leads.view', create: 'crm.leads.create', update: 'crm.leads.update' },
  },
  {
    module: 'Interactions CRM',
    category: 'CRM',
    permissions: { interact: 'crm.interactions.create' },
  },
  {
    module: 'Brouillons de communication',
    category: 'CRM',
    permissions: {
      generate: 'crm.drafts.generate',
      review: 'crm.drafts.review',
      approve: 'crm.email.approve',
      send: 'crm.email.send',
    },
  },
  {
    module: 'Conversion client',
    category: 'CRM',
    permissions: { convert: 'crm.customer.convert' },
  },
  {
    module: 'Clients VIP',
    category: 'CRM',
    permissions: { manage: 'crm.vip.manage' },
  },
  {
    module: 'Demandes de congé',
    category: 'Congés',
    permissions: {
      create: 'leave.request.create',
      viewOwn: 'leave.request.view_own',
      viewAll: 'leave.request.view_all',
    },
  },
  {
    module: 'Validations manager',
    category: 'Congés',
    permissions: {
      approve: 'leave.request.approve',
      reject: 'leave.request.reject',
      hrValidate: 'leave.request.hr_validate',
    },
  },
  {
    module: 'Supervision des automatisations',
    category: 'Automatisations',
    permissions: { view: 'workflow.monitor.view' },
  },
  {
    module: 'Executions workflow',
    category: 'Automatisations',
    permissions: { view: 'workflow.executions.view', retry: 'workflow.executions.retry' },
  },
  {
    module: 'Centre des agents',
    category: 'Agents IA',
    permissions: { view: 'agents.view', run: 'agents.run' },
  },
  {
    module: 'Utilisateurs',
    category: 'Administration',
    permissions: { manage: 'admin.users.manage' },
  },
  {
    module: 'Rôles & permissions',
    category: 'Administration',
    permissions: { manage: 'admin.roles.manage' },
  },
]

function deriveDepartment(role: AdminRoleRecord) {
  const lower = role.name.toLowerCase()
  if (lower.includes('crm') || lower.includes('sales')) return 'Ventes'
  if (lower.includes('hr') || lower.includes('rh')) return 'RH'
  if (lower.includes('admin')) return 'IT / Admin'
  if (lower.includes('manager')) return 'Management'
  return 'Opérations'
}

function deriveTone(role: AdminRoleRecord): BadgeTone {
  const lower = role.name.toLowerCase()
  if (lower.includes('admin')) return 'red'
  if (lower.includes('manager')) return 'orange'
  if (lower.includes('sales') || lower.includes('crm')) return 'purple'
  if (lower.includes('hr') || lower.includes('rh')) return 'blue'
  if (lower.includes('employee') || lower.includes('staff')) return 'green'
  return 'slate'
}

function buildRoleOption(role: AdminRoleRecord): RoleOption {
  return {
    id: role.id,
    name: role.name,
    description: role.description || 'Rôle métier FlowPilot AI',
    users: role.user_count,
    department: deriveDepartment(role),
    tone: deriveTone(role),
  }
}

function buildFallbackRoles(): { role: AdminRoleRecord; option: RoleOption }[] {
  return fallbackRoles.map((role) => {
    const adminRole: AdminRoleRecord = {
      id: role.id,
      name: role.name,
      description: `Rôle ${role.name}`,
      user_count: Number(role.users) || 0,
      permissions: [
        'dashboard.view',
        'crm.leads.view',
        'crm.leads.create',
        'leave.request.view_own',
        'workflow.monitor.view',
        'agents.view',
      ],
    }
    return { role: adminRole, option: buildRoleOption(adminRole) }
  })
}

function buildMatrix(permissions: string[]): PermissionRow[] {
  const set = new Set(permissions)
  return PERMISSION_MATRIX.map((row) => ({
    module: row.module,
    category: row.category,
    permissions: row.permissions,
    enabled: PERMISSION_ACTIONS.reduce<Partial<Record<PermissionAction, boolean>>>(
      (acc, action) => {
        const code = row.permissions[action]
        if (code) acc[action] = set.has(code)
        return acc
      },
      {},
    ),
  }))
}

function serializeMatrix(matrix: PermissionRow[]): string[] {
  return matrix.flatMap((row) =>
    PERMISSION_ACTIONS.flatMap((action) => {
      const code = row.permissions[action]
      return code && row.enabled[action] ? [code] : []
    }),
  )
}

function RolesPermissionsPage() {
  const { hasPermission } = useAuth()
  const canManageRoles = hasPermission('admin.roles.manage')
  const [backendRoles, setBackendRoles] = useState<AdminRoleRecord[]>([])
  const [roleOptions, setRoleOptions] = useState<RoleOption[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [matrices, setMatrices] = useState<Record<string, PermissionRow[]>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isUsingFallback, setIsUsingFallback] = useState(false)
  const [saveMessage, setSaveMessage] = useState('')
  const [saveError, setSaveError] = useState('')

  useEffect(() => {
    let isMounted = true
    async function loadRoles() {
      setIsLoading(true)
      try {
        const response = await getRoles()
        if (!isMounted) return
        setBackendRoles(response.items)
        setRoleOptions(response.items.map(buildRoleOption))
        setSelectedId(response.items[0]?.id ?? null)
        setIsUsingFallback(false)
      } catch {
        if (!isMounted) return
        const { roles, options } = buildFallbackRoles().reduce(
          (acc, entry) => {
            acc.roles.push(entry.role)
            acc.options.push(entry.option)
            return acc
          },
          { roles: [] as AdminRoleRecord[], options: [] as RoleOption[] },
        )
        setBackendRoles(roles)
        setRoleOptions(options)
        setSelectedId(options[0]?.id ?? null)
        setIsUsingFallback(true)
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }
    void loadRoles()
    return () => {
      isMounted = false
    }
  }, [])

  const selectedBackend =
    backendRoles.find((role) => role.id === selectedId) ?? backendRoles[0] ?? null
  const selectedOption = roleOptions.find((option) => option.id === selectedId) ?? roleOptions[0]

  const matrix = useMemo(() => {
    if (!selectedId) return [] as PermissionRow[]
    if (matrices[selectedId]) return matrices[selectedId]
    return buildMatrix(selectedBackend?.permissions ?? [])
  }, [matrices, selectedBackend, selectedId])

  const matrixByCategory = useMemo(() => {
    const byCategory = new Map<PermissionRow['category'], PermissionRow[]>()
    matrix.forEach((row) => {
      if (!byCategory.has(row.category)) byCategory.set(row.category, [])
      byCategory.get(row.category)!.push(row)
    })
    return byCategory
  }, [matrix])

  const visibleMatrixByCategory = useMemo(() => {
    const visible = new Map<PermissionRow['category'], PermissionRow[]>()
    matrixByCategory.forEach((rows, category) => {
      if (category === 'Automatisations' || category === 'Agents IA') return
      visible.set(category, rows)
    })
    return visible
  }, [matrixByCategory])

  const advancedPermissionRows = useMemo(
    () => [
      ...(matrixByCategory.get('Automatisations') ?? []),
      ...(matrixByCategory.get('Agents IA') ?? []),
    ],
    [matrixByCategory],
  )

  const summary = useMemo(
    () => ({
      roles: roleOptions.length,
      totalUsers: roleOptions.reduce((sum, option) => sum + option.users, 0),
      adminRoles: roleOptions.filter((option) => option.name.toLowerCase().includes('admin')).length,
      restrictedPermissions: PERMISSION_MATRIX.filter((row) => row.category === 'Administration').length,
    }),
    [roleOptions],
  )

  function togglePermission(module: string, action: PermissionAction) {
    if (!selectedId) return
    setSaveMessage('')
    setSaveError('')
    setMatrices((current) => {
      const currentMatrix = current[selectedId] ?? buildMatrix(selectedBackend?.permissions ?? [])
      return {
        ...current,
        [selectedId]: currentMatrix.map((row) =>
          row.module === module
            ? {
                ...row,
                enabled: {
                  ...row.enabled,
                  [action]: !row.enabled[action],
                },
              }
            : row,
        ),
      }
    })
  }

  async function handleSave() {
    if (!selectedId) return
    setSaveMessage('')
    setSaveError('')
    if (!canManageRoles) {
      setSaveError('Votre role ne permet pas de gerer les roles.')
      return
    }
    if (isUsingFallback) {
      setSaveError('La sauvegarde est désactivée en mode hors ligne.')
      return
    }
    setIsSaving(true)
    try {
      const permissions = serializeMatrix(
        matrices[selectedId] ?? buildMatrix(selectedBackend?.permissions ?? []),
      )
      await updateRolePermissions(selectedId, permissions)
      setSaveMessage('Permissions mises à jour avec succès.')
    } catch {
      setSaveError('Les permissions n’ont pas pu être sauvegardées.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Administration"
        title="Rôles & permissions"
        subtitle="Matrice d’autorisations par module métier. Activez ou désactivez chaque permission pour un rôle donné."
        statusLabel={`${summary.roles} rôles`}
        statusTone="info"
      />

      {isLoading ? <LoadingState message="Chargement des rôles..." /> : null}
      {isUsingFallback ? (
        <ErrorState
          tone="warning"
          title="Données des rôles indisponibles"
          message="Affichage d’exemples hors ligne. La sauvegarde est désactivée."
        />
      ) : null}
      {saveMessage ? (
        <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm font-medium text-emerald-200">
          {saveMessage}
        </div>
      ) : null}
      {saveError ? (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm font-medium text-rose-200">
          {saveError}
        </div>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Rôles définis"
          value={String(summary.roles)}
          tone="emerald"
          icon="lock"
          helper="Dans la plateforme"
        />
        <KpiCard
          label="Utilisateurs rattachés"
          value={String(summary.totalUsers)}
          tone="sky"
          icon="users"
          helper="Comptes totaux"
        />
        <KpiCard
          label="Rôles admin"
          value={String(summary.adminRoles)}
          tone="rose"
          icon="star"
          helper="Privilèges étendus"
        />
        <KpiCard
          label="Modules critiques"
          value={String(summary.restrictedPermissions)}
          tone="amber"
          icon="alert"
          helper="Revue IT recommandée"
        />
      </section>

      <div className="grid gap-5 lg:grid-cols-[320px_minmax(0,1fr)]">
        <AppCard
          eyebrow="Rôles"
          title="Sélection"
          description="Cliquez sur un rôle pour éditer sa matrice."
        >
          {roleOptions.length === 0 ? (
            <EmptyState
              icon="lock"
              title="Aucun rôle disponible"
              description="Les rôles apparaîtront ici dès leur configuration."
            />
          ) : (
            <ul className="space-y-2">
              {roleOptions.map((option) => {
                const isActive = option.id === selectedId
                return (
                  <li key={option.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(option.id)}
                      className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                        isActive
                          ? 'border-emerald-500/40 bg-emerald-500/10'
                          : 'border-slate-800 bg-slate-950/60 hover:border-slate-700 hover:bg-slate-900/70'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-bold text-white">{option.name}</p>
                          <p className="truncate text-xs text-slate-400">{option.department}</p>
                        </div>
                        <PriorityBadge label={`${option.users}`} tone={option.tone} size="sm" />
                      </div>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </AppCard>

        <AppCard
          eyebrow="Matrice des permissions"
          title={selectedOption?.name ?? 'Aucun rôle sélectionné'}
          description={selectedOption?.description ?? 'Choisissez un rôle pour éditer ses permissions.'}
          actions={
            <ActionButton
              label={isSaving ? 'Sauvegarde...' : 'Enregistrer les modifications'}
              onClick={() => void handleSave()}
              disabled={isSaving || isUsingFallback || !selectedId || !canManageRoles}
            />
          }
        >
          {matrix.length === 0 ? (
            <EmptyState
              icon="lock"
              title="Aucune permission à afficher"
              description="Sélectionnez un rôle pour configurer ses accès."
            />
          ) : (
            <div className="space-y-5">
              {Array.from(visibleMatrixByCategory.entries()).map(([category, rows]) => (
                <section key={category}>
                  <div className="mb-3 flex items-center justify-between">
                    <h3 className="text-sm font-bold text-white">{category}</h3>
                    <StatusBadge label={`${rows.length} modules`} status="neutral" size="sm" />
                  </div>
                  <div className="overflow-x-auto rounded-xl border border-slate-800">
                    <table className="min-w-full text-left text-sm">
                      <thead className="bg-slate-950/70 text-[11px] uppercase tracking-[0.14em] text-slate-400">
                        <tr>
                          <th className="px-4 py-3 font-semibold">Module</th>
                          {PERMISSION_ACTIONS.map((action) => (
                            <th key={action} className="px-4 py-3 font-semibold text-center">
                              {PERMISSION_ACTION_LABELS[action]}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800">
                        {rows.map((row) => (
                          <tr key={row.module} className="transition hover:bg-slate-900/60">
                            <td className="px-4 py-3">
                              <p className="font-semibold text-slate-100">{row.module}</p>
                              <p className="mt-1 text-xs text-slate-500">
                                {Object.values(row.permissions).map(getPermissionLabel).join(' · ')}
                              </p>
                            </td>
                            {PERMISSION_ACTIONS.map((action) => {
                              const code = row.permissions[action]
                              const enabled = Boolean(row.enabled[action])
                              if (!code) {
                                return (
                                  <td key={action} className="px-4 py-3 text-center text-slate-600">
                                    -
                                  </td>
                                )
                              }
                              return (
                                <td key={action} className="px-4 py-3 text-center">
                                  <label className="inline-flex cursor-pointer items-center">
                                    <input
                                      type="checkbox"
                                      className="sr-only"
                                      checked={enabled}
                                      onChange={() => togglePermission(row.module, action)}
                                    />
                                    <span
                                      title={getPermissionLabel(code)}
                                      className={`flex h-5 w-5 items-center justify-center rounded-md border transition ${
                                        enabled
                                          ? 'border-emerald-500/50 bg-emerald-500/20 text-emerald-300'
                                          : 'border-slate-700 bg-slate-950 text-slate-600'
                                      }`}
                                    >
                                      {enabled ? <Icon name="check" size={12} /> : null}
                                    </span>
                                  </label>
                                </td>
                              )
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              ))}

              {advancedPermissionRows.length > 0 ? (
                <TechnicalDetailsPanel title="Permissions avancées">
                  <div className="space-y-3">
                    {advancedPermissionRows.map((row) => {
                      const activeLabels = PERMISSION_ACTIONS.flatMap((action) => {
                        const code = row.permissions[action]
                        return code && row.enabled[action] ? [getPermissionLabel(code)] : []
                      })
                      return (
                        <div key={row.module} className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                          <p className="text-sm font-semibold text-white">{row.module}</p>
                          <p className="mt-1 text-xs text-slate-400">
                            {activeLabels.length > 0
                              ? activeLabels.join(' · ')
                              : 'Aucune permission avancée active'}
                          </p>
                        </div>
                      )
                    })}
                  </div>
                </TechnicalDetailsPanel>
              ) : null}

              <TechnicalDetailsPanel title="Traçabilité">
                <dl className="space-y-2 text-sm text-slate-300">
                  <div>
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                      Identifiant du rôle
                    </dt>
                    <dd className="break-words">{selectedBackend?.id ?? '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                      Permissions actives
                    </dt>
                    <dd>
                      {matrix.length > 0
                        ? serializeMatrix(matrix).map(getPermissionLabel).join(', ') || 'Aucune'
                        : 'Aucune'}
                    </dd>
                  </div>
                </dl>
              </TechnicalDetailsPanel>
            </div>
          )}
        </AppCard>
      </div>
    </div>
  )
}

export default RolesPermissionsPage
