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
  createCrmDeal,
  createCrmDealComment,
  deleteCrmDeal,
  deleteCrmDealComment,
  listCrmDealComments,
  listCrmDeals,
  listCrmTeamMembers,
  transitionCrmDealStage,
  updateCrmDeal,
} from '../services/crmTasksDealsService'
import type {
  CrmCommentItem,
  CrmDealItem,
  CrmDealStage,
  CrmTeamMember,
} from '../services/crmTasksDealsService'

const STAGES: CrmDealStage[] = [
  'discovery',
  'proposal',
  'negotiation',
  'closing',
  'won',
  'lost',
]

const STAGE_LABELS: Record<CrmDealStage, string> = {
  discovery: 'Découverte',
  proposal: 'Proposition',
  negotiation: 'Négociation',
  closing: 'Closing',
  won: 'Gagné',
  lost: 'Perdu',
}

const STAGE_TONES: Record<CrmDealStage, 'blue' | 'orange' | 'purple' | 'green' | 'red' | 'slate'> = {
  discovery: 'blue',
  proposal: 'orange',
  negotiation: 'purple',
  closing: 'orange',
  won: 'green',
  lost: 'red',
}

const ALLOWED_TRANSITIONS: Record<CrmDealStage, CrmDealStage[]> = {
  discovery: ['proposal', 'lost'],
  proposal: ['negotiation', 'lost'],
  negotiation: ['closing', 'lost'],
  closing: ['won', 'lost'],
  won: [],
  lost: [],
}

function formatCurrency(amount: string | number | null | undefined, currency: string) {
  if (amount == null) return '—'
  const num = typeof amount === 'string' ? Number(amount) : amount
  if (!Number.isFinite(num)) return '—'
  try {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: currency || 'TND',
      maximumFractionDigits: 0,
    }).format(num)
  } catch {
    return `${num} ${currency}`
  }
}

function formatDate(iso: string | null | undefined) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString('fr-FR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return iso
  }
}

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

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback
}

type CreateFormState = {
  lead_id: string
  owner_user_id: string
  title: string
  amount: string
  currency: string
  expected_close_date: string
  probability_percent: number
  notes: string
  stage: CrmDealStage
}

type EditFormState = {
  title: string
  amount: string
  currency: string
  expected_close_date: string
  probability_percent: number
  notes: string
  owner_user_id: string
}

function emptyCreateForm(userId?: string): CreateFormState {
  return {
    lead_id: '',
    owner_user_id: userId ?? '',
    title: '',
    amount: '',
    currency: 'TND',
    expected_close_date: '',
    probability_percent: 20,
    notes: '',
    stage: 'discovery',
  }
}

function dealToEditForm(deal: CrmDealItem): EditFormState {
  return {
    title: deal.title,
    amount: deal.amount != null ? String(deal.amount) : '',
    currency: deal.currency,
    expected_close_date: deal.expected_close_date
      ? deal.expected_close_date.slice(0, 10)
      : '',
    probability_percent: deal.probability_percent,
    notes: deal.notes || '',
    owner_user_id: deal.owner_user_id,
  }
}

function CRMDealsPage() {
  const { user, hasPermission } = useAuth()
  const canManage = hasPermission('crm.deals.manage')

  const [deals, setDeals] = useState<CrmDealItem[]>([])
  const [teamMembers, setTeamMembers] = useState<CrmTeamMember[]>([])
  const [leads, setLeads] = useState<CrmLeadRecord[]>([])
  const [stageFilter, setStageFilter] = useState<CrmDealStage | 'all'>('all')
  const [ownerFilter, setOwnerFilter] = useState<string>('all')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [pendingKey, setPendingKey] = useState<string | null>(null)

  const [isCreating, setIsCreating] = useState(false)
  const [createForm, setCreateForm] = useState<CreateFormState>(emptyCreateForm(user?.id))

  const [editingDeal, setEditingDeal] = useState<CrmDealItem | null>(null)
  const [editForm, setEditForm] = useState<EditFormState | null>(null)

  const [transitioningDeal, setTransitioningDeal] = useState<CrmDealItem | null>(null)
  const [transitionTarget, setTransitionTarget] = useState<CrmDealStage | null>(null)
  const [transitionReason, setTransitionReason] = useState('')

  const [commentsDealId, setCommentsDealId] = useState<string | null>(null)
  const [comments, setComments] = useState<CrmCommentItem[]>([])
  const [commentsLoading, setCommentsLoading] = useState(false)
  const [commentDraft, setCommentDraft] = useState('')

  const refresh = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [dealsResponse, teamResponse, leadsResponse] = await Promise.all([
        listCrmDeals(),
        listCrmTeamMembers().catch(() => ({ count: 0, items: [] as CrmTeamMember[] })),
        getCrmLeads().catch(() => ({ items: [] as CrmLeadRecord[], pagination: null })),
      ])
      setDeals(dealsResponse?.items ?? [])
      setTeamMembers(teamResponse?.items ?? [])
      setLeads(leadsResponse?.items ?? [])
    } catch (e) {
      setError(getErrorMessage(e, 'Impossible de charger les deals.'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (user?.id && !createForm.owner_user_id) {
      setCreateForm((prev) => ({ ...prev, owner_user_id: user.id }))
    }
  }, [user?.id, createForm.owner_user_id])

  const filtered = useMemo(() => {
    let scope = deals
    if (ownerFilter !== 'all') scope = scope.filter((d) => d.owner_user_id === ownerFilter)
    if (stageFilter !== 'all') scope = scope.filter((d) => d.stage === stageFilter)
    return scope
  }, [deals, stageFilter, ownerFilter])

  const metrics = useMemo(() => {
    const scope = ownerFilter === 'all' ? deals : deals.filter((d) => d.owner_user_id === ownerFilter)
    const open = scope.filter((d) => d.stage !== 'won' && d.stage !== 'lost')
    const won = scope.filter((d) => d.stage === 'won')
    const lost = scope.filter((d) => d.stage === 'lost')
    const totalOpenAmount = open.reduce((sum, d) => {
      const v = typeof d.amount === 'string' ? Number(d.amount) : d.amount
      return sum + (Number.isFinite(v) ? Number(v) : 0)
    }, 0)
    const weighted = open.reduce((sum, d) => {
      const v = typeof d.amount === 'string' ? Number(d.amount) : d.amount
      const amount = Number.isFinite(v) ? Number(v) : 0
      return sum + amount * (d.probability_percent / 100)
    }, 0)
    return { open: open.length, won: won.length, lost: lost.length, totalOpenAmount, weighted }
  }, [deals, ownerFilter])

  const loadComments = useCallback(async (dealId: string) => {
    setCommentsLoading(true)
    try {
      const response = await listCrmDealComments(dealId)
      setComments(response?.items ?? [])
    } catch (e) {
      setActionError(getErrorMessage(e, 'Impossible de charger les commentaires.'))
    } finally {
      setCommentsLoading(false)
    }
  }, [])

  function openComments(deal: CrmDealItem) {
    setCommentsDealId(deal.id)
    setCommentDraft('')
    setComments([])
    void loadComments(deal.id)
  }

  function closeComments() {
    setCommentsDealId(null)
    setComments([])
    setCommentDraft('')
  }

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault()
    if (!canManage) return
    setActionError(null)
    if (!createForm.lead_id.trim() || !createForm.title.trim() || !createForm.owner_user_id) {
      setActionError('Lead, titre et propriétaire sont requis.')
      return
    }
    setPendingKey('create')
    try {
      await createCrmDeal({
        lead_id: createForm.lead_id,
        owner_user_id: createForm.owner_user_id,
        title: createForm.title.trim(),
        amount: createForm.amount.trim() ? Number(createForm.amount) : null,
        currency: createForm.currency.trim() || 'TND',
        probability_percent: createForm.probability_percent,
        expected_close_date: createForm.expected_close_date
          ? new Date(createForm.expected_close_date).toISOString()
          : null,
        notes: createForm.notes.trim() || null,
        stage: createForm.stage,
      })
      setIsCreating(false)
      setCreateForm(emptyCreateForm(user?.id))
      await refresh()
    } catch (e) {
      setActionError(getErrorMessage(e, 'Création impossible.'))
    } finally {
      setPendingKey(null)
    }
  }

  async function handleEdit(event: React.FormEvent) {
    event.preventDefault()
    if (!editingDeal || !editForm || !canManage) return
    setActionError(null)
    setPendingKey(`edit_${editingDeal.id}`)
    try {
      await updateCrmDeal(editingDeal.id, {
        title: editForm.title.trim() || editingDeal.title,
        amount: editForm.amount.trim() ? Number(editForm.amount) : null,
        currency: editForm.currency.trim() || 'TND',
        probability_percent: editForm.probability_percent,
        expected_close_date: editForm.expected_close_date
          ? new Date(editForm.expected_close_date).toISOString()
          : null,
        notes: editForm.notes.trim() || null,
        owner_user_id: editForm.owner_user_id,
      })
      setEditingDeal(null)
      setEditForm(null)
      await refresh()
    } catch (e) {
      setActionError(getErrorMessage(e, 'Mise à jour impossible.'))
    } finally {
      setPendingKey(null)
    }
  }

  async function handleConfirmTransition() {
    if (!transitioningDeal || !transitionTarget || !canManage) return
    setActionError(null)
    setPendingKey(`transition_${transitioningDeal.id}`)
    try {
      await transitionCrmDealStage(transitioningDeal.id, {
        new_stage: transitionTarget,
        reason: transitionReason.trim() || null,
        trigger_workflow: true,
      })
      setTransitioningDeal(null)
      setTransitionTarget(null)
      setTransitionReason('')
      await refresh()
    } catch (e) {
      setActionError(getErrorMessage(e, 'Transition impossible.'))
    } finally {
      setPendingKey(null)
    }
  }

  async function handleDelete(dealId: string) {
    if (!canManage) return
    if (!window.confirm('Supprimer ce deal ?')) return
    setActionError(null)
    setPendingKey(`delete_${dealId}`)
    try {
      await deleteCrmDeal(dealId)
      await refresh()
    } catch (e) {
      setActionError(getErrorMessage(e, 'Suppression impossible.'))
    } finally {
      setPendingKey(null)
    }
  }

  async function handleAddComment() {
    if (!commentsDealId || !commentDraft.trim() || !canManage) return
    setActionError(null)
    setPendingKey('comment_add')
    try {
      await createCrmDealComment(commentsDealId, commentDraft.trim())
      setCommentDraft('')
      await loadComments(commentsDealId)
      const refreshed = await listCrmDeals()
      setDeals(refreshed?.items ?? [])
    } catch (e) {
      setActionError(getErrorMessage(e, 'Commentaire impossible à enregistrer.'))
    } finally {
      setPendingKey(null)
    }
  }

  async function handleDeleteComment(commentId: string) {
    if (!commentsDealId || !canManage) return
    if (!window.confirm('Supprimer ce commentaire ?')) return
    setActionError(null)
    setPendingKey(`comment_delete_${commentId}`)
    try {
      await deleteCrmDealComment(commentsDealId, commentId)
      await loadComments(commentsDealId)
      const refreshed = await listCrmDeals()
      setDeals(refreshed?.items ?? [])
    } catch (e) {
      setActionError(getErrorMessage(e, 'Suppression impossible.'))
    } finally {
      setPendingKey(null)
    }
  }

  function renderLeadLabel(deal: CrmDealItem) {
    if (deal.lead_full_name && deal.lead_company_name) {
      return `${deal.lead_full_name} · ${deal.lead_company_name}`
    }
    return deal.lead_full_name || deal.lead_company_name || deal.lead_id
  }

  function renderOwnerLabel(deal: CrmDealItem) {
    return deal.owner_full_name || deal.owner_user_id
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="CRM · Pipeline"
        title="Pipeline commercial"
        subtitle="Suivi des opportunités. Chaque changement d'étape déclenche le workflow n8n FP_CRM_07."
        actions={
          canManage ? (
            <ActionButton
              label={
                <span className="inline-flex items-center gap-1.5">
                  <Icon name="plus" size={14} /> {isCreating ? 'Annuler' : 'Nouveau deal'}
                </span>
              }
              variant={isCreating ? 'ghost' : 'primary'}
              onClick={() => setIsCreating((prev) => !prev)}
            />
          ) : undefined
        }
      />

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Deals ouverts" value={metrics.open.toString()} tone="sky" icon="target" />
        <KpiCard
          label="Pipeline ouvert"
          value={formatCurrency(metrics.totalOpenAmount, 'TND')}
          tone="amber"
          icon="trending-up"
        />
        <KpiCard
          label="Pondéré"
          value={formatCurrency(metrics.weighted, 'TND')}
          tone="violet"
          icon="activity"
        />
        <KpiCard
          label="Gagnés / Perdus"
          value={`${metrics.won} / ${metrics.lost}`}
          tone="emerald"
          icon="check"
        />
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
        <AppCard title="Créer un deal" eyebrow="Nouvelle opportunité">
          <form onSubmit={handleCreate} className="grid grid-cols-1 gap-4 px-5 py-4 lg:grid-cols-2">
            <FieldLabel label="Lead lié *">
              <select
                value={createForm.lead_id}
                onChange={(e) => setCreateForm({ ...createForm, lead_id: e.target.value })}
                className={inputClass}
              >
                <option value="">Sélectionner un lead…</option>
                {leads.map((lead) => (
                  <option key={lead.id} value={lead.id}>
                    {lead.name} · {lead.company}
                  </option>
                ))}
              </select>
            </FieldLabel>
            <FieldLabel label="Titre du deal *">
              <input
                value={createForm.title}
                onChange={(e) => setCreateForm({ ...createForm, title: e.target.value })}
                className={inputClass}
                placeholder="Northwind — AI CRM Automation"
              />
            </FieldLabel>
            <FieldLabel label="Montant">
              <input
                value={createForm.amount}
                onChange={(e) => setCreateForm({ ...createForm, amount: e.target.value })}
                type="number"
                className={inputClass}
                placeholder="15000"
              />
            </FieldLabel>
            <FieldLabel label="Devise">
              <input
                value={createForm.currency}
                onChange={(e) =>
                  setCreateForm({ ...createForm, currency: e.target.value.toUpperCase() })
                }
                className={inputClass}
                placeholder="TND"
                maxLength={6}
              />
            </FieldLabel>
            <FieldLabel label="Étape initiale">
              <select
                value={createForm.stage}
                onChange={(e) =>
                  setCreateForm({ ...createForm, stage: e.target.value as CrmDealStage })
                }
                className={inputClass}
              >
                {STAGES.map((s) => (
                  <option key={s} value={s}>
                    {STAGE_LABELS[s]}
                  </option>
                ))}
              </select>
            </FieldLabel>
            <FieldLabel label="Clôture prévue">
              <input
                type="date"
                value={createForm.expected_close_date}
                onChange={(e) =>
                  setCreateForm({ ...createForm, expected_close_date: e.target.value })
                }
                className={inputClass}
              />
            </FieldLabel>
            <FieldLabel label="Propriétaire *">
              <select
                value={createForm.owner_user_id}
                onChange={(e) =>
                  setCreateForm({ ...createForm, owner_user_id: e.target.value })
                }
                className={inputClass}
              >
                <option value="">Sélectionner…</option>
                {teamMembers.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.full_name} ({m.email})
                  </option>
                ))}
              </select>
            </FieldLabel>
            <FieldLabel label="Probabilité (%)">
              <input
                type="number"
                min={0}
                max={100}
                value={createForm.probability_percent}
                onChange={(e) =>
                  setCreateForm({
                    ...createForm,
                    probability_percent: Number(e.target.value) || 0,
                  })
                }
                className={inputClass}
              />
            </FieldLabel>
            <FieldLabel label="Notes" className="lg:col-span-2">
              <textarea
                value={createForm.notes}
                onChange={(e) => setCreateForm({ ...createForm, notes: e.target.value })}
                rows={3}
                className={inputClass}
                placeholder="Contexte interne, périmètre, dépendances…"
              />
            </FieldLabel>
            <div className="lg:col-span-2">
              <ActionButton
                label="Créer le deal"
                variant="primary"
                disabled={pendingKey === 'create'}
              />
            </div>
          </form>
        </AppCard>
      ) : null}

      <section className="flex flex-wrap items-center gap-2">
        <FilterChip
          label="Tous"
          active={stageFilter === 'all'}
          onClick={() => setStageFilter('all')}
        />
        {STAGES.map((s) => (
          <FilterChip
            key={s}
            label={STAGE_LABELS[s]}
            active={stageFilter === s}
            onClick={() => setStageFilter(s)}
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
        <LoadingState message="Chargement des deals..." />
      ) : error ? (
        <ErrorState
          message={error}
          actionLabel="Réessayer"
          onAction={() => void refresh()}
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="Aucun deal"
          description="Aucun deal ne correspond au filtre sélectionné."
          icon="target"
        />
      ) : (
        <div className="space-y-4">
          {filtered.map((deal) => {
            const allowed = ALLOWED_TRANSITIONS[deal.stage] ?? []
            const isClosed = deal.stage === 'won' || deal.stage === 'lost'
            return (
              <AppCard key={deal.id} title={deal.title} eyebrow={renderLeadLabel(deal)}>
                <div className="flex flex-col gap-4 px-5 py-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="flex-1 space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <PriorityBadge
                        label={STAGE_LABELS[deal.stage]}
                        tone={STAGE_TONES[deal.stage]}
                        size="sm"
                      />
                      {deal.previous_stage ? (
                        <span className="text-xs text-slate-500">
                          (depuis {STAGE_LABELS[deal.previous_stage as CrmDealStage] || deal.previous_stage})
                        </span>
                      ) : null}
                      <button
                        type="button"
                        onClick={() => openComments(deal)}
                        className="ml-auto inline-flex items-center gap-1.5 rounded-md border border-slate-700 px-2 py-1 text-xs text-slate-200 transition hover:border-emerald-500/40 hover:bg-emerald-500/10 hover:text-emerald-200"
                      >
                        <Icon name="mail" size={12} />
                        {deal.comments_count > 0
                          ? `${deal.comments_count} commentaire${deal.comments_count > 1 ? 's' : ''}`
                          : 'Ajouter un commentaire'}
                      </button>
                    </div>
                    <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm text-slate-300 sm:grid-cols-3">
                      <Field label="Montant" value={formatCurrency(deal.amount, deal.currency)} />
                      <Field label="Probabilité" value={`${deal.probability_percent}%`} />
                      <Field label="Clôture prévue" value={formatDate(deal.expected_close_date)} />
                      <Field label="Propriétaire" value={renderOwnerLabel(deal)} />
                      {deal.closed_at ? (
                        <Field label="Clôturé le" value={formatDate(deal.closed_at)} />
                      ) : null}
                    </div>
                    {deal.notes ? (
                      <p className="text-xs text-slate-400">{deal.notes}</p>
                    ) : null}
                    {deal.won_reason ? (
                      <StatusBadge label={`Gagné : ${deal.won_reason}`} status="success" size="sm" />
                    ) : null}
                    {deal.lost_reason ? (
                      <StatusBadge label={`Perdu : ${deal.lost_reason}`} status="danger" size="sm" />
                    ) : null}
                  </div>

                  {canManage ? (
                    <div className="w-full space-y-3 lg:w-72">
                      {!isClosed ? (
                        <>
                          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                            Faire évoluer l'étape
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {allowed.map((next) => (
                              <button
                                key={next}
                                type="button"
                                onClick={() => {
                                  setTransitioningDeal(deal)
                                  setTransitionTarget(next)
                                  setTransitionReason('')
                                }}
                                className="rounded-md border border-slate-700 px-2.5 py-1 text-xs text-slate-200 transition hover:border-emerald-500/40 hover:bg-emerald-500/10 hover:text-emerald-200"
                              >
                                → {STAGE_LABELS[next]}
                              </button>
                            ))}
                          </div>
                        </>
                      ) : (
                        <StatusBadge
                          label="Deal clôturé"
                          status={deal.stage === 'won' ? 'success' : 'neutral'}
                          size="sm"
                        />
                      )}
                      <div className="flex flex-wrap gap-2 pt-2">
                        <SmallButton
                          onClick={() => {
                            setEditingDeal(deal)
                            setEditForm(dealToEditForm(deal))
                          }}
                          tone="neutral"
                        >
                          Modifier
                        </SmallButton>
                        <SmallButton
                          onClick={() => void handleDelete(deal.id)}
                          disabled={pendingKey === `delete_${deal.id}`}
                          tone="danger"
                        >
                          Supprimer
                        </SmallButton>
                      </div>
                    </div>
                  ) : null}
                </div>
              </AppCard>
            )
          })}
        </div>
      )}

      {transitioningDeal && transitionTarget ? (
        <Modal
          title={`Passer en ${STAGE_LABELS[transitionTarget]}`}
          onClose={() => {
            setTransitioningDeal(null)
            setTransitionTarget(null)
            setTransitionReason('')
          }}
        >
          <p className="text-sm text-slate-300">
            Le deal <strong>{transitioningDeal.title}</strong> va passer de{' '}
            <strong>{STAGE_LABELS[transitioningDeal.stage]}</strong> à{' '}
            <strong>{STAGE_LABELS[transitionTarget]}</strong>. Le workflow n8n FP_CRM_07
            sera déclenché.
          </p>
          <FieldLabel
            label={
              transitionTarget === 'won'
                ? 'Raison du gagné'
                : transitionTarget === 'lost'
                  ? 'Raison du perdu'
                  : 'Raison (optionnelle)'
            }
          >
            <textarea
              value={transitionReason}
              onChange={(e) => setTransitionReason(e.target.value)}
              rows={3}
              className={inputClass}
              placeholder="Contexte pour l'équipe…"
            />
          </FieldLabel>
          <div className="flex justify-end gap-2 pt-2">
            <ActionButton
              label="Annuler"
              variant="ghost"
              onClick={() => {
                setTransitioningDeal(null)
                setTransitionTarget(null)
                setTransitionReason('')
              }}
            />
            <ActionButton
              label="Confirmer la transition"
              variant="primary"
              disabled={pendingKey === `transition_${transitioningDeal.id}`}
              onClick={handleConfirmTransition}
            />
          </div>
        </Modal>
      ) : null}

      {editingDeal && editForm ? (
        <Modal
          title={`Modifier — ${editingDeal.title}`}
          onClose={() => {
            setEditingDeal(null)
            setEditForm(null)
          }}
        >
          <form onSubmit={handleEdit} className="space-y-4">
            <FieldLabel label="Titre">
              <input
                value={editForm.title}
                onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                className={inputClass}
              />
            </FieldLabel>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FieldLabel label="Montant">
                <input
                  type="number"
                  value={editForm.amount}
                  onChange={(e) => setEditForm({ ...editForm, amount: e.target.value })}
                  className={inputClass}
                />
              </FieldLabel>
              <FieldLabel label="Devise">
                <input
                  value={editForm.currency}
                  onChange={(e) =>
                    setEditForm({ ...editForm, currency: e.target.value.toUpperCase() })
                  }
                  className={inputClass}
                />
              </FieldLabel>
              <FieldLabel label="Probabilité (%)">
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={editForm.probability_percent}
                  onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      probability_percent: Number(e.target.value) || 0,
                    })
                  }
                  className={inputClass}
                />
              </FieldLabel>
              <FieldLabel label="Clôture prévue">
                <input
                  type="date"
                  value={editForm.expected_close_date}
                  onChange={(e) =>
                    setEditForm({ ...editForm, expected_close_date: e.target.value })
                  }
                  className={inputClass}
                />
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
            <FieldLabel label="Notes">
              <textarea
                value={editForm.notes}
                onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                rows={3}
                className={inputClass}
              />
            </FieldLabel>
            <div className="flex justify-end gap-2 pt-2">
              <ActionButton
                label="Annuler"
                variant="ghost"
                onClick={() => {
                  setEditingDeal(null)
                  setEditForm(null)
                }}
              />
              <ActionButton
                label="Enregistrer"
                variant="primary"
                disabled={pendingKey === `edit_${editingDeal.id}`}
              />
            </div>
          </form>
        </Modal>
      ) : null}

      {commentsDealId ? (
        <Modal title="Commentaires du deal" onClose={closeComments}>
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
                  <p className="mt-1 whitespace-pre-wrap text-sm text-slate-100">
                    {comment.content}
                  </p>
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

type FieldProps = { label: string; value: string }
function Field({ label, value }: FieldProps) {
  return (
    <div>
      <div className="text-[11px] uppercase text-slate-500">{label}</div>
      <div className="text-slate-200">{value}</div>
    </div>
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

export default CRMDealsPage
