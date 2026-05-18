import { useCallback, useEffect, useState } from "react"

import api from "@/api/axios"
import { Button } from "@/components/ui/button"
import usePageTitle from "@/hooks/usePageTitle"

const ROLE_STYLES = {
  admin: "bg-red-100 text-red-800",
  manager: "bg-blue-100 text-blue-800",
  employee: "bg-gray-100 text-gray-700",
}

export default function UserManagementPage() {
  usePageTitle("User Management")
  const [users, setUsers] = useState([])
  const [managers, setManagers] = useState([])
  const [lockedGoals, setLockedGoals] = useState([])
  const [unlockSearch, setUnlockSearch] = useState("")
  const [showAdd, setShowAdd] = useState(false)
  const [editUser, setEditUser] = useState(null)
  const [unlockGoal, setUnlockGoal] = useState(null)
  const [unlockReason, setUnlockReason] = useState("")
  const [message, setMessage] = useState("")
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    role: "employee",
    manager_id: "",
  })

  const load = useCallback(async () => {
    const [u, l] = await Promise.all([
      api.get("/admin/users"),
      api.get("/admin/goals/locked", { params: unlockSearch ? { search: unlockSearch } : {} }),
    ])
    setUsers(u.data)
    setManagers(u.data.filter((x) => x.role === "manager"))
    setLockedGoals(l.data)
  }, [unlockSearch])

  useEffect(() => {
    load()
  }, [load])

  async function createUser(e) {
    e.preventDefault()
    setMessage("")
    try {
      await api.post("/admin/users", {
        ...form,
        manager_id: form.role === "employee" && form.manager_id ? Number(form.manager_id) : null,
      })
      setShowAdd(false)
      setForm({ name: "", email: "", password: "", role: "employee", manager_id: "" })
      setMessage("User created successfully")
      load()
    } catch (err) {
      setMessage(err.response?.data?.detail ?? "Failed to create user")
    }
  }

  async function saveEdit(e) {
    e.preventDefault()
    try {
      await api.put(`/admin/users/${editUser.id}`, {
        name: editUser.name,
        email: editUser.email,
        role: editUser.role,
        manager_id: editUser.manager_id || null,
        is_active: editUser.is_active,
      })
      setEditUser(null)
      setMessage("User updated")
      load()
    } catch (err) {
      setMessage(err.response?.data?.detail ?? "Update failed")
    }
  }

  async function submitUnlock() {
    if (!unlockGoal || !unlockReason.trim()) return
    try {
      await api.post(`/admin/goals/unlock/${unlockGoal.goal_id}`, { reason: unlockReason })
      setUnlockGoal(null)
      setUnlockReason("")
      setMessage("Goal unlocked — employee must resubmit for approval")
      load()
    } catch (err) {
      setMessage(err.response?.data?.detail ?? "Unlock failed")
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">User Management</h1>
        <Button onClick={() => setShowAdd(true)}>Add User</Button>
      </div>

      {message && (
        <p className="rounded-md border border-green-200 bg-green-50 px-4 py-2 text-sm text-green-800">
          {message}
        </p>
      )}

      <div className="overflow-x-auto rounded-xl border bg-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50 text-left">
              <th className="p-3">Name</th>
              <th className="p-3">Email</th>
              <th className="p-3">Role</th>
              <th className="p-3">Manager</th>
              <th className="p-3">Goals</th>
              <th className="p-3">Status</th>
              <th className="p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b">
                <td className="p-3">{u.name}</td>
                <td className="p-3">{u.email}</td>
                <td className="p-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${ROLE_STYLES[u.role]}`}>
                    {u.role}
                  </span>
                </td>
                <td className="p-3">{u.manager_name ?? "—"}</td>
                <td className="p-3">{u.goal_count}</td>
                <td className="p-3">{u.submission_status}</td>
                <td className="p-3">
                  <Button size="sm" variant="outline" onClick={() => setEditUser({ ...u })}>
                    Edit
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <section>
        <h2 className="mb-4 text-lg font-semibold">Unlock Locked Goals</h2>
        <input
          type="search"
          placeholder="Search by employee or goal title..."
          className="mb-4 w-full max-w-md rounded-md border px-3 py-2 text-sm"
          value={unlockSearch}
          onChange={(e) => setUnlockSearch(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load()}
        />
        <div className="space-y-2">
          {lockedGoals.map((g) => (
            <div
              key={g.goal_id}
              className="flex items-center justify-between rounded-lg border bg-card p-4"
            >
              <div>
                <p className="font-medium">{g.title}</p>
                <p className="text-sm text-muted-foreground">
                  {g.employee_name} · {g.employee_email}
                </p>
              </div>
              <Button size="sm" variant="destructive" onClick={() => setUnlockGoal(g)}>
                Unlock
              </Button>
            </div>
          ))}
        </div>
      </section>

      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <form onSubmit={createUser} className="w-full max-w-md rounded-xl border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold">Add User</h2>
            <div className="space-y-3">
              <input
                required
                placeholder="Name"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
              <input
                required
                type="email"
                placeholder="Email"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              />
              <input
                required
                type="password"
                placeholder="Password"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              />
              <select
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={form.role}
                onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
              >
                <option value="employee">Employee</option>
                <option value="manager">Manager</option>
                <option value="admin">Admin</option>
              </select>
              {form.role === "employee" && (
                <select
                  className="w-full rounded-md border px-3 py-2 text-sm"
                  value={form.manager_id}
                  onChange={(e) => setForm((f) => ({ ...f, manager_id: e.target.value }))}
                >
                  <option value="">Select manager</option>
                  {managers.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              )}
            </div>
            <div className="mt-4 flex gap-2">
              <Button type="button" variant="outline" className="flex-1" onClick={() => setShowAdd(false)}>
                Cancel
              </Button>
              <Button type="submit" className="flex-1">
                Create
              </Button>
            </div>
          </form>
        </div>
      )}

      {editUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <form onSubmit={saveEdit} className="w-full max-w-md rounded-xl border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold">Edit User</h2>
            <div className="space-y-3">
              <input
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={editUser.name}
                onChange={(e) => setEditUser((u) => ({ ...u, name: e.target.value }))}
              />
              <input
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={editUser.email}
                onChange={(e) => setEditUser((u) => ({ ...u, email: e.target.value }))}
              />
              <select
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={editUser.role}
                onChange={(e) => setEditUser((u) => ({ ...u, role: e.target.value }))}
              >
                <option value="employee">Employee</option>
                <option value="manager">Manager</option>
                <option value="admin">Admin</option>
              </select>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={editUser.is_active}
                  onChange={(e) => setEditUser((u) => ({ ...u, is_active: e.target.checked }))}
                />
                Active
              </label>
            </div>
            <div className="mt-4 flex gap-2">
              <Button type="button" variant="outline" className="flex-1" onClick={() => setEditUser(null)}>
                Cancel
              </Button>
              <Button type="submit" className="flex-1">
                Save
              </Button>
            </div>
          </form>
        </div>
      )}

      {unlockGoal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl border bg-card p-6">
            <h2 className="mb-2 text-lg font-semibold">Unlock Goal</h2>
            <p className="mb-4 text-sm text-muted-foreground">{unlockGoal.title}</p>
            <textarea
              className="w-full rounded-md border px-3 py-2 text-sm"
              rows={3}
              placeholder="Reason for unlock (required)"
              value={unlockReason}
              onChange={(e) => setUnlockReason(e.target.value)}
            />
            <div className="mt-4 flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => setUnlockGoal(null)}>
                Cancel
              </Button>
              <Button
                className="flex-1"
                disabled={!unlockReason.trim()}
                onClick={submitUnlock}
              >
                Unlock
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
