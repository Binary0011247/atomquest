import axios from "axios"

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000/api",
  headers: {
    "Content-Type": "application/json",
  },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token")
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export function setDemoMode(enabled) {
  if (enabled) {
    api.defaults.headers.common["X-Demo-Mode"] = "true"
    localStorage.setItem("demo_mode", "true")
  } else {
    delete api.defaults.headers.common["X-Demo-Mode"]
    localStorage.removeItem("demo_mode")
  }
}

if (localStorage.getItem("demo_mode") === "true") {
  api.defaults.headers.common["X-Demo-Mode"] = "true"
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && window.location.pathname !== "/login") {
      localStorage.clear()
      window.location.href = "/login"
    }
    return Promise.reject(error)
  },
)

export default api
