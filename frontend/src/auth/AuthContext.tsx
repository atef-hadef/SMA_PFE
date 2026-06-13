import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useNavigate } from 'react-router-dom'
import {
  clearStoredAccessToken,
  getStoredAccessToken,
  setStoredAccessToken,
} from '../services/apiClient'
import {
  getCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  type AuthUser,
} from '../services/authService'

type AuthContextValue = {
  user: AuthUser | null
  isAuthenticated: boolean
  isLoading: boolean
  accessDeniedMessage: string | null
  login: (email: string, password: string) => Promise<AuthUser>
  logout: () => Promise<void>
  hasPermission: (permission: string) => boolean
  hasAnyPermission: (permissions: string[]) => boolean
  clearAccessDeniedMessage: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [accessDeniedMessage, setAccessDeniedMessage] = useState<string | null>(null)

  const handleLogoutState = useCallback(() => {
    clearStoredAccessToken()
    setUser(null)
  }, [])

  useEffect(() => {
    let isMounted = true

    async function loadCurrentUser() {
      if (!getStoredAccessToken()) {
        setIsLoading(false)
        return
      }

      try {
        const currentUser = await getCurrentUser()
        if (isMounted) setUser(currentUser)
      } catch {
        if (isMounted) handleLogoutState()
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }

    void loadCurrentUser()
    return () => {
      isMounted = false
    }
  }, [handleLogoutState])

  useEffect(() => {
    function handleUnauthorized() {
      handleLogoutState()
      navigate('/login', { replace: true })
    }

    function handleForbidden(event: Event) {
      const detail = (event as CustomEvent<{ message?: string }>).detail
      setAccessDeniedMessage(detail?.message ?? 'Access denied.')
      navigate('/access-denied', { replace: false })
    }

    window.addEventListener('flowpilot:unauthorized', handleUnauthorized)
    window.addEventListener('flowpilot:forbidden', handleForbidden)
    return () => {
      window.removeEventListener('flowpilot:unauthorized', handleUnauthorized)
      window.removeEventListener('flowpilot:forbidden', handleForbidden)
    }
  }, [handleLogoutState, navigate])

  const login = useCallback(async (email: string, password: string) => {
    const response = await loginRequest({ email, password })
    setStoredAccessToken(response.access_token)
    setUser(response.user)
    setAccessDeniedMessage(null)
    return response.user
  }, [])

  const logout = useCallback(async () => {
    try {
      if (getStoredAccessToken()) {
        await logoutRequest()
      }
    } catch {
      // Token removal is the authoritative client-side logout step.
    } finally {
      handleLogoutState()
      navigate('/login', { replace: true })
    }
  }, [handleLogoutState, navigate])

  const hasPermission = useCallback(
    (permission: string) => Boolean(user?.permissions.includes(permission)),
    [user],
  )

  const hasAnyPermission = useCallback(
    (permissions: string[]) =>
      Boolean(user && permissions.some((permission) => user.permissions.includes(permission))),
    [user],
  )

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: Boolean(user),
      isLoading,
      accessDeniedMessage,
      login,
      logout,
      hasPermission,
      hasAnyPermission,
      clearAccessDeniedMessage: () => setAccessDeniedMessage(null),
    }),
    [
      accessDeniedMessage,
      hasAnyPermission,
      hasPermission,
      isLoading,
      login,
      logout,
      user,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export { AuthContext, AuthProvider }
export type { AuthContextValue }
