import { Link, Outlet } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { useAuth } from "@/context/AuthContext"

export default function AppLayout() {
  const { logout, user } = useAuth()

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <Link to="/" className="text-lg font-semibold tracking-tight">
            AtomQuest Goal Portal
          </Link>
          <div className="flex items-center gap-3">
            {user?.email && (
              <span className="text-sm text-muted-foreground">{user.email}</span>
            )}
            <Button variant="outline" size="sm" onClick={logout}>
              Log out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
