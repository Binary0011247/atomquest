import api from "./axios"

export const getMyGoals = () => api.get("/goals/my")

export const getGoal = (id) => api.get(`/goals/${id}`)

export const createGoal = (data) => api.post("/goals/", data)

export const updateGoal = (id, data) => api.put(`/goals/${id}`, data)

export const deleteGoal = (id) => api.delete(`/goals/${id}`)

export const submitGoal = (id) => api.post(`/goals/${id}/submit`)

export const submitAllGoals = () => api.post("/goals/submit-all")

export const getTeamGoals = () => api.get("/goals/team")
