import { useEffect, useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { getDefaultPathForPermissions } from '../auth/permissions'
import { useAuth } from '../auth/useAuth'
import { Icon } from '../components/common'

type LocationState = {
  from?: {
    pathname?: string
  }
}

function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { isAuthenticated, isLoading, login, user } = useAuth()
  const [email, setEmail] = useState('admin@flowpilot.ai')
  const [password, setPassword] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (!isLoading && isAuthenticated && user) {
      navigate(getDefaultPathForPermissions(user.permissions), { replace: true })
    }
  }, [isAuthenticated, isLoading, navigate, user])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErrorMessage('')
    setIsSubmitting(true)

    try {
      const loggedInUser = await login(email, password)
      const state = location.state as LocationState | null
      const fallbackPath = getDefaultPathForPermissions(loggedInUser.permissions)
      navigate(state?.from?.pathname ?? fallbackPath, { replace: true })
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : 'Connexion impossible. Verifiez vos identifiants.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-linear-to-br from-slate-950 via-slate-900 to-slate-950 px-4 py-8 text-slate-100">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-6xl items-center justify-center">
        <div className="grid w-full overflow-hidden rounded-xl border border-slate-800 bg-slate-950/70 shadow-2xl shadow-slate-950/50 lg:grid-cols-[1fr_420px]">
          <section className="hidden border-r border-slate-800 bg-slate-900/50 p-10 lg:block">
            <div className="flex h-full flex-col justify-between">
              <div>
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-linear-to-br from-emerald-500 to-emerald-600 font-black text-white">
                  FP
                </div>
                <h1 className="mt-8 text-3xl font-black tracking-tight text-white">
                  FlowPilot AI
                </h1>
                <p className="mt-3 max-w-xl text-sm leading-6 text-slate-400">
                  Espace securise pour piloter les processus CRM, demandes de conge,
                  automatisations et agents IA selon vos permissions.
                </p>
              </div>

              <div className="grid gap-3">
                {[
                  'Authentification JWT cote FastAPI',
                  'RBAC par permissions',
                  'Acces interface et API controles',
                ].map((item) => (
                  <div
                    key={item}
                    className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-950/50 px-4 py-3 text-sm text-slate-300"
                  >
                    <Icon name="check" size={16} className="text-emerald-400" />
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="p-6 sm:p-8">
            <div className="mb-8 lg:hidden">
              <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-linear-to-br from-emerald-500 to-emerald-600 font-black text-white">
                FP
              </div>
              <h1 className="mt-4 text-2xl font-black text-white">FlowPilot AI</h1>
            </div>

            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-emerald-300">
                Connexion securisee
              </p>
              <h2 className="mt-2 text-2xl font-black text-white">
                Acceder a la plateforme
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Utilisez un compte demo local ou un utilisateur cree dans PostgreSQL.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="mt-8 space-y-5">
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                  Email
                </span>
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="email"
                  className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950/80 px-3 py-2.5 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/20"
                />
              </label>

              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                  Mot de passe
                </span>
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                  className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950/80 px-3 py-2.5 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/20"
                />
              </label>

              {errorMessage ? (
                <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm font-medium text-rose-200">
                  {errorMessage}
                </div>
              ) : null}

              <button
                type="submit"
                disabled={isSubmitting || !email.trim() || !password}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-emerald-400 bg-emerald-500 px-4 py-2.5 text-sm font-bold text-slate-950 shadow-md shadow-emerald-500/20 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-700 disabled:text-slate-400"
              >
                {isSubmitting ? (
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-950 border-t-transparent" />
                ) : (
                  <Icon name="lock" size={16} />
                )}
                {isSubmitting ? 'Connexion...' : 'Se connecter'}
              </button>
            </form>

            <p className="mt-6 rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2 text-xs leading-5 text-slate-400">
              Les comptes de demonstration sont documentes dans
              <span className="font-semibold text-slate-200"> docs/step_69_auth_rbac.md</span>.
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}

export default LoginPage
