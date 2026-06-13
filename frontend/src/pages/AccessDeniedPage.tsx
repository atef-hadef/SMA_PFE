import { useNavigate } from 'react-router-dom'
import { getDefaultPathForPermissions } from '../auth/permissions'
import { useAuth } from '../auth/useAuth'
import { ActionButton, AppCard, Icon, PageHeader } from '../components/common'

type AccessDeniedPageProps = {
  requiredPermissions?: string[]
}

function AccessDeniedPage({ requiredPermissions = [] }: AccessDeniedPageProps) {
  const navigate = useNavigate()
  const { accessDeniedMessage, clearAccessDeniedMessage, user } = useAuth()
  const homePath = getDefaultPathForPermissions(user?.permissions ?? [])

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Securite"
        title="Acces refuse"
        subtitle="Votre role ne dispose pas des autorisations necessaires pour cette interface ou cette action."
        statusLabel="403"
        statusTone="danger"
      />

      <AppCard
        eyebrow="Autorisation"
        title="Permission insuffisante"
        description={
          accessDeniedMessage ??
          "Cette ressource est protegee par la couche RBAC FlowPilot AI."
        }
      >
        {requiredPermissions.length > 0 ? (
          <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              Permissions acceptees
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {requiredPermissions.map((permission) => (
                <span
                  key={permission}
                  className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs text-slate-300"
                >
                  {permission}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        <div className="mt-5 flex flex-wrap gap-3">
          <ActionButton
            label={
              <span className="inline-flex items-center gap-1.5">
                <Icon name="dashboard" size={14} />
                Retour a mon espace
              </span>
            }
            onClick={() => {
              clearAccessDeniedMessage()
              navigate(homePath, { replace: true })
            }}
          />
        </div>
      </AppCard>
    </div>
  )
}

export default AccessDeniedPage
