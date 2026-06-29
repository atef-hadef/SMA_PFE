import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { getDefaultPathForPermissions } from '../auth/permissions'
import { useAuth } from '../auth/useAuth'
import { Icon } from '../components/common'

type LocationState = { from?: { pathname?: string } }

const LAST_EMAIL_KEY = 'tactic_last_email'
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

const KEY_POINTS = [
  'Automatisation IA des relances',
  'Scoring intelligent des prospects',
  'Workflows complets de bout en bout',
]

function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { isAuthenticated, isLoading, login, user } = useAuth()

  const [email, setEmail] = useState(() => localStorage.getItem(LAST_EMAIL_KEY) ?? '')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [welcomeName, setWelcomeName] = useState('')

  const emailIsValid = useMemo(() => EMAIL_REGEX.test(email.trim()), [email])
  const showEmailError = email.length > 0 && !emailIsValid

  useEffect(() => {
    if (!isLoading && isAuthenticated && user) {
      navigate(getDefaultPathForPermissions(user.permissions), { replace: true })
    }
  }, [isAuthenticated, isLoading, navigate, user])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErrorMessage('')

    if (!emailIsValid) {
      setErrorMessage('Veuillez saisir une adresse email valide.')
      return
    }

    setIsSubmitting(true)
    try {
      const loggedInUser = await login(email.trim(), password)
      localStorage.setItem(LAST_EMAIL_KEY, email.trim())

      const firstName = (loggedInUser.full_name || '').split(' ')[0] || ''
      setWelcomeName(firstName)

      const state = location.state as LocationState | null
      const fallbackPath = getDefaultPathForPermissions(loggedInUser.permissions)
      const target = state?.from?.pathname ?? fallbackPath
      // Laisse le toast de bienvenue s'afficher avant la redirection.
      setTimeout(() => navigate(target, { replace: true }), 900)
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : 'Connexion impossible. Vérifiez vos identifiants.',
      )
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-white text-slate-900 lg:grid lg:grid-cols-2">
      {/* Toast de bienvenue */}
      {welcomeName ? (
        <div className="fixed left-1/2 top-6 z-50 -translate-x-1/2 rounded-xl border border-emerald-300 bg-emerald-50 px-5 py-3 text-sm font-semibold text-emerald-800 shadow-lg">
          Bienvenue {welcomeName} 👋
        </div>
      ) : null}

      {/* Colonne gauche — branding */}
      <section className="relative hidden flex-col justify-between bg-gradient-to-br from-[#0f172a] to-[#1e293b] p-12 text-white lg:flex">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500 text-lg font-black text-white shadow-lg shadow-emerald-500/30">
              TT
            </div>
            <span className="text-xl font-black tracking-tight">TAC-TIC</span>
          </div>

          <h1 className="mt-16 text-4xl font-black leading-tight">
            CRM intelligent piloté par l'IA
          </h1>
          <p className="mt-4 max-w-md text-base leading-7 text-slate-300">
            Automatisez votre processus commercial de A à Z.
          </p>

          <ul className="mt-10 space-y-4">
            {KEY_POINTS.map((point) => (
              <li key={point} className="flex items-center gap-3 text-slate-200">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-300">
                  <Icon name="check" size={16} />
                </span>
                <span className="text-sm">{point}</span>
              </li>
            ))}
          </ul>
        </div>

        <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
          Powered by TAC-TIC AI
        </p>
      </section>

      {/* Colonne droite — formulaire */}
      <section className="flex min-h-screen items-center justify-center px-6 py-12 lg:min-h-0">
        <div className="w-full max-w-sm">
          {/* Logo mobile */}
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500 font-black text-white">
              TT
            </div>
            <span className="text-lg font-black text-slate-900">TAC-TIC</span>
          </div>

          <h2 className="text-2xl font-black text-slate-900">Bon retour parmi nous</h2>
          <p className="mt-2 text-sm text-slate-500">Connectez-vous à votre espace</p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-5" noValidate>
            {/* Email */}
            <div>
              <label htmlFor="login-email" className="mb-1.5 block text-sm font-semibold text-slate-700">
                Email professionnel
              </label>
              <div className="relative">
                <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-400">
                  <Icon name="mail" size={18} />
                </span>
                <input
                  id="login-email"
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  tabIndex={1}
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="vous@tac-tic.tn"
                  className={`w-full rounded-lg border bg-white py-2.5 pl-10 pr-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:ring-2 ${
                    showEmailError
                      ? 'border-rose-400 focus:border-rose-400 focus:ring-rose-100'
                      : 'border-slate-300 focus:border-emerald-500 focus:ring-emerald-100'
                  }`}
                />
              </div>
              {showEmailError ? (
                <p className="mt-1.5 text-xs font-medium text-rose-600">Adresse email invalide.</p>
              ) : null}
            </div>

            {/* Password */}
            <div>
              <label htmlFor="login-password" className="mb-1.5 block text-sm font-semibold text-slate-700">
                Mot de passe
              </label>
              <div className="relative">
                <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-400">
                  <Icon name="lock" size={18} />
                </span>
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  tabIndex={2}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-lg border border-slate-300 bg-white py-2.5 pl-10 pr-10 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
                  className="absolute inset-y-0 right-3 flex items-center text-slate-400 transition hover:text-slate-600"
                >
                  <Icon name="eye" size={18} />
                </button>
              </div>
            </div>

            {errorMessage ? (
              <div className="flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm font-medium text-rose-700">
                <Icon name="alert" size={16} />
                <span>{errorMessage}</span>
              </div>
            ) : null}

            <button
              type="submit"
              tabIndex={3}
              disabled={isSubmitting || !email.trim() || !password}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-bold text-white shadow-md shadow-emerald-600/20 transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
            >
              {isSubmitting ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              ) : null}
              {isSubmitting ? 'Connexion…' : 'Se connecter'}
            </button>

            <div className="text-center">
              <a href="#" className="text-xs font-semibold text-emerald-600 hover:text-emerald-700">
                Mot de passe oublié ?
              </a>
            </div>
          </form>
        </div>
      </section>
    </div>
  )
}

export default LoginPage
