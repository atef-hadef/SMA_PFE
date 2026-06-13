import type { TableRow } from '../components/common'

type AdminKpi = {
  label: string
  value: string
  trend?: string
}

type AdminUser = {
  id: string
  name: string
  email: string
  role: 'Admin' | 'Manager' | 'User'
  department: string
  status: TableRow['status']
  lastLogin: string
}

type SelectedUser = {
  name: string
  email: string
  role: string
  department: string
  status: string
  lastLogin: string
}

type PermissionItem = {
  label: string
  detail: string
  status: TableRow['status']
}

const adminKpis: AdminKpi[] = [
  { label: 'Total Users', value: '42', trend: '+3 this month' },
  { label: 'Active Users', value: '38', trend: '91% online' },
  { label: 'Manager Accounts', value: '9', trend: 'Across departments' },
  { label: 'Admin Accounts', value: '3', trend: 'Full control' },
]

const adminUsers: AdminUser[] = [
  {
    id: 'u-1',
    name: 'Sarah Johnson',
    email: 'sarah@flowpilot.ai',
    role: 'Admin',
    department: 'Operations',
    status: 'success',
    lastLogin: '2 min ago',
  },
  {
    id: 'u-2',
    name: 'Daniel Kim',
    email: 'daniel@flowpilot.ai',
    role: 'Manager',
    department: 'Product',
    status: 'warning',
    lastLogin: '14 min ago',
  },
  {
    id: 'u-3',
    name: 'Amina Rafi',
    email: 'amina@flowpilot.ai',
    role: 'Manager',
    department: 'Customer Success',
    status: 'success',
    lastLogin: '8 min ago',
  },
  {
    id: 'u-4',
    name: 'Julien Moreau',
    email: 'julien@flowpilot.ai',
    role: 'User',
    department: 'Sales',
    status: 'info',
    lastLogin: '1 hour ago',
  },
  {
    id: 'u-5',
    name: 'Mariam El-Sayed',
    email: 'mariam@flowpilot.ai',
    role: 'User',
    department: 'HR',
    status: 'danger',
    lastLogin: '3 days ago',
  },
]

const selectedUser: SelectedUser = {
  name: 'Sarah Johnson',
  email: 'sarah@flowpilot.ai',
  role: 'Admin',
  department: 'Operations',
  status: 'Active account with full access',
  lastLogin: '2 min ago',
}

const permissionPreview: PermissionItem[] = [
  {
    label: 'Workflow Management',
    detail: 'Can review and adjust AI workflow executions.',
    status: 'success',
  },
  {
    label: 'User Administration',
    detail: 'Can add, edit, and deactivate users.',
    status: 'warning',
  },
  {
    label: 'Reporting Access',
    detail: 'Can view dashboards and operational summaries.',
    status: 'info',
  },
]

export type { AdminKpi, AdminUser, PermissionItem, SelectedUser }
export { adminKpis, adminUsers, permissionPreview, selectedUser }
