import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { getDefaultPathForPermissions, ROUTE_PERMISSIONS } from './auth/permissions'
import { useAuth } from './auth/useAuth'
import ProtectedRoute from './components/auth/ProtectedRoute'
import RequirePermission from './components/auth/RequirePermission'
import MainLayout from './layouts/MainLayout'
import { ThemeProvider } from './theme/ThemeContext'
import AccessDeniedPage from './pages/AccessDeniedPage'
import ActivityFeedPage from './pages/ActivityFeedPage'
import AdminUsersPage from './pages/AdminUsersPage'
import AIAgentCenterPage from './pages/AIAgentCenterPage'
import AssistantPage from './pages/AssistantPage'
import CRMDealsPage from './pages/CRMDealsPage'
import CRMLeadDetailsPage from './pages/CRMLeadDetailsPage'
import CRMLeadsPage from './pages/CRMLeadsPage'
import CRMTasksPage from './pages/CRMTasksPage'
import DashboardPage from './pages/DashboardPage'
import DataSciencePage from './pages/DataSciencePage'
import LeaveAllocationPage from './pages/LeaveAllocationPage'
import LeaveRequestPage from './pages/LeaveRequestPage'
import LoginPage from './pages/LoginPage'
import ManagerApprovalPage from './pages/ManagerApprovalPage'
import RolesPermissionsPage from './pages/RolesPermissionsPage'
import WorkflowMonitoringPage from './pages/WorkflowMonitoringPage'

function ProtectedPage({ permissions, children }: { permissions: string[]; children: ReactNode }) {
  return (
    <ProtectedRoute>
      <MainLayout>
        <RequirePermission anyOf={permissions}>{children}</RequirePermission>
      </MainLayout>
    </ProtectedRoute>
  )
}

function HomeRedirect() {
  const { user } = useAuth()
  return <Navigate to={getDefaultPathForPermissions(user?.permissions ?? [])} replace />
}

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <HomeRedirect />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard"
            element={
              <ProtectedPage permissions={ROUTE_PERMISSIONS['/dashboard']}>
                <DashboardPage />
              </ProtectedPage>
            }
          />
          <Route
            path="/assistant"
            element={
              <ProtectedPage permissions={ROUTE_PERMISSIONS['/assistant']}>
                <AssistantPage />
              </ProtectedPage>
            }
          />
          <Route
            path="/leave-requests"
            element={
              <ProtectedPage permissions={ROUTE_PERMISSIONS['/leave-requests']}>
                <LeaveRequestPage />
              </ProtectedPage>
            }
          />
          <Route
            path="/manager-approvals"
            element={
              <ProtectedPage permissions={ROUTE_PERMISSIONS['/manager-approvals']}>
                <ManagerApprovalPage />
              </ProtectedPage>
            }
          />
          <Route
            path="/leave-allocations"
            element={
              <ProtectedPage permissions={ROUTE_PERMISSIONS['/leave-allocations']}>
                <LeaveAllocationPage />
              </ProtectedPage>
            }
          />
          <Route
            path="/crm-leads"
            element={
              <ProtectedPage permissions={ROUTE_PERMISSIONS['/crm-leads']}>
                <CRMLeadsPage />
              </ProtectedPage>
            }
          />
          <Route
            path="/crm-lead-details"
            element={
              <ProtectedPage permissions={ROUTE_PERMISSIONS['/crm-lead-details']}>
                <CRMLeadDetailsPage />
              </ProtectedPage>
            }
          />
          <Route
            path="/crm-tasks"
            element={
              <ProtectedPage permissions={ROUTE_PERMISSIONS['/crm-tasks']}>
                <CRMTasksPage />
              </ProtectedPage>
            }
          />
          <Route
            path="/crm-deals"
            element={
              <ProtectedPage permissions={ROUTE_PERMISSIONS['/crm-deals']}>
                <CRMDealsPage />
              </ProtectedPage>
            }
          />
          <Route
            path="/data-science"
            element={
              <ProtectedPage permissions={ROUTE_PERMISSIONS['/data-science']}>
                <DataSciencePage />
              </ProtectedPage>
            }
          />
          <Route
            path="/activities"
            element={
              <ProtectedPage permissions={ROUTE_PERMISSIONS['/activities']}>
                <ActivityFeedPage />
              </ProtectedPage>
            }
          />
          <Route
            path="/ai-agents"
            element={
              <ProtectedPage permissions={ROUTE_PERMISSIONS['/ai-agents']}>
                <AIAgentCenterPage />
              </ProtectedPage>
            }
          />
          <Route
            path="/workflow-monitoring"
            element={
              <ProtectedPage permissions={ROUTE_PERMISSIONS['/workflow-monitoring']}>
                <WorkflowMonitoringPage />
              </ProtectedPage>
            }
          />
          <Route
            path="/admin/users"
            element={
              <ProtectedPage permissions={ROUTE_PERMISSIONS['/admin/users']}>
                <AdminUsersPage />
              </ProtectedPage>
            }
          />
          <Route
            path="/admin/roles-permissions"
            element={
              <ProtectedPage permissions={ROUTE_PERMISSIONS['/admin/roles-permissions']}>
                <RolesPermissionsPage />
              </ProtectedPage>
            }
          />
          <Route
            path="/access-denied"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <AccessDeniedPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  )
}

export default App
