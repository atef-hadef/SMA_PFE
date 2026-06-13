type UserRole =
  | 'Admin'
  | 'Employee'
  | 'Manager'
  | 'HR Officer'
  | 'Sales Agent'
  | 'CRM Manager'

type MockUser = {
  id: string
  name: string
  role: UserRole
  initials: string
}

const availableRoles: UserRole[] = [
  'Admin',
  'Employee',
  'Manager',
  'HR Officer',
  'Sales Agent',
  'CRM Manager',
]

const currentUser: MockUser = {
  id: 'user-admin-001',
  name: 'Admin User',
  role: 'Admin',
  initials: 'AU',
}

const allowedNavigationPaths: Record<UserRole, string[]> = {
  Admin: [
    '/dashboard',
    '/assistant',
    '/leave-requests',
    '/manager-approvals',
    '/crm-leads',
    '/crm-lead-details',
    '/crm-tasks',
    '/crm-deals',
    '/ai-agents',
    '/workflow-monitoring',
    '/admin/users',
    '/admin/roles-permissions',
  ],
  Employee: ['/dashboard', '/assistant', '/leave-requests'],
  Manager: ['/dashboard', '/assistant', '/leave-requests', '/manager-approvals'],
  'HR Officer': [
    '/dashboard',
    '/assistant',
    '/leave-requests',
    '/manager-approvals',
    '/workflow-monitoring',
  ],
  'Sales Agent': [
    '/dashboard',
    '/assistant',
    '/crm-leads',
    '/crm-lead-details',
    '/crm-tasks',
    '/crm-deals',
  ],
  'CRM Manager': [
    '/dashboard',
    '/assistant',
    '/crm-leads',
    '/crm-lead-details',
    '/crm-tasks',
    '/crm-deals',
    '/ai-agents',
    '/workflow-monitoring',
  ],
}

export type { MockUser, UserRole }
export { allowedNavigationPaths, availableRoles, currentUser }
