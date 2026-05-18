import { useEffect, useRef, useState } from "react"
import { Navigate, useNavigate } from "react-router-dom"

import api from "@/api/axios"
import { Button } from "@/components/ui/button"
import { getDashboardPath, useAuth } from "@/context/AuthContext"
import { useToast } from "@/context/ToastContext"
import usePageTitle from "@/hooks/usePageTitle"

export default function Login() {
  usePageTitle("Login")
  const navigate = useNavigate()
  const toast = useToast()
  const { login, isAuthenticated, loading, role } = useAuth()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const emailRef = useRef(null)

  useEffect(() => {
    emailRef.current?.focus()
    const params = new URLSearchParams(window.location.search)
    if (params.get("expired") === "1") {
      setError("Your session expired. Please login again.")
    }
  }, [])

  if (!loading && isAuthenticated) {
    return <Navigate to={getDashboardPath(role)} replace />
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (submitting) return
    setError("")
    setSubmitting(true)

    try {
      const user = await login(email, password)
      toast.success(`Welcome back, ${user.name}`)
      navigate(getDashboardPath(user.role))
    } catch {
      setError("Invalid email or password")
      toast.error("Invalid email or password")
    } finally {
      setSubmitting(false)
    }
  }

  async function handleGoogleLogin() {
    setGoogleLoading(true)
    setError("")
    try {
      const { data } = await api.get("/auth/google/login")
      window.location.href = data.auth_url
    } catch {
      setError("Google sign-in is not available")
      toast.error("Google sign-in is not configured")
      setGoogleLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
      <div className="w-full max-w-md rounded-xl border bg-card p-8 shadow-sm">
        <div className="mb-8 space-y-2 text-center">
          <p className="text-xs font-semibold uppercase tracking-widest text-primary">
            AtomQuest
          </p>
          <h1 className="text-2xl font-semibold tracking-tight">Goal Portal</h1>
          <p className="text-sm text-muted-foreground">Sign in to continue</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="email" className="text-sm font-medium">
              Email
            </label>
            <input
              ref={emailRef}
              id="email"
              type="email"
              autoComplete="email"
              autoFocus
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="you@atomquest.com"
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className="text-sm font-medium">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSubmit(e)
              }}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="••••••••"
            />
          </div>

          {error && (
            <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}

          <Button type="submit" className="w-full" disabled={submitting || googleLoading}>
            {submitting ? (
              <span className="inline-flex items-center gap-2">
                <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                Signing in...
              </span>
            ) : (
              "Sign in"
            )}
          </Button>
        </form>

        <div className="my-6 flex items-center gap-3">
          <div className="h-px flex-1 bg-border" />
          <span className="text-xs text-muted-foreground">or</span>
          <div className="h-px flex-1 bg-border" />
        </div>

        <Button
          type="button"
          variant="outline"
          className="w-full gap-2 bg-white"
          disabled={googleLoading || submitting}
          onClick={handleGoogleLogin}
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24" aria-hidden>
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          {googleLoading ? "Redirecting…" : "Continue with Google"}
        </Button>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Demo: admin@atomquest.com / admin123
        </p>
      </div>
    </div>
  )
}
