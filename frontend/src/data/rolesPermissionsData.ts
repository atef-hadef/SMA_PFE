import type { TableRow } from '../components/common'

type RolesKpi = {
  label: string
  value: string
  trend?: string
}

type RoleItem = {
  id: string
  name: string
  department: string
  users: string
  status: TableRow['status']
}

type SelectedRole = {
  name: string
  department: string
  description: string
  users: string
  scope: string
  lastUpdated: string
}

type PermissionCategory = {
  name: string
  dashboard: boolean
  leaveManagement: boolean
  crmIntelligence: boolean
  aiAgents: boolean
  workflowMonitoring: boolean
  admin: boolean
}

type PermissionSummary = {
  title: string
  detail: string
  status: TableRow['status']
}

const rolesKpis: RolesKpi[] = [
  { label: 'Total Roles', value: '6', trend: '3 core roles' },
  { label: 'Permission Rules', value: '18', trend: 'Across all modules' },
  { label: 'Admin Roles', value: '2', trend: 'Privileged access' },
  { label: 'Restricted Permissions', value: '4', trend: 'Approval needed' },
]

const rolesList: RoleItem[] = [
  { id: 'role-1', name: 'Super Admin', department: 'Operations', users: '2', status: 'danger' },
  { id: 'role-2', name: 'Operations Manager', department: 'Operations', users: '5', status: 'warning' },
  { id: 'role-3', name: 'CRM Lead Manager', department: 'Sales', users: '4', status: 'success' },
  { id: 'role-4', name: 'Workflow Analyst', department: 'Monitoring', users: '6', status: 'info' },
  { id: 'role-5', name: 'HR Reviewer', department: 'HR', users: '3', status: 'warning' },
]

const selectedRole: SelectedRole = {
  name: 'Operations Manager',
  department: 'Operations',
  description: 'Balanced operational role for managing leave approvals, workflow monitoring, and CRM oversight.',
  users: '5 assigned users',
  scope: 'Mid-level control across Leave, CRM, and Monitoring modules',
  lastUpdated: 'Today at 10:40 AM',
}

const permissionCategories: PermissionCategory[] = [
  {
    name: 'Dashboard',
    dashboard: true,
    leaveManagement: false,
    crmIntelligence: true,
    aiAgents: true,
    workflowMonitoring: true,
    admin: false,
  },
  {
    name: 'Leave Management',
    dashboard: true,
    leaveManagement: true,
    crmIntelligence: false,
    aiAgents: false,
    workflowMonitoring: true,
    admin: false,
  },
  {
    name: 'CRM Intelligence',
    dashboard: true,
    leaveManagement: false,
    crmIntelligence: true,
    aiAgents: true,
    workflowMonitoring: true,
    admin: false,
  },
  {
    name: 'AI Agents',
    dashboard: true,
    leaveManagement: false,
    crmIntelligence: true,
    aiAgents: true,
    workflowMonitoring: true,
    admin: false,
  },
  {
    name: 'Workflow Monitoring',
    dashboard: true,
    leaveManagement: true,
    crmIntelligence: true,
    aiAgents: true,
    workflowMonitoring: true,
    admin: false,
  },
  {
    name: 'Admin',
    dashboard: true,
    leaveManagement: false,
    crmIntelligence: false,
    aiAgents: false,
    workflowMonitoring: true,
    admin: false,
  },
]

const permissionSummary: PermissionSummary[] = [
  {
    title: 'Module coverage',
    detail: 'The selected role can access the core operational dashboard and module summaries.',
    status: 'success',
  },
  {
    title: 'Restricted actions',
    detail: 'Admin-level actions remain locked for this role to protect account management controls.',
    status: 'warning',
  },
  {
    title: 'Audit readiness',
    detail: 'Permission scope is narrow enough for clear operational auditing.',
    status: 'info',
  },
]

export type { PermissionCategory, PermissionSummary, RoleItem, RolesKpi, SelectedRole }
export { permissionCategories, permissionSummary, rolesKpis, rolesList, selectedRole }
