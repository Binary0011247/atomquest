import { useCallback, useEffect, useState } from "react"

import api from "@/api/axios"
import { Button } from "@/components/ui/button"
import usePageTitle from "@/hooks/usePageTitle"

const emptyForm = {
  cycle_year: new Date().getFullYear(),
  goal_setting_start: "",
  q1_checkin_start: "",
  q2_checkin_start: "",
  q3_checkin_start: "",
  q4_checkin_start: "",
}

export default function CycleManagementPage() {
  usePageTitle("Cycle Management")
  const [cycles, setCycles] = useState([])
  const [showCreate, setShowCreate] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [message, setMessage] = useState("")

  const load = useCallback(async () => {
    const { data } = await api.get("/admin/cycles")
    setCycles(data)
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const active = cycles.find((c) => c.is_active)

  async function createCycle(e) {
    e.preventDefault()
    try {
      await api.post("/admin/cycles", { ...form, is_active: true })
      setShowCreate(false)
      setForm(emptyForm)
      setMessage("Cycle created and activated")
      load()
    } catch (err) {
      setMessage(err.response?.data?.detail ?? "Failed to create cycle")
    }
  }

  function openEdit(cycle) {
    setEditing(cycle)
    setForm({
      cycle_year: cycle.cycle_year,
      goal_setting_start: cycle.goal_setting_start,
      q1_checkin_start: cycle.q1_checkin_start,
      q2_checkin_start: cycle.q2_checkin_start,
      q3_checkin_start: cycle.q3_checkin_start,
      q4_checkin_start: cycle.q4_checkin_start,
    })
  }

  async function saveEdit(e) {
    e.preventDefault()
    if (!editing) return
    try {
      await api.put(`/admin/cycles/${editing.id}`, {
        goal_setting_start: form.goal_setting_start,
        q1_checkin_start: form.q1_checkin_start,
        q2_checkin_start: form.q2_checkin_start,
        q3_checkin_start: form.q3_checkin_start,
        q4_checkin_start: form.q4_checkin_start,
      })
      setEditing(null)
      setForm(emptyForm)
      setMessage("Cycle dates updated")
      load()
    } catch (err) {
      setMessage(err.response?.data?.detail ?? "Failed to update cycle")
    }
  }

  async function activate(id) {
    try {
      await api.put(`/admin/cycles/${id}/activate`)
      setMessage("Cycle activated")
      load()
    } catch (err) {
      setMessage(err.response?.data?.detail ?? "Activation failed")
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Cycle Management</h1>
        <Button onClick={() => setShowCreate(true)}>Create New Cycle</Button>
      </div>

      {message && (
        <p className="rounded-md border border-green-200 bg-green-50 px-4 py-2 text-sm">{message}</p>
      )}

      {active && (
        <div className="rounded-xl border-2 border-primary bg-card p-6">
          <div className="mb-4 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold">Active Cycle — {active.cycle_year}</h2>
              <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-800">Active</span>
            </div>
            <Button size="sm" variant="outline" onClick={() => openEdit(active)}>
              Edit
            </Button>
          </div>
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">Goal setting start</dt>
              <dd className="font-medium">{active.goal_setting_start}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Q1 check-in start</dt>
              <dd className="font-medium">{active.q1_checkin_start}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Q2 check-in start</dt>
              <dd className="font-medium">{active.q2_checkin_start}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Q3 check-in start</dt>
              <dd className="font-medium">{active.q3_checkin_start}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Q4 check-in start</dt>
              <dd className="font-medium">{active.q4_checkin_start}</dd>
            </div>
          </dl>
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border bg-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50 text-left">
              <th className="p-3">Year</th>
              <th className="p-3">Goal Setting</th>
              <th className="p-3">Q1</th>
              <th className="p-3">Q2</th>
              <th className="p-3">Q3</th>
              <th className="p-3">Q4</th>
              <th className="p-3">Status</th>
              <th className="p-3">Action</th>
            </tr>
          </thead>
          <tbody>
            {cycles.map((c) => (
              <tr key={c.id} className="border-b">
                <td className="p-3 font-medium">{c.cycle_year}</td>
                <td className="p-3">{c.goal_setting_start}</td>
                <td className="p-3">{c.q1_checkin_start}</td>
                <td className="p-3">{c.q2_checkin_start}</td>
                <td className="p-3">{c.q3_checkin_start}</td>
                <td className="p-3">{c.q4_checkin_start}</td>
                <td className="p-3">{c.is_active ? "Active" : "Inactive"}</td>
                <td className="p-3">
                  {!c.is_active && (
                    <Button size="sm" variant="outline" onClick={() => activate(c.id)}>
                      Activate
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <form onSubmit={saveEdit} className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold">Edit Cycle {editing.cycle_year}</h2>
            <div className="space-y-3">
              {[
                ["goal_setting_start", "Goal Setting Start"],
                ["q1_checkin_start", "Q1 Check-in Start"],
                ["q2_checkin_start", "Q2 Check-in Start"],
                ["q3_checkin_start", "Q3 Check-in Start"],
                ["q4_checkin_start", "Q4 Check-in Start"],
              ].map(([key, label]) => (
                <label key={key} className="block text-sm">
                  {label}
                  <input
                    type="date"
                    required
                    className="mt-1 w-full rounded-md border px-3 py-2"
                    value={form[key]}
                    onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                  />
                </label>
              ))}
            </div>
            <div className="mt-4 flex gap-2">
              <Button
                type="button"
                variant="outline"
                className="flex-1"
                onClick={() => {
                  setEditing(null)
                  setForm(emptyForm)
                }}
              >
                Cancel
              </Button>
              <Button type="submit" className="flex-1">
                Save
              </Button>
            </div>
          </form>
        </div>
      )}

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <form onSubmit={createCycle} className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold">Create Cycle</h2>
            <div className="space-y-3">
              <label className="block text-sm">
                Year
                <input
                  type="number"
                  required
                  className="mt-1 w-full rounded-md border px-3 py-2"
                  value={form.cycle_year}
                  onChange={(e) => setForm((f) => ({ ...f, cycle_year: Number(e.target.value) }))}
                />
              </label>
              {[
                ["goal_setting_start", "Goal Setting Start"],
                ["q1_checkin_start", "Q1 Check-in Start"],
                ["q2_checkin_start", "Q2 Check-in Start"],
                ["q3_checkin_start", "Q3 Check-in Start"],
                ["q4_checkin_start", "Q4 Check-in Start"],
              ].map(([key, label]) => (
                <label key={key} className="block text-sm">
                  {label}
                  <input
                    type="date"
                    required
                    className="mt-1 w-full rounded-md border px-3 py-2"
                    value={form[key]}
                    onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                  />
                </label>
              ))}
            </div>
            <div className="mt-4 flex gap-2">
              <Button type="button" variant="outline" className="flex-1" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
              <Button type="submit" className="flex-1">
                Create
              </Button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
