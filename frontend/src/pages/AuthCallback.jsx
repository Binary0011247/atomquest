import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"

import api from "@/api/axios"
import { getDashboardPath, useAuth } from "@/context/AuthContext"
import { useToast } from "@/context/ToastContext"
import usePageTitle from "@/hooks/usePageTitle"

export default function AuthCallback() {
  usePageTitle("Signing in")
  const [searchParams] = useSearchParams()
  const { completeOAuthLogin } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const [error, setError] = useState(null)

  useEffect(() => {
    const code = searchParams.get("code")
    if (!code) {
      setError("Missing authorization code from Google")
      return
    }

    let cancelled = false

    api
      .get("/auth/google/callback", { params: { code } })
      .then(({ data }) => {
        if (cancelled) return
        completeOAuthLogin(data.access_token, data.user)
        if (data.is_new_user) {
          toast.success("Welcome to AtomQuest! Your account has been created.")
        } else {
          toast.success(`Welcome back, ${data.user.name}`)
        }
        navigate(getDashboardPath(data.user.role), { replace: true })
      })
      .catch((err) => {
        if (cancelled) return
        const detail = err.response?.data?.detail || "Google sign-in failed"
        setError(typeof detail === "string" ? detail : "Google sign-in failed")
        toast.error("Google sign-in failed")
      })

    return () => {
      cancelled = true
    }
  }, [searchParams, completeOAuthLogin, toast, navigate])

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="max-w-md rounded-xl border bg-card p-8 text-center shadow-sm">
          <p className="text-destructive">{error}</p>
          <a href="/login" className="mt-4 inline-block text-sm text-primary underline">
            Back to login
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-muted-foreground">Completing Google sign-in…</p>
    </div>
  )
}
