import { useEffect, useMemo, useState } from "react"
import api from "@/api/axios"
import { Button } from "@/components/ui/button"
import { useToast } from "@/context/ToastContext"
import usePageTitle from "@/hooks/usePageTitle"

const THRUST_AREAS = [
  "Sales",
  "Operations",
  "Safety",
  "HR",
  "Finance",
  "Technology",
  "Customer Service",
]

const UOM_OPTIONS = [
  { value: "numeric_min", icon: "📈", label: "Numeric Min", desc: "Higher is better" },
  { value: "numeric_max", icon: "📉", label: "Numeric Max", desc: "Lower is better" },
  { value: "timeline", icon: "📅", label: "Timeline", desc: "Completion by target date" },
  { value: "zero", icon: "🎯", label: "Zero Based", desc: "Zero = success" },
]

const QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

function formatTarget(goal) {
  if (goal.uom_type === "timeline" && goal.target_date) return goal.target_date
  if (goal.uom_type === "zero") return "Zero = success"
  if (goal.target_value != null) return String(goal.target_value)
  return "—"
}

function formatApiError(detail) {
  if (!detail) return null
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || d.detail || JSON.stringify(d)).join("; ")
  }
  if (typeof detail === "string") return detail
  return detail.msg || detail.detail || String(detail)
}

export default function SharedGoalsPage() {
  usePageTitle("Shared Goals")
  const toast = useToast()
  const [loading, setLoading] = useState(true)
  const [parents, setParents] = useState([])
  const [employees, setEmployees] = useState([])
  const [managers, setManagers] = useState([])
  const [managerFilter, setManagerFilter] = useState("")
  const [syncModal, setSyncModal] = useState(null)
  const [pushing, setPushing] = useState(false)
  const [form, setForm] = useState({
    thrust_area: "",
    title: "",
    description: "",
    uom_type: "numeric_min",
    target_value: "",
    target_date: "",
    recipient_employee_ids: [],
    default_weightage: 10,
  })

  useEffect(() => {
    load()
    loadEmployees()
  }, [])

  async function load() {
    setLoading(true)
    try {
      const { data } = await api.get("/admin/shared-goals")
      setParents(data)
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Failed to load shared goals")
    } finally {
      setLoading(false)
    }
  }

  async function loadEmployees() {
    try {
      const { data } = await api.get("/admin/users")
      const all = data ?? []
      setEmployees(all.filter((u) => u.role === "employee"))
      setManagers(all.filter((u) => u.role === "manager"))
    } catch {
      setEmployees([])
      setManagers([])
    }
  }

  const filteredEmployees = useMemo(() => {
    if (!managerFilter) return employees
    return employees.filter((e) => String(e.manager_id) === managerFilter)
  }, [employees, managerFilter])

  async function push() {
    if (!form.thrust_area || !form.title) {
      toast.error("Thrust area and title are required")
      return
    }
    if (form.recipient_employee_ids.length === 0) {
      toast.error("Select at least one employee")
      return
    }
    setPushing(true)
    try {
      const payload = {
        thrust_area: form.thrust_area,
        title: form.title,
        description: form.description || null,
        uom_type: form.uom_type,
        target_value: form.target_value === "" ? null : Number(form.target_value),
        target_date: form.target_date === "" ? null : form.target_date,
        recipient_employee_ids: form.recipient_employee_ids,
        default_weightage: form.default_weightage,
      }
      const { data } = await api.post("/admin/shared-goals/push", payload)
      toast.success(`Goal pushed to ${data.pushed_to_count} employees`)
      setForm({
        thrust_area: "",
        title: "",
        description: "",
        uom_type: "numeric_min",
        target_value: "",
        target_date: "",
        recipient_employee_ids: [],
        default_weightage: 10,
      })
      await load()
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Failed to push shared goal")
    } finally {
      setPushing(false)
    }
  }

  function toggleRecipient(id) {
    setForm((f) => {
      const set = new Set(f.recipient_employee_ids)
      if (set.has(id)) set.delete(id)
      else set.add(id)
      return { ...f, recipient_employee_ids: Array.from(set) }
    })
  }

  function selectAllFiltered() {
    setForm((f) => ({
      ...f,
      recipient_employee_ids: filteredEmployees.map((e) => e.id),
    }))
  }

  function clearRecipients() {
    setForm((f) => ({ ...f, recipient_employee_ids: [] }))
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">🔗 Shared Goals</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Push organization-wide goals to multiple employees. Check-ins sync from the primary owner.
        </p>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <section className="rounded-xl border bg-card p-6 shadow-sm">
          <h2 className="text-lg font-semibold">Push New Shared Goal</h2>
          <div className="mt-4 space-y-4">
            <label className="block text-sm font-medium">
              Thrust Area
              <select
                className="mt-1 w-full rounded-md border px-3 py-2"
                value={form.thrust_area}
                onChange={(e) => setForm({ ...form, thrust_area: e.target.value })}
              >
                <option value="">Select thrust area</option>
                {THRUST_AREAS.map((area) => (
                  <option key={area} value={area}>
                    {area}
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-sm font-medium">
              Goal Title
              <input
                className="mt-1 w-full rounded-md border px-3 py-2"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="Goal title"
              />
            </label>

            <label className="block text-sm font-medium">
              Description
              <textarea
                className="mt-1 w-full rounded-md border px-3 py-2"
                rows={2}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </label>

            <div>
              <p className="text-sm font-medium">Unit of Measurement</p>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {UOM_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setForm({ ...form, uom_type: opt.value })}
                    className={`rounded-lg border p-3 text-left transition-colors ${
                      form.uom_type === opt.value
                        ? "border-primary bg-primary/5 ring-2 ring-primary/30"
                        : "hover:bg-muted/50"
                    }`}
                  >
                    <span className="text-lg">{opt.icon}</span>
                    <p className="mt-1 text-sm font-medium">{opt.label}</p>
                    <p className="text-xs text-muted-foreground">{opt.desc}</p>
                  </button>
                ))}
              </div>
            </div>

            {(form.uom_type === "numeric_min" || form.uom_type === "numeric_max") && (
              <label className="block text-sm font-medium">
                Target Value
                <input
                  type="number"
                  className="mt-1 w-full rounded-md border px-3 py-2"
                  value={form.target_value}
                  onChange={(e) => setForm({ ...form, target_value: e.target.value })}
                />
              </label>
            )}
            {form.uom_type === "timeline" && (
              <label className="block text-sm font-medium">
                Target Date
                <input
                  type="date"
                  className="mt-1 w-full rounded-md border px-3 py-2"
                  value={form.target_date}
                  onChange={(e) => setForm({ ...form, target_date: e.target.value })}
                />
              </label>
            )}

            <label className="block text-sm font-medium">
              Default Weightage (%)
              <input
                type="number"
                min={10}
                max={100}
                className="mt-1 w-full rounded-md border px-3 py-2"
                value={form.default_weightage}
                onChange={(e) =>
                  setForm({ ...form, default_weightage: Number(e.target.value) })
                }
              />
            </label>

            <div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium">
                  Recipients ({form.recipient_employee_ids.length} selected)
                </p>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" size="sm" onClick={selectAllFiltered}>
                    Select All
                  </Button>
                  <Button type="button" variant="ghost" size="sm" onClick={clearRecipients}>
                    Clear
                  </Button>
                </div>
              </div>
              <select
                className="mt-2 w-full rounded-md border px-3 py-2 text-sm"
                value={managerFilter}
                onChange={(e) => setManagerFilter(e.target.value)}
              >
                <option value="">All managers</option>
                {managers.map((m) => (
                  <option key={m.id} value={String(m.id)}>
                    {m.name}
                  </option>
                ))}
              </select>
              <div className="mt-2 max-h-48 overflow-y-auto rounded-md border p-2">
                {filteredEmployees.map((e) => (
                  <label key={e.id} className="flex cursor-pointer items-center gap-2 py-1 text-sm">
                    <input
                      type="checkbox"
                      checked={form.recipient_employee_ids.includes(e.id)}
                      onChange={() => toggleRecipient(e.id)}
                    />
                    {e.name}
                    {e.manager_name && (
                      <span className="text-xs text-muted-foreground">({e.manager_name})</span>
                    )}
                  </label>
                ))}
              </div>
            </div>

            <Button onClick={push} disabled={pushing} className="w-full">
              {pushing ? "Pushing..." : "Push Shared Goal"}
            </Button>
          </div>
        </section>

        <section className="rounded-xl border bg-card p-6 shadow-sm lg:col-span-2">
          <h2 className="text-lg font-semibold">Existing Shared Goals</h2>
          {loading ? (
            <p className="mt-4 text-sm text-muted-foreground">Loading...</p>
          ) : parents.length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">No shared goals pushed yet.</p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">Goal Title</th>
                    <th className="py-2 pr-4 font-medium">Thrust Area</th>
                    <th className="py-2 pr-4 font-medium">Target</th>
                    <th className="py-2 pr-4 font-medium">Recipients</th>
                    <th className="py-2 pr-4 font-medium">Created By</th>
                    <th className="py-2 font-medium">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {parents.map((p) => (
                    <SharedGoalTableRow
                      key={p.parent_goal.id}
                      item={p}
                      onViewSync={() => setSyncModal(p)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {syncModal && <SyncStatusModal item={syncModal} onClose={() => setSyncModal(null)} />}
    </div>
  )
}

function SharedGoalTableRow({ item, onViewSync }) {
  const [open, setOpen] = useState(false)
  const g = item.parent_goal
  const created = g.created_at ? new Date(g.created_at).toLocaleDateString() : "—"

  return (
    <>
      <tr className="border-b align-top">
        <td className="py-3 pr-4">
          <button
            type="button"
            className="font-medium text-primary hover:underline"
            onClick={() => setOpen((o) => !o)}
          >
            {open ? "▼" : "▶"} {g.title}
          </button>
        </td>
        <td className="py-3 pr-4">{g.thrust_area}</td>
        <td className="py-3 pr-4">{formatTarget(g)}</td>
        <td className="py-3 pr-4">{item.total_recipients}</td>
        <td className="py-3 pr-4">{item.created_by_name}</td>
        <td className="py-3">{created}</td>
      </tr>
      {open && (
        <tr className="border-b bg-muted/30">
          <td colSpan={6} className="px-4 py-3">
            <div className="space-y-2">
              {item.recipients.map((r) => (
                <div
                  key={r.employee_id}
                  className="flex flex-wrap items-center justify-between gap-2 text-sm"
                >
                  <span>{r.employee_name}</span>
                  <span className="text-muted-foreground">{r.custom_weightage}% weightage</span>
                </div>
              ))}
              <Button type="button" variant="outline" size="sm" onClick={onViewSync}>
                View Sync Status
              </Button>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function SyncStatusModal({ item, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-xl border bg-card p-6 shadow-lg">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold">Sync Status</h3>
            <p className="text-sm text-muted-foreground">{item.parent_goal.title}</p>
          </div>
        </div>
        <ul className="mt-4 space-y-3">
          {item.recipients.map((r) => {
            const logged = r.quarters_with_checkins?.length > 0
            return (
              <li key={r.employee_id} className="rounded-lg border p-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{r.employee_name}</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      logged ? "bg-green-100 text-green-800" : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {logged ? "Has check-ins" : "No check-ins yet"}
                  </span>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">
                  Quarters logged: {logged ? r.quarters_with_checkins.join(", ") : "None"}
                  {!logged && (
                    <span className="mt-1 block">
                      Missing:{" "}
                      {QUARTERS.filter((q) => !r.quarters_with_checkins?.includes(q)).join(", ")}
                    </span>
                  )}
                </p>
              </li>
            )
          })}
        </ul>
        <Button className="mt-6 w-full" variant="outline" onClick={onClose}>
          Close
        </Button>
      </div>
    </div>
  )
}
