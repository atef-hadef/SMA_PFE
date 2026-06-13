import { get, post, put } from './apiClient'

type AdminUserRecord = {
  id: string
  name: string
  email: string
  role: string
  department: string
  status: 'active' | 'inactive'
  last_login: string | null
}

type AdminRoleRecord = {
  id: string
  name: string
  description: string
  user_count: number
  permissions: string[]
}

type CreateUserInput = {
  name: string
  email: string
  role: string
  department: string
}

type UpdateUserInput = Partial<CreateUserInput> & {
  status?: 'active' | 'inactive'
}

type UserCreatedResponse = {
  id: string
  name: string
  email: string
  role: string
  department: string
  status: 'active'
  created_at: string
}

type UserUpdatedResponse = {
  id: string
  name: string
  role: string
  department: string
  updated_at: string
}

type DeactivateUserResponse = {
  id: string
  status: 'inactive'
  deactivated_at: string
  reason: string
}

type RolePermissionsUpdatedResponse = {
  id: string
  name: string
  permissions: string[]
  updated_at: string
}

type PaginationMeta = {
  page: number
  page_size: number
  total_items: number
  total_pages: number
}

type PaginatedResponse<T> = {
  items: T[]
  pagination: PaginationMeta
}

function getUsers() {
  return get<PaginatedResponse<AdminUserRecord>>('/users')
}

function createUser(input: CreateUserInput) {
  return post<UserCreatedResponse>('/users', input)
}

function updateUser(userId: string, input: UpdateUserInput) {
  return put<UserUpdatedResponse>(`/users/${userId}`, input)
}

function deactivateUser(userId: string, reason: string) {
  return post<DeactivateUserResponse>(`/users/${userId}/deactivate`, {
    reason,
  })
}

function getRoles() {
  return get<PaginatedResponse<AdminRoleRecord>>('/roles')
}

function updateRolePermissions(roleId: string, permissions: string[]) {
  return put<RolePermissionsUpdatedResponse>(`/roles/${roleId}/permissions`, {
    permissions,
  })
}

export type {
  AdminRoleRecord,
  AdminUserRecord,
  CreateUserInput,
  DeactivateUserResponse,
  PaginatedResponse,
  RolePermissionsUpdatedResponse,
  UpdateUserInput,
  UserCreatedResponse,
  UserUpdatedResponse,
}
export { createUser, deactivateUser, getRoles, getUsers, updateRolePermissions, updateUser }
