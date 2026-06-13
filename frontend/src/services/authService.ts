import { get, post } from './apiClient'

type AuthUser = {
  id: string
  full_name: string
  email: string
  role_id: string
  role_name: string
  permissions: string[]
  status: string
  job_title?: string | null
  department?: string | null
}

type LoginResponse = {
  access_token: string
  token_type: 'bearer'
  user: AuthUser
}

type LoginPayload = {
  email: string
  password: string
}

function login(payload: LoginPayload) {
  return post<LoginResponse>('/auth/login', payload)
}

function getCurrentUser() {
  return get<AuthUser>('/auth/me')
}

function logout() {
  return post<{ message: string }>('/auth/logout')
}

export type { AuthUser, LoginPayload, LoginResponse }
export { getCurrentUser, login, logout }
