type Permission =
  | 'dashboard.view'
  | 'admin.users.manage'
  | 'admin.roles.manage'
  | 'crm.leads.view'
  | 'crm.leads.create'
  | 'crm.leads.update'
  | 'crm.interactions.create'
  | 'crm.drafts.generate'
  | 'crm.drafts.review'
  | 'crm.email.approve'
  | 'crm.email.send'
  | 'crm.customer.convert'
  | 'crm.vip.manage'
  | 'crm.tasks.view'
  | 'crm.tasks.manage'
  | 'crm.deals.view'
  | 'crm.deals.manage'
  | 'leave.request.create'
  | 'leave.request.view_own'
  | 'leave.request.view_all'
  | 'leave.request.approve'
  | 'leave.request.reject'
  | 'leave.request.hr_validate'
  | 'workflow.monitor.view'
  | 'workflow.executions.view'
  | 'workflow.executions.retry'
  | 'agents.view'
  | 'agents.run'

const ROUTE_PERMISSIONS: Record<string, Permission[]> = {
  '/dashboard': ['dashboard.view'],
  '/assistant': ['dashboard.view'],
  '/crm-leads': ['crm.leads.view'],
  '/crm-lead-details': ['crm.leads.view'],
  '/crm-tasks': ['crm.tasks.view'],
  '/crm-deals': ['crm.deals.view'],
  '/leave-requests': ['leave.request.create', 'leave.request.view_own'],
  '/manager-approvals': ['leave.request.approve', 'leave.request.view_all'],
  '/workflow-monitoring': ['workflow.monitor.view', 'workflow.executions.view'],
  '/ai-agents': ['agents.view'],
  '/admin/users': ['admin.users.manage'],
  '/admin/roles-permissions': ['admin.roles.manage'],
}

function getDefaultPathForPermissions(permissions: string[]) {
  const orderedPaths = [
    '/dashboard',
    '/crm-leads',
    '/leave-requests',
    '/manager-approvals',
    '/workflow-monitoring',
    '/ai-agents',
    '/admin/users',
  ]

  return (
    orderedPaths.find((path) =>
      ROUTE_PERMISSIONS[path].some((permission) => permissions.includes(permission)),
    ) ?? '/access-denied'
  )
}

export type { Permission }
export { ROUTE_PERMISSIONS, getDefaultPathForPermissions }
