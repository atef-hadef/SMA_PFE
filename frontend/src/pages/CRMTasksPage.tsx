import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
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
} from '../components/common'
import { useAuth } from '../auth/useAuth'
import { getCrmLeads } from '../services/crmService'
import type { CrmLeadRecord } from '../services/crmService'
import {
  createCrmTask,
  createCrmTaskComment,
  deleteCrmTask,
  deleteCrmTaskComment,
  listCrmTaskComments,
  listCrmTasks,
  listCrmTeamMembers,
  updateCrmTask,
} from '../services/crmTasksDealsService'
import type {
  CrmCommentItem,
  CrmTaskItem,
  CrmTaskPriority,
  CrmTaskStatus,
  CrmTeamMember,
} from '../services/crmTasksDealsService'

type FilterKey = 'pending' | 'overdue' | 'done' | 'cancelled' | 'all'

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: 'pending', label: 'En cours' },
  { key: 'overdue', label: 'En retard' },
  { key: 'done', label: 'Terminées' },
  { key: 'cancelled', label: 'Annulées' },
  { key: 'all', label: 'Toutes' },
]

const PRIORITY_OPTIONS: CrmTaskPriority[] = ['low', 'medium', 'high']

function formatDateTime(iso: string | null | undefined) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('fr-FR', {
      dateStyle: 'short',
      timeStyle: 'short',
    })
  } catch {
    return iso
  }
}

function toDatetimeLocalValue(iso: string | null | undefined) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const pad = (n: number) => n.toString().padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch {
    return ''
  }
}

function priorityLabel(p: CrmTaskPriority) {
  if (p === 'high') return 'Haute'
  if (p === 'low') return 'Basse'
  return 'Moyenne'
}

function statusLabel(s: CrmTaskStatus) {
  if (s === 'done') return 'Terminée'
  if (s === 'cancelled') return 'Annulée'
  return 'En cours'
}

type FormState = {
  title: string
  description: string
  due_date: string
  priority: CrmTaskPriority
  lead_id: string
  owner_user_id: string
}

function emptyForm(userId?: string): FormState {
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 16)
  return {
    title: '',
    description: '',
    due_date: tomorrow,
    priority: 'medium',
    lead_id: '',
    owner_user_id: userId ?? '',
  }
}

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback
}

function CRMTasksPage() {
  const { user, hasPermission } = useAuth()
  const canManage = hasPermission('crm.tasks.manage')

  const [tasks, setTasks] = useState<CrmTaskItem[]>([])
  const [teamMembers, setTeamMembers] = useState<CrmTeamMember[]>([])
  const [leads, setLeads] = useState<CrmLeadRecord[]>([])
  const [filter, setFilter] = useState<FilterKey>('pending')
  // Default to "Mes tâches" so the sales rep sees their own follow-ups
  // immediately on page load. Falls back to 'all' if the auth context has not
  // resolved yet — overridden by the effect below once user.id is available.
  const [ownerFilter, setOwnerFilter] = useState<string>(user?.id ?? 'all')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [pendingKey, setPendingKey] = useState<string | null>(null)

  const [isCreating, setIsCreating] = useState(false)
  const [form, setForm] = useState<FormState>(emptyForm(user?.id))
  const [editingTask, setEditingTask] = useState<CrmTaskItem | null>(null)
  const [editForm, setEditForm] = useState<FormState>(emptyForm())
  const [commentsTaskId, setCommentsTaskId] = useState<string | null>(null)
  const [comments, setComments] = useState<CrmCommentItem[]>([])
  const [commentsLoading, setCommentsLoading] = useState(false)
  const [commentDraft, setCommentDraft] = useState('')

  const refresh = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [tasksResponse, teamResponse, leadsResponse] = await Promise.all([
        listCrmTasks(),
        listCrmTeamMembers().catch(() => ({ count: 0, items: [] as CrmTeamMember[] })),
        getCrmLeads().catch(() => ({ items: [] as CrmLeadRecord[], pagination: null })),
      ])
      setTasks(tasksResponse?.items ?? [])
      setTeamMembers(teamResponse?.items ?? [])
      setLeads(leadsResponse?.items ?? [])
    } catch (e) {
      setError(getErrorMessage(e, 'Impossible de charger les tâches.'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (user?.id && !form.owner_user_id) {
      setForm((prev) => ({ ...prev, owner_user_id: user.id }))
    }
  }, [user?.id, form.owner_user_id])

  // Auto-select "Mes tâches" once auth resolves. We only override the default
  // 'all' value — if the rep has manually picked another owner, leave it alone.
  useEffect(() => {
    if (user?.id && ownerFilter === 'all') {
      setOwnerFilter(user.id)
    }
  }, [user?.id, ownerFilter])

  const filtered = useMemo(() => {
    const byOwner = ownerFilter === 'all' ? tasks : tasks.filter((t) => t.owner_user_id === ownerFilter)
    if (filter === 'all') return byOwner
    if (filter === 'overdue') return byOwner.filter((t) => t.is_overdue)
    if (filter === 'pending') return byOwner.filter((t) => t.status === 'pending')
    if (filter === 'done') return byOwner.filter((t) => t.status === 'done')
    if (filter === 'cancelled') return byOwner.filter((t) => t.status === 'cancelled')
    return byOwner
  }, [tasks, filter, ownerFilter])

  const metrics = useMemo(() => {
    const scope = ownerFilter === 'all' ? tasks : tasks.filter((t) => t.owner_user_id === ownerFilter)
    const pending = scope.filter((t) => t.status === 'pending').length
    const overdue = scope.filter((t) => t.is_overdue).length
    const done = scope.filter((t) => t.status === 'done').length
    const urgent = scope.filter((t) => t.status === 'pending' && t.priority === 'high').length
    return { pending, overdue, done, urgent }
  }, [tasks, ownerFilter])

  const loadComments = useCallback(async (taskId: string) => {
    setCommentsLoading(true)
    try {
      const response = await listCrmTaskComments(taskId)
      setComments(response?.items ?? [])
    } catch (e) {
      setActionError(getErrorMessage(e, 'Impossible de charger les commentaires.'))
    } finally {
      setCommentsLoading(false)
    }
  }, [])

  function openComments(task: CrmTaskItem) {
    setCommentsTaskId(task.id)
    setCommentDraft('')
    setComments([])
    void loadComments(task.id)
  }

  function closeComments() {
    setCommentsTaskId(null)
    setComments([])
    setCommentDraft('')
  }

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault()
    if (!canManage) return
    setActionError(null)
    if (!form.title.trim() || !form.due_date || !form.owner_user_id) {
      setActionError('Titre, échéance et propriétaire sont requis.')
      return
    }
    setPendingKey('create')
    try {
      await createCrmTask({
        title: form.title.trim(),
        description: form.description.trim() || null,
        due_date: new Date(form.due_date).toISOString(),
        priority: form.priority,
        lead_id: form.lead_id.trim() || null,
        owner_user_id: form.owner_user_id,
      })
      setIsCreating(false)
      setForm(emptyForm(user?.id))
      await refresh()
    } catch (e) {
      setActionError(getErrorMessage(e, 'Création impossible.'))
    } finally {
      setPendingKey(null)
    }
  }

  async function handleEdit(event: React.FormEvent) {
    event.preventDefault()
    if (!editingTask || !canManage) return
    setActionError(null)
    setPendingKey(`edit_${editingTask.id}`)
    try {
      await updateCrmTask(editingTask.id, {
        title: editForm.title.trim() || editingTask.title,
        description: editForm.description.trim() || null,
        due_date: editForm.due_date ? new Date(editForm.due_date).toISOString() : undefined,
        priority: editForm.priority,
        owner_user_id: editForm.owner_user_id || undefined,
      })
      setEditingTask(null)
      await refresh()
    } catch (e) {
      setActionError(getErrorMessage(e, 'Mise à jour impossible.'))
    } finally {
      setPendingKey(null)
    }
  }

  async function handleStatusChange(task: CrmTaskItem, status: CrmTaskStatus) {
    if (!canManage) return
    setActionError(null)
    setPendingKey(`status_${task.id}`)
    try {
      await updateCrmTask(task.id, { status })
      await refresh()
    } catch (e) {
      setActionError(getErrorMessage(e, 'Changement de statut impossible.'))
    } finally {
      setPendingKey(null)
    }
  }

  async function handleDelete(taskId: string) {
    if (!canManage) return
    if (!window.confirm('Supprimer cette tâche ?')) return
    setActionError(null)
    setPendingKey(`delete_${taskId}`)
    try {
      await deleteCrmTask(taskId)
      await refresh()
    } catch (e) {
      setActionError(getErrorMessage(e, 'Suppression impossible.'))
    } finally {
      setPendingKey(null)
    }
  }

  async function handleAddComment() {
    if (!commentsTaskId || !commentDraft.trim() || !canManage) return
    setActionError(null)
    setPendingKey('comment_add')
    try {
      await createCrmTaskComment(commentsTaskId, commentDraft.trim())
      setCommentDraft('')
      await loadComments(commentsTaskId)
      // Refresh task list to update comments_count column
      const refreshed = await listCrmTasks()
      setTasks(refreshed?.items ?? [])
    } catch (e) {
      setActionError(getErrorMessage(e, 'Commentaire impossible à enregistrer.'))
    } finally {
      setPendingKey(null)
    }
  }

  async function handleDeleteComment(commentId: string) {
    if (!commentsTaskId || !canManage) return
    if (!window.confirm('Supprimer ce commentaire ?')) return
    setActionError(null)
    setPendingKey(`comment_delete_${commentId}`)
    try {
      await deleteCrmTaskComment(commentsTaskId, commentId)
      await loadComments(commentsTaskId)
      const refreshed = await listCrmTasks()
      setTasks(refreshed?.items ?? [])
    } catch (e) {
      setActionError(getErrorMessage(e, 'Suppression impossible.'))
    } finally {
      setPendingKey(null)
    }
  }

  function renderOwnerLabel(task: CrmTaskItem) {
    if (task.owner_full_name) return task.owner_full_name
    return task.owner_user_id
  }

  function renderLeadLabel(task: CrmTaskItem) {
    if (!task.lead_id) return '—'
    if (task.lead_full_name && task.lead_company_name) {
      return `${task.lead_full_name} · ${task.lead_company_name}`
    }
    return task.lead_full_name || task.lead_company_name || task.lead_id
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="CRM · Tâches & Relances"
        title="Tâches & Relances CRM"
        subtitle="Vos relances commerciales — alimentées par le workflow n8n FP_CRM_06 (rappel automatique chaque matin)."
        actions={
          canManage ? (
            <ActionButton
              label={
                <span className="inline-flex items-center gap-1.5">
                  <Icon name="plus" size={14} /> {isCreating ? 'Annuler' : 'Nouvelle tâche'}
                </span>
              }
              variant={isCreating ? 'ghost' : 'primary'}
              onClick={() => setIsCreating((prev) => !prev)}
            />
          ) : undefined
        }
      />

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="En cours" value={metrics.pending.toString()} tone="sky" icon="clock" />
        <KpiCard label="En retard" value={metrics.overdue.toString()} tone="rose" icon="alert" />
        <KpiCard label="Priorité haute" value={metrics.urgent.toString()} tone="amber" icon="star" />
        <KpiCard label="Terminées" value={metrics.done.toString()} tone="emerald" icon="check" />
      </section>

      {actionError ? (
        <ErrorState
          title="Action en échec"
          message={actionError}
          actionLabel="Fermer"
          onAction={() => setActionError(null)}
        />
      ) : null}

      {isCreating ? (
        <AppCard title="Créer une tâche" eyebrow="Nouvelle entrée">
          <form onSubmit={handleCreate} className="grid grid-cols-1 gap-4 px-5 py-4 lg:grid-cols-2">
            <FieldLabel label="Titre *">
              <input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                className={inputClass}
                placeholder="Relancer Northwind sur la proposition"
              />
            </FieldLabel>
            <FieldLabel label="Échéance *">
              <input
                type="datetime-local"
                value={form.due_date}
                onChange={(e) => setForm({ ...form, due_date: e.target.value })}
                className={inputClass}
              />
            </FieldLabel>
            <FieldLabel label="Propriétaire *">
              <select
                value={form.owner_user_id}
                onChange={(e) => setForm({ ...form, owner_user_id: e.target.value })}
                className={inputClass}
              >
                <option value="">Sélectionner…</option>
                {teamMembers.map((member) => (
                  <option key={member.id} value={member.id}>
                    {member.full_name} ({member.email})
                  </option>
                ))}
              </select>
            </FieldLabel>
            <FieldLabel label="Lead lié (optionnel)">
              <select
                value={form.lead_id}
                onChange={(e) => setForm({ ...form, lead_id: e.target.value })}
                className={inputClass}
              >
                <option value="">Aucun lead</option>
                {leads.map((lead) => (
                  <option key={lead.id} value={lead.id}>
                    {lead.name} · {lead.company}
                  </option>
                ))}
              </select>
            </FieldLabel>
            <FieldLabel label="Priorité">
              <select
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: e.target.value as CrmTaskPriority })}
                className={inputClass}
              >
                {PRIORITY_OPTIONS.map((p) => (
                  <option key={p} value={p}>
                    {priorityLabel(p)}
                  </option>
                ))}
              </select>
            </FieldLabel>
            <FieldLabel label="Description" className="lg:col-span-2">
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                rows={3}
                className={inputClass}
                placeholder="Contexte de la relance, points à aborder…"
              />
            </FieldLabel>
            <div className="lg:col-span-2">
              <ActionButton
                label="Créer la tâche"
                variant="primary"
                disabled={pendingKey === 'create'}
              />
            </div>
          </form>
        </AppCard>
      ) : null}

      <section className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <FilterChip
            key={f.key}
            label={f.label}
            active={filter === f.key}
            onClick={() => setFilter(f.key)}
          />
        ))}
        <div className="ml-auto">
          <select
            value={ownerFilter}
            onChange={(e) => setOwnerFilter(e.target.value)}
            className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-100"
          >
            <option value="all">Tous les propriétaires</option>
            {teamMembers.map((m) => (
              <option key={m.id} value={m.id}>
                {m.full_name}
              </option>
            ))}
          </select>
        </div>
      </section>

      {isLoading ? (
        <LoadingState message="Chargement des tâches..." />
      ) : error ? (
        <ErrorState
          message={error}
          actionLabel="Réessayer"
          onAction={() => void refresh()}
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="Aucune tâche"
          description="Aucune tâche ne correspond au filtre sélectionné."
          icon="check"
        />
      ) : (
        <AppCard title="Liste des tâches" eyebrow="Pipeline relances">
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-800 text-xs uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="px-5 py-3">Tâche</th>
                  <th className="px-3 py-3">Lead</th>
                  <th className="px-3 py-3">Échéance</th>
                  <th className="px-3 py-3">Priorité</th>
                  <th className="px-3 py-3">Statut</th>
                  <th className="px-3 py-3">Propriétaire</th>
                  <th className="px-3 py-3">Commentaires</th>
                  {canManage ? <th className="px-5 py-3 text-right">Actions</th> : null}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {filtered.map((task) => (
                  <tr key={task.id} className="text-slate-200">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{task.title}</span>
                        {task.task_type === 'follow_up' ? (
                          <span
                            className="inline-flex items-center gap-1 rounded-full border border-violet-500/40 bg-violet-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-200"
                            title="Tâche générée automatiquement après envoi d'email — aucune réponse reçue."
                          >
                            🤖 Auto
                          </span>
                        ) : null}
                      </div>
                      {task.description ? (
                        <div className="mt-1 text-xs text-slate-400">{task.description}</div>
                      ) : null}
                    </td>
                    <td className="px-3 py-3 text-xs text-slate-300">{renderLeadLabel(task)}</td>
                    <td className="px-3 py-3 text-xs">
                      <div>{formatDateTime(task.due_date)}</div>
                      {task.is_overdue ? (
                        <div className="mt-1 text-[11px] font-semibold text-rose-400">
                          En retard
                        </div>
                      ) : task.status === 'pending' ? (
                        <div className="mt-1 text-[11px] text-slate-500">
                          J{task.days_until_due >= 0 ? `+${task.days_until_due}` : task.days_until_due}
                        </div>
                      ) : null}
                    </td>
                    <td className="px-3 py-3">
                      <PriorityBadge
                        label={priorityLabel(task.priority)}
                        tone={
                          task.priority === 'high'
                            ? 'red'
                            : task.priority === 'low'
                              ? 'slate'
                              : 'orange'
                        }
                        size="sm"
                      />
                    </td>
                    <td className="px-3 py-3">
                      <StatusBadge
                        label={statusLabel(task.status)}
                        status={
                          task.status === 'done'
                            ? 'success'
                            : task.status === 'cancelled'
                              ? 'neutral'
                              : task.is_overdue
                                ? 'danger'
                                : 'info'
                        }
                        size="sm"
                      />
                      {task.reminder_sent_at ? (
                        <div className="mt-1 text-[11px] text-slate-500">
                          Relance le {formatDateTime(task.reminder_sent_at)}
                        </div>
                      ) : null}
                    </td>
                    <td className="px-3 py-3 text-xs text-slate-300">{renderOwnerLabel(task)}</td>
                    <td className="px-3 py-3">
                      <button
                        type="button"
                        onClick={() => openComments(task)}
                        className="inline-flex items-center gap-1.5 rounded-md border border-slate-700 px-2 py-1 text-xs text-slate-200 transition hover:border-emerald-500/40 hover:bg-emerald-500/10 hover:text-emerald-200"
                      >
                        <Icon name="mail" size={12} />
                        {task.comments_count > 0 ? `${task.comments_count} commentaire${task.comments_count > 1 ? 's' : ''}` : 'Ajouter'}
                      </button>
                    </td>
                    {canManage ? (
                      <td className="px-5 py-3 text-right">
                        <div className="flex flex-wrap justify-end gap-2">
                          {task.status === 'pending' ? (
                            <>
                              <SmallButton
                                onClick={() => void handleStatusChange(task, 'done')}
                                disabled={pendingKey === `status_${task.id}`}
                                tone="success"
                              >
                                Terminer
                              </SmallButton>
                              <SmallButton
                                onClick={() => void handleStatusChange(task, 'cancelled')}
                                disabled={pendingKey === `status_${task.id}`}
                                tone="neutral"
                              >
                                Annuler
                              </SmallButton>
                            </>
                          ) : (
                            <SmallButton
                              onClick={() => void handleStatusChange(task, 'pending')}
                              disabled={pendingKey === `status_${task.id}`}
                              tone="neutral"
                            >
                              Réouvrir
                            </SmallButton>
                          )}
                          <SmallButton
                            onClick={() => {
                              setEditingTask(task)
                              setEditForm({
                                title: task.title,
                                description: task.description || '',
                                due_date: toDatetimeLocalValue(task.due_date),
                                priority: task.priority,
                                lead_id: task.lead_id || '',
                                owner_user_id: task.owner_user_id,
                              })
                            }}
                            tone="neutral"
                          >
                            Modifier
                          </SmallButton>
                          <SmallButton
                            onClick={() => void handleDelete(task.id)}
                            disabled={pendingKey === `delete_${task.id}`}
                            tone="danger"
                          >
                            Supprimer
                          </SmallButton>
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </AppCard>
      )}

      {editingTask ? (
        <Modal title={`Modifier — ${editingTask.title}`} onClose={() => setEditingTask(null)}>
          <form onSubmit={handleEdit} className="space-y-4">
            <FieldLabel label="Titre">
              <input
                value={editForm.title}
                onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                className={inputClass}
              />
            </FieldLabel>
            <FieldLabel label="Description">
              <textarea
                value={editForm.description}
                onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                rows={3}
                className={inputClass}
              />
            </FieldLabel>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FieldLabel label="Échéance">
                <input
                  type="datetime-local"
                  value={editForm.due_date}
                  onChange={(e) => setEditForm({ ...editForm, due_date: e.target.value })}
                  className={inputClass}
                />
              </FieldLabel>
              <FieldLabel label="Priorité">
                <select
                  value={editForm.priority}
                  onChange={(e) =>
                    setEditForm({ ...editForm, priority: e.target.value as CrmTaskPriority })
                  }
                  className={inputClass}
                >
                  {PRIORITY_OPTIONS.map((p) => (
                    <option key={p} value={p}>
                      {priorityLabel(p)}
                    </option>
                  ))}
                </select>
              </FieldLabel>
            </div>
            <FieldLabel label="Propriétaire">
              <select
                value={editForm.owner_user_id}
                onChange={(e) => setEditForm({ ...editForm, owner_user_id: e.target.value })}
                className={inputClass}
              >
                {teamMembers.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.full_name} ({m.email})
                  </option>
                ))}
              </select>
            </FieldLabel>
            <div className="flex justify-end gap-2 pt-2">
              <ActionButton label="Annuler" variant="ghost" onClick={() => setEditingTask(null)} />
              <ActionButton
                label="Enregistrer"
                variant="primary"
                disabled={pendingKey === `edit_${editingTask.id}`}
              />
            </div>
          </form>
        </Modal>
      ) : null}

      {commentsTaskId ? (
        <Modal title="Commentaires de la tâche" onClose={closeComments}>
          {commentsLoading ? (
            <LoadingState message="Chargement…" />
          ) : comments.length === 0 ? (
            <p className="text-sm italic text-slate-400">Aucun commentaire pour le moment.</p>
          ) : (
            <ul className="space-y-2">
              {comments.map((comment) => (
                <li
                  key={comment.id}
                  className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-semibold text-slate-200">
                      {comment.author_full_name}
                    </p>
                    <span className="text-[11px] text-slate-500">
                      {formatDateTime(comment.created_at)}
                    </span>
                  </div>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-slate-100">{comment.content}</p>
                  {canManage && comment.author_user_id === user?.id ? (
                    <button
                      type="button"
                      onClick={() => void handleDeleteComment(comment.id)}
                      className="mt-2 text-[11px] text-rose-300 hover:text-rose-200"
                    >
                      Supprimer
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          {canManage ? (
            <div className="space-y-2 border-t border-slate-800 pt-3">
              <textarea
                value={commentDraft}
                onChange={(e) => setCommentDraft(e.target.value)}
                rows={3}
                placeholder="Ajouter un commentaire…"
                className={inputClass}
              />
              <div className="flex justify-end">
                <ActionButton
                  label="Publier"
                  variant="primary"
                  disabled={!commentDraft.trim() || pendingKey === 'comment_add'}
                  onClick={handleAddComment}
                />
              </div>
            </div>
          ) : null}
        </Modal>
      ) : null}
    </div>
  )
}

const inputClass =
  'w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100'

type FieldLabelProps = { label: string; children: ReactNode; className?: string }
function FieldLabel({ label, children, className = '' }: FieldLabelProps) {
  return (
    <label className={`space-y-1 ${className}`}>
      <span className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
        {label}
      </span>
      {children}
    </label>
  )
}

type FilterChipProps = { label: string; active: boolean; onClick: () => void }
function FilterChip({ label, active, onClick }: FilterChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md border px-3 py-1.5 text-xs transition ${
        active
          ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-200'
          : 'border-slate-700 text-slate-400 hover:bg-slate-800/70 hover:text-slate-100'
      }`}
    >
      {label}
    </button>
  )
}

type SmallButtonProps = {
  children: ReactNode
  onClick: () => void
  disabled?: boolean
  tone: 'success' | 'danger' | 'neutral'
}
function SmallButton({ children, onClick, disabled, tone }: SmallButtonProps) {
  const tones = {
    success: 'border-emerald-500/40 text-emerald-200 hover:bg-emerald-500/15',
    danger: 'border-rose-500/30 text-rose-300 hover:bg-rose-500/15',
    neutral: 'border-slate-700 text-slate-300 hover:bg-slate-800',
  }
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`rounded-md border px-2 py-1 text-xs transition disabled:opacity-50 ${tones[tone]}`}
    >
      {children}
    </button>
  )
}

type ModalProps = { title: string; onClose: () => void; children: ReactNode }
function Modal({ title, onClose, children }: ModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4">
      <div className="w-full max-w-2xl rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
          <h2 className="text-base font-semibold text-white">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
            aria-label="Fermer"
          >
            <Icon name="close" size={16} />
          </button>
        </div>
        <div className="space-y-4 px-5 py-4">{children}</div>
      </div>
    </div>
  )
}

export default CRMTasksPage
