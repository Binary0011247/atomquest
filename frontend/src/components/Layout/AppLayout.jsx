import { useCallback, useEffect, useRef, useState } from "react"
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom"

import api from "@/api/axios"
import RoleSwitcher from "@/components/RoleSwitcher"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/context/AuthContext"

const NAV_BY_ROLE = {
  employee: [
    { to: "/employee/dashboard", label: "Dashboard", icon: "🏠" },
    { to: "/employee/checkins", label: "Check-ins", icon: "📊" },
    { to: "/employee/progress", label: "My Progress", icon: "📋" },
  ],
  manager: [
    { to: "/manager/dashboard", label: "Dashboard", icon: "🏠" },
    { to: "/manager/dashboard", label: "Team Goals", icon: "👥" },
    { to: "/manager/dashboard", label: "Pending Approvals", icon: "✅" },
    { to: "/manager/checkins", label: "Team Check-ins", icon: "📊" },
    { to: "/manager/team-progress", label: "Team Progress", icon: "📈" },
  ],
  admin: [
    { to: "/admin/dashboard", label: "Dashboard", icon: "🏠" },
    { to: "/admin/users", label: "User Management", icon: "👥" },
    { to: "/admin/analytics", label: "Analytics", icon: "📊" },
    { to: "/admin/reports", label: "Reports", icon: "📋" },
    { to: "/admin/audit-logs", label: "Audit Logs", icon: "🔍" },
    { to: "/admin/cycles", label: "Cycle Management", icon: "⚙️" },
    { to: "/admin/escalations", label: "Escalations", icon: "⚠️", badge: true },
    { to: "/admin/shared-goals", label: "Shared Goals", icon: "🔗" },
  ],
}

const ROLE_BADGE = {
  admin: "bg-red-100 text-red-800",
  manager: "bg-blue-100 text-blue-800",
  employee: "bg-gray-100 text-gray-800",
}

export default function AppLayout() {
  const { logout, user, role } = useAuth()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)
  const [escalationCount, setEscalationCount] = useState(0)
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [bellOpen, setBellOpen] = useState(false)
  const [demoPhase, setDemoPhase] = useState(null)
  const bellRef = useRef(null)
  const nav = NAV_BY_ROLE[role] ?? []

  const loadDemoPhase = useCallback(async () => {
    if (role !== "admin") {
      setDemoPhase(null)
      return
    }
    try {
      const { data } = await api.get("/admin/current-phase")
      setDemoPhase(data)
    } catch {
      setDemoPhase(null)
    }
  }, [role])

  const loadNotifications = useCallback(async () => {
    try {
      const { data } = await api.get("/notifications/my")
      setNotifications(data.notifications ?? [])
      setUnreadCount(data.unread_count ?? 0)
      if (role === "admin") {
        const critical = (data.notifications ?? []).some(
          (n) => n.critical && !n.is_read,
        )
        const esc = (data.notifications ?? []).filter(
          (n) => n.type === "admin_escalation",
        )
        setEscalationCount(esc[0]?.message?.match(/\d+/)?.[0] ?? data.unread_count)
        if (critical) setEscalationCount((c) => Math.max(c, 1))
      }
    } catch {
      setNotifications([])
      setUnreadCount(0)
    }
  }, [role])

  useEffect(() => {
    loadNotifications()
    const interval = setInterval(loadNotifications, 60_000)
    return () => clearInterval(interval)
  }, [loadNotifications])

  useEffect(() => {
    loadDemoPhase()
    const interval = setInterval(loadDemoPhase, 15_000)
    const onPhaseChange = () => loadDemoPhase()
    window.addEventListener("demo-phase-changed", onPhaseChange)
    return () => {
      clearInterval(interval)
      window.removeEventListener("demo-phase-changed", onPhaseChange)
    }
  }, [loadDemoPhase])

  useEffect(() => {
    function handleClickOutside(e) {
      if (bellRef.current && !bellRef.current.contains(e.target)) {
        setBellOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  async function handleMarkAllRead() {
    await api.post("/notifications/mark-read")
    await loadNotifications()
  }

  function handleNotificationClick(item) {
    setBellOpen(false)
    if (item.link) navigate(item.link)
  }

  const hasCritical = notifications.some((n) => n.critical && !n.is_read)
  const showDemoBanner = role === "admin" && demoPhase?.phase_override_active
  const overrideLabel =
    demoPhase?.override_phase === "goal_setting"
      ? "Goal Setting Phase"
      : demoPhase?.override_phase
        ? `${demoPhase.override_phase} Check-in`
        : demoPhase?.label ?? "Demo"

  return (
    <div className="flex min-h-screen flex-col bg-muted/20">
      {showDemoBanner && (
        <div className="border-b border-amber-300 bg-amber-100 px-4 py-2 text-center text-sm font-medium text-amber-900">
          ⚡ Demo Mode Active — Phase overridden to {overrideLabel} | Check-in windows bypassed
        </div>
      )}
      <div className="flex min-h-0 flex-1">
      <aside
        className={`flex shrink-0 flex-col border-r bg-card transition-all ${
          collapsed ? "w-16" : "w-56"
        }`}
      >
        <div className="flex items-center gap-2 border-b p-3">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0"
            onClick={() => setCollapsed((c) => !c)}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? "→" : "←"}
          </Button>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold uppercase tracking-widest text-primary">
                AtomQuest
              </p>
              <p className="truncate text-sm text-muted-foreground capitalize">{role} portal</p>
            </div>
          )}
        </div>
        <nav className="flex-1 space-y-1 p-2">
          {nav.map((item, i) => (
            <NavLink
              key={`${item.to}-${item.label}-${i}`}
              to={item.to}
              end={item.label === "Dashboard"}
              title={item.label}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`
              }
            >
              <span className="text-base">{item.icon}</span>
              {!collapsed && <span className="flex-1">{item.label}</span>}
              {!collapsed && item.badge && escalationCount > 0 && (
                <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1.5 text-xs font-bold text-white">
                  {escalationCount > 99 ? "99+" : escalationCount}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        {!collapsed && user && (
          <footer className="border-t p-3">
            <p className="truncate text-sm font-medium">{user.name}</p>
            <span
              className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${ROLE_BADGE[role] ?? ""}`}
            >
              {role}
            </span>
            <p className="mt-2 text-xs text-muted-foreground">
              Logged in as: {user.name}
            </p>
          </footer>
        )}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b bg-card px-6 py-3">
          <p className="text-lg font-bold tracking-tight">⚡ AtomQuest</p>
          <div className="flex items-center gap-3">
            <div className="relative" ref={bellRef}>
              <button
                type="button"
                onClick={() => setBellOpen((o) => !o)}
                className="relative rounded-md p-2 text-lg hover:bg-muted"
                aria-label="Notifications"
              >
                🔔
                {unreadCount > 0 && (
                  <span
                    className={`absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-bold text-white ${
                      hasCritical ? "bg-red-600" : "bg-orange-500"
                    }`}
                  >
                    {unreadCount > 9 ? "9+" : unreadCount}
                  </span>
                )}
              </button>
              {bellOpen && (
                <div className="absolute right-0 z-50 mt-2 w-80 rounded-lg border bg-card shadow-lg">
                  <div className="flex items-center justify-between border-b px-4 py-3">
                    <p className="text-sm font-semibold">Notifications</p>
                    {unreadCount > 0 && (
                      <button
                        type="button"
                        onClick={handleMarkAllRead}
                        className="text-xs text-primary hover:underline"
                      >
                        Mark all read
                      </button>
                    )}
                  </div>
                  <div className="max-h-80 overflow-y-auto">
                    {notifications.length === 0 ? (
                      <p className="px-4 py-6 text-center text-sm text-muted-foreground">
                        No notifications
                      </p>
                    ) : (
                      notifications.map((n) => (
                        <button
                          key={`${n.id}-${n.type}-${n.created_at}`}
                          type="button"
                          onClick={() => handleNotificationClick(n)}
                          className={`block w-full border-b px-4 py-3 text-left text-sm transition-colors hover:bg-muted/50 ${
                            !n.is_read ? "bg-primary/5" : ""
                          }`}
                        >
                          <p
                            className={`font-medium ${n.critical ? "text-red-600" : ""}`}
                          >
                            {n.message}
                          </p>
                          <p className="mt-1 text-xs text-muted-foreground capitalize">
                            {n.type.replace(/_/g, " ")}
                          </p>
                        </button>
                      ))
                    )}
                  </div>
                  {role === "admin" && (
                    <div className="border-t p-2">
                      <Link
                        to="/admin/escalations"
                        className="block rounded-md px-3 py-2 text-center text-xs text-primary hover:bg-muted"
                        onClick={() => setBellOpen(false)}
                      >
                        View all escalations →
                      </Link>
                    </div>
                  )}
                </div>
              )}
            </div>
            <span className="text-sm font-medium">{user?.name}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${ROLE_BADGE[role] ?? ""}`}
            >
              {role}
            </span>
            <Button variant="outline" size="sm" onClick={logout}>
              Log out
            </Button>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>

      <RoleSwitcher />
      </div>
    </div>
  )
}
