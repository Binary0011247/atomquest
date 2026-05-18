import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"

import ButtonSpinner from "@/components/ButtonSpinner"
import { getDashboardPath, useAuth } from "@/context/AuthContext"
import { useToast } from "@/context/ToastContext"

const ROLES = [
  {
    role: "employee",
    icon: "👤",
    label: "Employee",
    name: "Priya Employee",
    email: "priya@atomquest.com",
    password: "emp123",
  },
  {
    role: "manager",
    icon: "👥",
    label: "Manager",
    name: "Meera Manager",
    email: "manager@atomquest.com",
    password: "manager123",
  },
  {
    role: "admin",
    icon: "⚙️",
    label: "Admin",
    name: "Aryan Admin",
    email: "admin@atomquest.com",
    password: "admin123",
  },
]

const ROLE_ICON = { employee: "👤", manager: "👥", admin: "⚙️" }

export default function RoleSwitcher() {
  const { role, login } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [switching, setSwitching] = useState(false)
  const panelRef = useRef(null)

  useEffect(() => {
    function onClickOutside(e) {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener("mousedown", onClickOutside)
    return () => document.removeEventListener("mousedown", onClickOutside)
  }, [open])

  useEffect(() => {
    function onKeyDown(e) {
      if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "r") {
        e.preventDefault()
        setOpen((o) => !o)
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [])

  async function switchTo(item) {
    if (switching) return
    if (item.role === role) {
      setOpen(false)
      return
    }
    setSwitching(true)
    try {
      await login(item.email, item.password)
      toast.success(`Switched to ${item.label} view`)
      navigate(getDashboardPath(item.role))
      setOpen(false)
    } catch {
      toast.error(`Could not switch to ${item.label}. Run seed API first.`)
    } finally {
      setSwitching(false)
    }
  }

  return (
    <div ref={panelRef} className="fixed bottom-6 right-6 z-[9999]">
      {open && (
        <div className="mb-3 w-72 rounded-xl border bg-card p-4 shadow-xl">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold">Switch Demo Role</h3>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="text-muted-foreground hover:text-foreground"
            >
              ✕
            </button>
          </div>
          <div className="space-y-2">
            {ROLES.map((item) => (
              <button
                key={item.role}
                type="button"
                disabled={switching}
                onClick={() => switchTo(item)}
                className={`w-full rounded-lg border p-3 text-left transition-colors hover:bg-muted/50 ${
                  role === item.role ? "border-primary ring-1 ring-primary" : ""
                }`}
              >
                <p className="font-medium">
                  {item.icon} {item.label}
                </p>
                <p className="text-sm text-muted-foreground">{item.name}</p>
                <p className="text-xs text-muted-foreground">{item.email}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      <p className="mb-2 text-center text-[10px] text-muted-foreground">
        Press Ctrl+Shift+R to switch roles
      </p>
      <button
        type="button"
        disabled={switching}
        onClick={() => setOpen((o) => !o)}
        className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-primary text-2xl text-primary-foreground shadow-lg transition-transform hover:scale-105 disabled:opacity-60"
        title="Switch demo role (Ctrl+Shift+R)"
      >
        {switching ? <ButtonSpinner className="h-6 w-6" /> : ROLE_ICON[role] ?? "👤"}
      </button>
    </div>
  )
}
