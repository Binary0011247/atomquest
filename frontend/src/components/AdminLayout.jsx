import { NavLink, Outlet } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { useAuth } from "@/context/AuthContext"

const NAV = [
  { to: "/admin/dashboard", label: "Dashboard" },
  { to: "/admin/users", label: "Users" },
  { to: "/admin/reports", label: "Reports" },
  { to: "/admin/audit-logs", label: "Audit Logs" },
  { to: "/admin/cycles", label: "Cycles" },
]

export default function AdminLayout() {
  const { logout, user } = useAuth()

  return (
    <div className="flex min-h-screen bg-muted/20">
      <aside className="flex w-56 shrink-0 flex-col border-r bg-card">
        <div className="border-b p-4">
          <p className="text-xs font-semibold uppercase tracking-widest text-primary">AtomQuest</p>
          <p className="text-sm font-medium">Admin Panel</p>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t p-4">
          <p className="mb-2 truncate text-xs text-muted-foreground">{user?.email}</p>
          <Button variant="outline" size="sm" className="w-full" onClick={logout}>
            Log out
          </Button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  )
}
