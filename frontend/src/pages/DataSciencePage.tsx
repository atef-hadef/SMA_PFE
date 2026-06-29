import { useEffect, useMemo, useState } from 'react'
import { AppCard, Icon, KpiCard, LoadingState, PageHeader } from '../components/common'
import { getMLAnalytics, type MLAnalytics } from '../services/mlService'

const MLFLOW_UI_URL = 'http://localhost:5000'

function formatAuc(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  return value.toFixed(3)
}

function categoryBadge(category: string) {
  const map: Record<string, string> = {
    hot: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    warm: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    cold: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  }
  const labels: Record<string, string> = { hot: 'Chaud', warm: 'Tiède', cold: 'Froid' }
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold ${
        map[category] ?? 'bg-slate-700/40 text-slate-300 border-slate-600/60'
      }`}
    >
      {labels[category] ?? category}
    </span>
  )
}

function runStatusBadge(status: string) {
  if (status === 'production') {
    return (
      <span className="inline-flex items-center rounded-md border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 text-[11px] font-semibold text-emerald-300">
        ⭐ Production
      </span>
    )
  }
  if (status === 'baseline') {
    return (
      <span className="inline-flex items-center rounded-md border border-slate-600/60 bg-slate-700/40 px-2 py-0.5 text-[11px] font-semibold text-slate-300">
        📊 Baseline
      </span>
    )
  }
  return (
    <span className="inline-flex items-center rounded-md border border-sky-500/30 bg-sky-500/15 px-2 py-0.5 text-[11px] font-semibold text-sky-300">
      Candidat
    </span>
  )
}

function DataSciencePage() {
  const [analytics, setAnalytics] = useState<MLAnalytics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getMLAnalytics()
      .then((data) => {
        if (!cancelled) {
          setAnalytics(data)
          setError(null)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Erreur de chargement.')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const totalScored = useMemo(() => {
    if (!analytics) return 0
    return Object.values(analytics.score_distribution).reduce((a, b) => a + b, 0)
  }, [analytics])

  const sortedRuns = useMemo(() => {
    if (!analytics) return []
    return [...analytics.mlflow_runs].sort((a, b) => b.auc_roc - a.auc_roc)
  }, [analytics])

  const bestRunName = sortedRuns.find((r) => r.status === 'production')?.model_name

  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Module Data Science"
          title="Lead Scoring Machine Learning"
          subtitle="Scoring prédictif, comparaison avec le LLM et explicabilité SHAP."
        />
        <LoadingState message="Chargement des analytics ML…" fullHeight />
      </div>
    )
  }

  if (error || !analytics) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Module Data Science"
          title="Lead Scoring Machine Learning"
          subtitle="Scoring prédictif, comparaison avec le LLM et explicabilité SHAP."
        />
        <AppCard tone="warning">
          <div className="flex flex-col items-start gap-4">
            <div>
              <p className="text-base font-semibold text-amber-200">
                🚀 Module Data Science en cours d'initialisation.
              </p>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                Lancez l'entraînement depuis les notebooks Jupyter, puis exécutez{' '}
                <code className="rounded bg-slate-800 px-1.5 py-0.5 text-emerald-300">
                  python ml/src/models/train.py
                </code>{' '}
                pour générer le modèle et les métriques.
              </p>
              {error ? (
                <p className="mt-2 text-xs text-slate-500">Détail : {error}</p>
              ) : null}
            </div>
            <a
              href={MLFLOW_UI_URL}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm font-semibold text-emerald-200 transition hover:bg-emerald-500/20"
            >
              📓 Ouvrir les notebooks / MLflow
            </a>
          </div>
        </AppCard>
      </div>
    )
  }

  const { model_info, feature_importance, recent_scores } = analytics

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Module Data Science"
        title="Lead Scoring Machine Learning"
        subtitle="Scoring prédictif, comparaison avec le LLM et explicabilité SHAP."
        statusLabel={`Modèle ${model_info.version} en production`}
        statusTone="success"
      />

      {/* SECTION 1 — KPIs */}
      <div className="grid gap-4 md:grid-cols-3">
        <KpiCard
          label="Modèle ML en production"
          value={model_info.algorithm}
          helper={`AUC-ROC : ${formatAuc(model_info.auc_roc)} · ${model_info.n_features} features`}
          trend="En production"
          trendDirection="up"
          tone="emerald"
          icon="trending-up"
        />
        <KpiCard
          label="vs LLM Baseline"
          value={model_info.improvement_vs_llm}
          helper="Gain d'AUC face au scoring LLM existant"
          trend="ML supérieur"
          trendDirection="up"
          tone="violet"
          icon="spark"
        />
        <KpiCard
          label="Leads scorés (récents)"
          value={totalScored}
          helper="Scorés par le modèle ML"
          trend={`${analytics.score_distribution.hot ?? 0} chauds`}
          trendDirection="up"
          tone="sky"
          icon="crm"
        />
      </div>

      {/* SECTION 2 — Comparaison ML vs LLM */}
      <AppCard
        eyebrow="Benchmark"
        title="Comparaison ML vs LLM"
        description="Performance des modèles entraînés, mesurée sur le jeu de test (20%)."
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
                <th className="px-3 py-2 font-semibold">Modèle</th>
                <th className="px-3 py-2 font-semibold">AUC-ROC</th>
                <th className="px-3 py-2 font-semibold">F1-Score</th>
                <th className="px-3 py-2 font-semibold">P@k</th>
                <th className="px-3 py-2 font-semibold">Statut</th>
              </tr>
            </thead>
            <tbody>
              {sortedRuns.map((run) => {
                const isBest = run.model_name === bestRunName
                const isLlm = run.status === 'baseline'
                return (
                  <tr
                    key={run.model_name}
                    className={`border-b border-slate-800/60 ${
                      isBest
                        ? 'bg-emerald-500/10'
                        : isLlm
                          ? 'bg-slate-800/30'
                          : ''
                    }`}
                  >
                    <td className="px-3 py-2.5 font-medium text-slate-100">
                      {run.model_name}
                    </td>
                    <td
                      className={`px-3 py-2.5 font-semibold ${
                        isBest ? 'text-emerald-300' : 'text-slate-300'
                      }`}
                    >
                      {formatAuc(run.auc_roc)}
                    </td>
                    <td className="px-3 py-2.5 text-slate-300">{formatAuc(run.f1_score)}</td>
                    <td className="px-3 py-2.5 text-slate-300">
                      {formatAuc(run.precision_at_k)}
                    </td>
                    <td className="px-3 py-2.5">{runStatusBadge(run.status)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </AppCard>

      {/* SECTION 3 — Feature importance SHAP */}
      <AppCard
        eyebrow="Explicabilité"
        title="Facteurs les plus influents sur la conversion"
        description="Importance globale calculée avec SHAP sur le modèle de production."
      >
        <div className="space-y-3">
          {feature_importance.map((feat) => {
            const pct = Math.round(feat.importance * 100)
            return (
              <div key={feat.feature} className="flex items-center gap-3">
                <div className="w-52 shrink-0 truncate text-sm text-slate-200" title={feat.label}>
                  <Icon name="trending-up" size={13} className="mr-1.5 inline text-emerald-400" />
                  {feat.label}
                </div>
                <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-800">
                  <div
                    className="h-full rounded-full bg-linear-to-r from-emerald-500 to-emerald-400"
                    style={{ width: `${Math.max(2, Math.min(100, feat.importance * 100 * 6))}%` }}
                  />
                </div>
                <div className="w-12 shrink-0 text-right text-xs font-semibold text-emerald-300">
                  {pct}%
                </div>
              </div>
            )
          })}
        </div>
      </AppCard>

      {/* SECTION 4 — Leads récemment scorés */}
      <AppCard
        eyebrow="Temps réel"
        title="Leads récemment scorés"
        description="Comparaison du score ML calibré et du score LLM existant."
      >
        {recent_scores.length === 0 ? (
          <p className="text-sm text-slate-400">
            Aucun lead à scorer pour le moment (base de données vide ou indisponible).
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-3 py-2 font-semibold">Prospect</th>
                  <th className="px-3 py-2 font-semibold">Score ML</th>
                  <th className="px-3 py-2 font-semibold">Catégorie</th>
                  <th className="px-3 py-2 font-semibold">Score LLM</th>
                  <th className="px-3 py-2 font-semibold">Delta</th>
                </tr>
              </thead>
              <tbody>
                {recent_scores.map((lead) => {
                  const delta = lead.delta ?? 0
                  const deltaUp = delta >= 0
                  return (
                    <tr key={lead.lead_id} className="border-b border-slate-800/60">
                      <td className="px-3 py-2.5 font-medium text-slate-100">
                        {lead.lead_name}
                      </td>
                      <td className="px-3 py-2.5 font-bold text-white">{lead.ml_score}</td>
                      <td className="px-3 py-2.5">{categoryBadge(lead.ml_category)}</td>
                      <td className="px-3 py-2.5 text-slate-400">{lead.llm_score ?? '—'}</td>
                      <td className="px-3 py-2.5">
                        {lead.delta === null ? (
                          <span className="text-slate-500">—</span>
                        ) : (
                          <span
                            className={`inline-flex items-center gap-1 font-semibold ${
                              deltaUp ? 'text-emerald-400' : 'text-rose-400'
                            }`}
                          >
                            <Icon
                              name={deltaUp ? 'trending-up' : 'trending-down'}
                              size={14}
                            />
                            {deltaUp ? '+' : ''}
                            {delta}
                          </span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </AppCard>

      {/* SECTION 5 — MLflow */}
      <AppCard
        eyebrow="MLOps"
        title="MLflow Experiment Tracking"
        description="Tous les runs de l'expériment « TAC-TIC Lead Scoring »."
        actions={
          <a
            href={MLFLOW_UI_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-200 transition hover:bg-emerald-500/20"
          >
            Voir l'interface MLflow complète →
          </a>
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
                <th className="px-3 py-2 font-semibold">Run</th>
                <th className="px-3 py-2 font-semibold">AUC</th>
                <th className="px-3 py-2 font-semibold">F1</th>
                <th className="px-3 py-2 font-semibold">P@k</th>
                <th className="px-3 py-2 font-semibold">Statut</th>
              </tr>
            </thead>
            <tbody>
              {sortedRuns.map((run) => (
                <tr key={`${run.model_name}-${run.run_id}`} className="border-b border-slate-800/60">
                  <td className="px-3 py-2.5 font-medium text-slate-100">{run.model_name}</td>
                  <td className="px-3 py-2.5 text-slate-300">{formatAuc(run.auc_roc)}</td>
                  <td className="px-3 py-2.5 text-slate-300">{formatAuc(run.f1_score)}</td>
                  <td className="px-3 py-2.5 text-slate-300">{formatAuc(run.precision_at_k)}</td>
                  <td className="px-3 py-2.5">{runStatusBadge(run.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </AppCard>
    </div>
  )
}

export default DataSciencePage
