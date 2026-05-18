import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"

import AppLayout from "@/components/Layout/AppLayout"
import ProtectedRoute from "@/components/ProtectedRoute"
import { AuthProvider } from "@/context/AuthContext"
import { ToastProvider } from "@/context/ToastContext"
import AdminDashboard from "@/pages/admin/AdminDashboard"
import AnalyticsPage from "@/pages/admin/AnalyticsPage"
import AuditLogPage from "@/pages/admin/AuditLogPage"
import CycleManagementPage from "@/pages/admin/CycleManagementPage"
import EscalationPage from "@/pages/admin/EscalationPage"
import ReportsPage from "@/pages/admin/ReportsPage"
import SharedGoalsPage from "@/pages/admin/SharedGoalsPage"
import UserManagementPage from "@/pages/admin/UserManagementPage"
import CheckinPage from "@/pages/employee/CheckinPage"
import EmployeeDashboard from "@/pages/employee/EmployeeDashboard"
import EmployeeProgressPage from "@/pages/employee/EmployeeProgressPage"
import GoalFormPage from "@/pages/employee/GoalFormPage"
import AuthCallback from "@/pages/AuthCallback"
import Login from "@/pages/Login"
import ManagerDashboard from "@/pages/manager/ManagerDashboard"
import ManagerTeamProgressPage from "@/pages/manager/ManagerTeamProgressPage"
import TeamCheckinView from "@/pages/manager/TeamCheckinView"

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/auth/callback" element={<AuthCallback />} />
            <Route
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route
                path="/employee/dashboard"
                element={
                  <ProtectedRoute allowedRole="employee">
                    <EmployeeDashboard />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/employee/goals/new"
                element={
                  <ProtectedRoute allowedRole="employee">
                    <GoalFormPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/employee/goals/edit/:id"
                element={
                  <ProtectedRoute allowedRole="employee">
                    <GoalFormPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/employee/checkins"
                element={
                  <ProtectedRoute allowedRole="employee">
                    <CheckinPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/employee/progress"
                element={
                  <ProtectedRoute allowedRole="employee">
                    <EmployeeProgressPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/manager/dashboard"
                element={
                  <ProtectedRoute allowedRole="manager">
                    <ManagerDashboard />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/manager/checkins"
                element={
                  <ProtectedRoute allowedRole="manager">
                    <TeamCheckinView />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/manager/team-progress"
                element={
                  <ProtectedRoute allowedRole="manager">
                    <ManagerTeamProgressPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/dashboard"
                element={
                  <ProtectedRoute allowedRole="admin">
                    <AdminDashboard />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/users"
                element={
                  <ProtectedRoute allowedRole="admin">
                    <UserManagementPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/analytics"
                element={
                  <ProtectedRoute allowedRole="admin">
                    <AnalyticsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/reports"
                element={
                  <ProtectedRoute allowedRole="admin">
                    <ReportsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/audit-logs"
                element={
                  <ProtectedRoute allowedRole="admin">
                    <AuditLogPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/cycles"
                element={
                  <ProtectedRoute allowedRole="admin">
                    <CycleManagementPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/escalations"
                element={
                  <ProtectedRoute allowedRole="admin">
                    <EscalationPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/shared-goals"
                element={
                  <ProtectedRoute allowedRole="admin">
                    <SharedGoalsPage />
                  </ProtectedRoute>
                }
              />
            </Route>
            <Route path="/" element={<Navigate to="/login" replace />} />
            <Route path="*" element={<Navigate to="/login" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ToastProvider>
  )
}
