import { get } from './apiClient'

export type ModelInfo = {
  model_name: string
  version: string
  trained_at: string
  algorithm: string
  auc_roc: number
  f1_score: number
  n_features: number
  n_training_samples: number
  improvement_vs_llm: string
  mlflow_run_id: string | null
}

export type FeatureImportance = {
  feature: string
  label: string
  importance: number
  rank: number
}

export type RecentScore = {
  lead_id: string
  lead_name: string
  ml_score: number
  ml_category: 'hot' | 'warm' | 'cold'
  llm_score: number | null
  delta: number | null
  scored_at: string
}

export type MLflowRun = {
  run_id: string
  model_name: string
  auc_roc: number
  f1_score: number
  precision_at_k: number
  status: string
  started_at: string
}

export type ModelComparisonEntry = {
  auc_roc: number | null
  f1_score: number | null
  precision_at_20: number | null
  lift_at_20: number | null
}

export type MLAnalytics = {
  score_distribution: Record<string, number>
  model_comparison: Record<string, ModelComparisonEntry>
  feature_importance: FeatureImportance[]
  recent_scores: RecentScore[]
  mlflow_runs: MLflowRun[]
  model_info: ModelInfo
}

function getMLAnalytics() {
  return get<MLAnalytics>('/ml/analytics')
}

function getMLflowRuns() {
  return get<MLflowRun[]>('/ml/mlflow-runs')
}

function getModelInfo() {
  return get<ModelInfo>('/ml/model-info')
}

export { getMLAnalytics, getMLflowRuns, getModelInfo }
