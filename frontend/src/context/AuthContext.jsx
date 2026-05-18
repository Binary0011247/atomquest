import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"

import api from "@/api/axios"
import { isTokenExpired } from "@/utils/jwt"

const AuthContext = createContext(null)

const DASHBOARD_BY_ROLE = {
  employee: "/employee/dashboard",
  manager: "/manager/dashboard",
  admin: "/admin/dashboard",
}

export function getDashboardPath(role) {
  return DASHBOARD_BY_ROLE[role] ?? "/login"
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(() => localStorage.getItem("access_token"))
  const [loading, setLoading] = useState(Boolean(localStorage.getItem("access_token")))

  const logout = useCallback(() => {
    localStorage.removeItem("access_token")
    setToken(null)
    setUser(null)
  }, [])

  const login = useCallback(async (email, password) => {
    const form = new URLSearchParams()
    form.append("username", email)
    form.append("password", password)

    const { data } = await api.post("/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    })

    localStorage.setItem("access_token", data.access_token)
    setToken(data.access_token)
    setUser(data.user)
    return data.user
  }, [])

  const completeOAuthLogin = useCallback((accessToken, userData) => {
    localStorage.setItem("access_token", accessToken)
    setToken(accessToken)
    setUser(userData)
    return userData
  }, [])

  useEffect(() => {
    if (!token) {
      setLoading(false)
      return
    }

    if (isTokenExpired(token)) {
      localStorage.clear()
      setToken(null)
      setUser(null)
      setLoading(false)
      if (window.location.pathname !== "/login") {
        window.location.href = "/login?expired=1"
      }
      return
    }

    let cancelled = false

    api
      .get("/auth/me")
      .then((response) => {
        if (!cancelled) {
          setUser(response.data)
        }
      })
      .catch(() => {
        if (!cancelled) {
          logout()
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [token, logout])

  const value = useMemo(
    () => ({
      user,
      token,
      loading,
      role: user?.role ?? null,
      isAuthenticated: Boolean(token && user),
      login,
      completeOAuthLogin,
      logout,
    }),
    [user, token, loading, login, completeOAuthLogin, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
