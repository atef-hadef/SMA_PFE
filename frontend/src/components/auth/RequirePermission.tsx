import type { ReactNode } from 'react'
import { useAuth } from '../../auth/useAuth'
import AccessDeniedPage from '../../pages/AccessDeniedPage'

type RequirePermissionProps = {
  anyOf: string[]
  children: ReactNode
}

function RequirePermission({ anyOf, children }: RequirePermissionProps) {
  const { hasAnyPermission } = useAuth()

  if (!hasAnyPermission(anyOf)) {
    return <AccessDeniedPage requiredPermissions={anyOf} />
  }

  return <>{children}</>
}

export default RequirePermission
