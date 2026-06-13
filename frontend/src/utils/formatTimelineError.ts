/**
 * Converts a raw backend/n8n error message into a short user-friendly label.
 *
 * Used in the CRM lead timeline to hide technical noise (OAuth tokens, stack
 * traces, HTTP status codes…) from sales reps while keeping the original
 * message available to admins via the second return field.
 */

export type FormattedTimelineError = {
  /** Human-readable message safe to show to any user. */
  friendly: string
  /** True when the original looked like a technical error (so we replaced it). */
  isTechnical: boolean
  /** Original raw message, exposed only when isTechnical is true. */
  technical: string | null
}

type Rule = {
  test: RegExp
  message: string
}

// Order matters: more specific patterns first.
const RULES: Rule[] = [
  {
    test: /authorization grant|refresh token|invalid_grant|invalid_token|expired token/i,
    message: '⚠️ Connexion Gmail expirée — reconnecter le compte',
  },
  {
    test: /oauth(?:2)?[^a-z]|access token|bearer token|missing.*token/i,
    message: '⚠️ Authentification Gmail invalide — reconnecter le compte',
  },
  {
    test: /\b(?:timeout|timed out|ETIMEDOUT|deadline exceeded)\b/i,
    message: '⚠️ Délai dépassé — connexion lente',
  },
  {
    test: /\bECONN(?:REFUSED|RESET|ABORTED)\b|connection refused|connection reset/i,
    message: '⚠️ Service injoignable — réessayer dans quelques minutes',
  },
  {
    test: /\bENOTFOUND\b|getaddrinfo|name resolution|dns/i,
    message: '⚠️ Service introuvable — vérifier la configuration réseau',
  },
  {
    test: /workflow (?:failed|error|not available)|n8n (?:webhook|workflow)|webhook (?:failed|unavailable)/i,
    message: '⚠️ Échec d\'envoi — réessayer dans quelques minutes',
  },
  {
    test: /HTTP\s*4(?:01|03)\b|status\s*:?\s*4(?:01|03)\b|forbidden|unauthorized/i,
    message: '⚠️ Action non autorisée — vérifier vos droits',
  },
  {
    test: /HTTP\s*5\d\d\b|status\s*:?\s*5\d\d\b|internal server error|bad gateway|service unavailable/i,
    message: '⚠️ Service indisponible — réessayer dans quelques minutes',
  },
  {
    test: /quota|rate limit|429/i,
    message: '⚠️ Limite atteinte — patienter quelques minutes',
  },
  {
    test: /traceback \(most recent|SQLAlchemy|gaxios|node:internal\//i,
    message: '⚠️ Erreur technique — contactez le support',
  },
]

const FALLBACK_TECHNICAL_MESSAGE = '⚠️ Erreur technique — contactez le support'

const TECHNICAL_HEURISTICS: RegExp[] = [
  /\bfailed\b/i,
  /\berror\b/i,
  /\bechec\b/i,
  /\béchec\b/i,
  /\bexception\b/i,
  /\bstack\b/i,
]

/**
 * Returns true when the raw message looks technical (likely an error to hide).
 * Used so we can decide whether to apply the rewrite at all.
 */
export function looksLikeTechnicalError(raw: string | null | undefined): boolean {
  if (!raw) return false
  const trimmed = raw.trim()
  if (trimmed.length === 0) return false
  if (RULES.some((rule) => rule.test.test(trimmed))) return true
  return TECHNICAL_HEURISTICS.some((re) => re.test(trimmed))
}

export function formatTimelineError(rawMessage: string | null | undefined): FormattedTimelineError {
  const trimmed = (rawMessage || '').trim()

  if (trimmed.length === 0) {
    return { friendly: '', isTechnical: false, technical: null }
  }

  for (const rule of RULES) {
    if (rule.test.test(trimmed)) {
      return { friendly: rule.message, isTechnical: true, technical: trimmed }
    }
  }

  if (TECHNICAL_HEURISTICS.some((re) => re.test(trimmed))) {
    return { friendly: FALLBACK_TECHNICAL_MESSAGE, isTechnical: true, technical: trimmed }
  }

  // Not technical — pass through as-is.
  return { friendly: trimmed, isTechnical: false, technical: null }
}
