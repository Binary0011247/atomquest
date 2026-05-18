import api from "./axios"

export const getManagerDashboard = () => api.get("/approvals/dashboard")

export const getPendingApprovals = () => api.get("/approvals/pending")

export const reviewGoal = (goalId, data) => api.post(`/approvals/${goalId}/review`, data)

export const approveAll = async (employeeId) => {
  const response = await api.post(`/approvals/approve-all/${employeeId}`)
  return response.data
}

export const getApprovalHistory = (employeeId) => api.get(`/approvals/history/${employeeId}`)
