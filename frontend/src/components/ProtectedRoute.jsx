import { Navigate } from "react-router-dom"

import LoadingSpinner from "@/components/LoadingSpinner"
import { getDashboardPath, useAuth } from "@/context/AuthContext"

export default function ProtectedRoute({ allowedRole, children }) {
  const { isAuthenticated, loading, role } = useAuth()

  if (loading) {
    return <LoadingSpinner fullPage />
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (allowedRole && role !== allowedRole) {
    return <Navigate to={getDashboardPath(role)} replace />
  }

  return children
}
