import { useCallback, useEffect, useMemo, useState } from "react"
import { Link, useNavigate } from "react-router-dom"

import api, { setDemoMode } from "@/api/axios"
import ButtonSpinner from "@/components/ButtonSpinner"
import LoadingSpinner from "@/components/LoadingSpinner"
import { Button } from "@/components/ui/button"
import { useToast } from "@/context/ToastContext"
import { useAuth } from "@/context/AuthContext"
import usePageTitle from "@/hooks/usePageTitle"

const PHASE_OPTIONS = [
  { value: "goal_setting", label: "Goal Setting Phase (May-June)" },
  { value: "Q1", label: "Q1 Check-in (July-Sept)" },
  { value: "Q2", label: "Q2 Check-in (Oct-Dec)" },
  { value: "Q3", label: "Q3 Check-in (Jan-Mar)" },
  { value: "Q4", label: "Q4 Check-in (Mar-Apr)" },
]

function StatCard({ label, value }) {
  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  )
}

function entityDotColor(entity) {
  if (entity === "goal") return "bg-blue-500"
  if (entity === "checkin") return "bg-purple-500"
  if (entity === "admin") return "bg-red-500"
  if (entity === "user") return "bg-gray-400"
  return "bg-gray-300"
}

function rowClass(emp) {
  if (emp.has_approved_goals && emp.q1_done && emp.q2_done && emp.q3_done && emp.q4_done) {
    return "bg-green-50"
  }
  if (!emp.has_created_goals) return "bg-red-50"
  return "bg-yellow-50"
}

function CellIcon({ done }) {
  return <span className={done ? "text-green-600" : "text-red-400"}>{done ? "✅" : "❌"}</span>
}

export default function AdminDashboard() {
  usePageTitle("Admin Dashboard")
  const toast = useToast()
  const navigate = useNavigate()
  const { role } = useAuth()
  const [dash, setDash] = useState(null)
  const [completion, setCompletion] = useState(null)
  const [search, setSearch] = useState("")
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [phaseInfo, setPhaseInfo] = useState(null)
  const [overridePhase, setOverridePhase] = useState("Q1")
  const [applyingOverride, setApplyingOverride] = useState(false)
  const [fastForwarding, setFastForwarding] = useState(false)
  const [simulatingEscalation, setSimulatingEscalation] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false)
  const [resetConfirmText, setResetConfirmText] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const [d, c, phase] = await Promise.all([
        api.get("/admin/dashboard"),
        api.get("/admin/reports/completion"),
        api.get("/admin/current-phase"),
      ])
      setDash(d.data)
      setCompletion(c.data)
      setPhaseInfo(phase.data)
      if (phase.data?.active_quarter) {
        setOverridePhase(phase.data.active_quarter)
      } else if (phase.data?.phase === "goal_setting") {
        setOverridePhase("goal_setting")
      }
    } catch (err) {
      setLoadError(err.response?.data?.detail ?? "Failed to load dashboard")
    } finally {
      setLoading(false)
    }
  }, [])

  async function fastForwardDemo() {
    if (fastForwarding) return
    const confirmed = window.confirm(
      "This will create demo goals and check-ins for all employees. Continue?",
    )
    if (!confirmed) return
    setFastForwarding(true)
    try {
      const { data } = await api.post("/admin/demo/fast-forward")
      toast.success(
        `${data.message} (${data.goals_created} goals, ${data.checkins_created} check-ins)`,
      )
      await load()
    } catch (err) {
      toast.error(err.response?.data?.detail ?? "Fast forward failed")
    } finally {
      setFastForwarding(false)
    }
  }

  async function simulateEscalation() {
    if (simulatingEscalation) return
    const confirmed = window.confirm(
      "This will send escalation emails to employees, managers, and HR. Continue?",
    )
    if (!confirmed) return
    setSimulatingEscalation(true)
    try {
      const { data } = await api.post("/admin/demo/simulate-escalation")
      toast.success(`${data.emails_sent} escalation emails sent! Check inbox.`)
      await load()
    } catch (err) {
      toast.error(err.response?.data?.detail ?? "Escalation simulation failed")
    } finally {
      setSimulatingEscalation(false)
    }
  }

  async function resetDemoData() {
    if (resetConfirmText !== "RESET") {
      toast.error('Type "RESET" to confirm')
      return
    }
    setResetting(true)
    try {
      await api.post("/admin/demo/reset")
      setResetConfirmOpen(false)
      setResetConfirmText("")
      toast.success("Demo reset complete. Fresh start ready.")
      setTimeout(() => {
        navigate("/admin/dashboard")
        load()
      }, 2000)
    } catch (err) {
      toast.error(err.response?.data?.detail ?? "Demo reset failed")
    } finally {
      setResetting(false)
    }
  }

  async function applyPhaseOverride() {
    if (applyingOverride) return
    setApplyingOverride(true)
    try {
      await api.post("/admin/demo/override-phase", { phase: overridePhase })
      setDemoMode(true)
      const { data } = await api.get("/admin/current-phase")
      setPhaseInfo(data)
      window.dispatchEvent(new Event("demo-phase-changed"))
      const quarterLabel =
        overridePhase === "goal_setting"
          ? "goal setting"
          : `${overridePhase} check-ins`
      toast.success(`Phase overridden — employees can now log ${quarterLabel}`)
    } catch (err) {
      toast.error(err.response?.data?.detail ?? "Failed to apply phase override")
    } finally {
      setApplyingOverride(false)
    }
  }

  useEffect(() => {
    load()
  }, [load])

  const filteredEmployees = useMemo(() => {
    const list = completion?.employees ?? []
    if (!search.trim()) return list
    const q = search.toLowerCase()
    return list.filter(
      (e) =>
        e.employee_name.toLowerCase().includes(q) ||
        (e.manager_name ?? "").toLowerCase().includes(q),
    )
  }, [completion, search])

  const avgCheckinRate = useMemo(() => {
    const rates = Object.values(dash?.checkin_completion_rates ?? {})
    if (!rates.length) return 0
    return Math.round(rates.reduce((a, b) => a + b, 0) / rates.length)
  }, [dash])

  if (loading) return <LoadingSpinner fullPage />

  if (loadError) {
    return (
      <div className="flex flex-col items-center gap-4 py-16 text-center">
        <p className="text-destructive">{loadError}</p>
        <Button onClick={() => load()}>Retry</Button>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold">Admin Dashboard</h1>

      {role === "admin" && (
        <section className="rounded-xl border-2 border-amber-300 bg-amber-50/50 p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-amber-900">⚡ Demo Mode Controls</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-sm text-amber-900">
                <span className="font-medium">Current Phase:</span> {phaseInfo?.label ?? "—"}
              </p>
              <p className="mt-1 text-sm text-amber-800">
                <span className="font-medium">Active Quarter:</span>{" "}
                {phaseInfo?.active_quarter ?? "None"}
              </p>
              {phaseInfo?.next_phase && (
                <p className="mt-1 text-xs text-amber-700">{phaseInfo.next_phase}</p>
              )}
            </div>
            <div className="space-y-2">
              <label className="block text-sm font-medium text-amber-900">
                Override Phase for Demo
                <select
                  className="mt-1 w-full rounded-md border border-amber-300 bg-white px-3 py-2 text-sm"
                  value={overridePhase}
                  onChange={(e) => setOverridePhase(e.target.value)}
                >
                  {PHASE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </label>
              <Button
                type="button"
                disabled={applyingOverride}
                onClick={applyPhaseOverride}
                className="w-full bg-amber-600 hover:bg-amber-700"
              >
                {applyingOverride ? (
                  <span className="inline-flex items-center gap-2">
                    <ButtonSpinner />
                    Applying...
                  </span>
                ) : (
                  "Apply Override"
                )}
              </Button>
            </div>
          </div>
          <p className="mt-3 text-xs text-amber-800">
            ⚠️ Phase override resets on server restart. For demo purposes only.
          </p>

          <div className="mt-6 border-t border-amber-200 pt-6">
            <h3 className="text-sm font-semibold text-amber-900">Data Controls</h3>
            <div className="mt-3 flex flex-wrap gap-3">
              <Button
                type="button"
                title="Creates realistic data for all employees including approved goals and Q1 check-ins"
                disabled={fastForwarding}
                onClick={fastForwardDemo}
                className="bg-green-600 hover:bg-green-700"
              >
                {fastForwarding ? (
                  <span className="inline-flex items-center gap-2">
                    <ButtonSpinner />
                    Creating...
                  </span>
                ) : (
                  "🚀 Fast Forward Demo"
                )}
              </Button>
              <Button
                type="button"
                title="Makes all draft goals appear 7 days old and triggers escalation emails"
                disabled={simulatingEscalation}
                onClick={simulateEscalation}
                className="bg-orange-500 hover:bg-orange-600"
              >
                {simulatingEscalation ? (
                  <span className="inline-flex items-center gap-2">
                    <ButtonSpinner />
                    Simulating...
                  </span>
                ) : (
                  "⚡ Simulate Escalation"
                )}
              </Button>
              <Button
                type="button"
                variant="destructive"
                title="Clears all goals and check-ins, keeps user accounts"
                onClick={() => {
                  setResetConfirmText("")
                  setResetConfirmOpen(true)
                }}
              >
                🔄 Reset Demo Data
              </Button>
            </div>
          </div>
        </section>
      )}

      {resetConfirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl border bg-card p-6 shadow-lg">
            <h3 className="text-lg font-semibold">Reset demo data?</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              This will delete ALL goals, check-ins, and audit logs. Users will be kept. Are you
              sure?
            </p>
            <label className="mt-4 block text-sm font-medium">
              Type RESET to confirm
              <input
                className="mt-1 w-full rounded-md border px-3 py-2"
                value={resetConfirmText}
                onChange={(e) => setResetConfirmText(e.target.value)}
                placeholder="RESET"
              />
            </label>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setResetConfirmOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={resetting || resetConfirmText !== "RESET"}
                onClick={resetDemoData}
              >
                {resetting ? "Resetting..." : "Reset"}
              </Button>
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard label="Total Employees" value={dash?.total_employees ?? 0} />
        <StatCard label="Total Managers" value={dash?.total_managers ?? 0} />
        <StatCard label="Goals Approved" value={dash?.goals_approved ?? 0} />
        <StatCard label="Goals Pending Approval" value={dash?.goals_pending ?? 0} />
        <StatCard label="Employees Not Started" value={dash?.employees_not_started ?? 0} />
        <StatCard label="Avg Check-in Completion" value={`${avgCheckinRate}%`} />
      </div>

      <section>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Completion Dashboard</h2>
          <input
            type="search"
            placeholder="Search employee..."
            className="rounded-md border px-3 py-2 text-sm"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="overflow-x-auto rounded-xl border bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50 text-left">
                <th className="p-3">Employee</th>
                <th className="p-3">Manager</th>
                <th className="p-3">Goals</th>
                <th className="p-3">Submitted</th>
                <th className="p-3">Approved</th>
                <th className="p-3">Q1</th>
                <th className="p-3">Q2</th>
                <th className="p-3">Q3</th>
                <th className="p-3">Q4</th>
              </tr>
            </thead>
            <tbody>
              {filteredEmployees.map((emp) => (
                <tr key={emp.employee_id} className={`border-b ${rowClass(emp)}`}>
                  <td className="p-3 font-medium">{emp.employee_name}</td>
                  <td className="p-3">{emp.manager_name ?? "—"}</td>
                  <td className="p-3 text-center">
                    <CellIcon done={emp.has_created_goals} />
                  </td>
                  <td className="p-3 text-center">
                    <CellIcon done={emp.has_submitted_goals} />
                  </td>
                  <td className="p-3 text-center">
                    <CellIcon done={emp.has_approved_goals} />
                  </td>
                  <td className="p-3 text-center">
                    <CellIcon done={emp.q1_done} />
                  </td>
                  <td className="p-3 text-center">
                    <CellIcon done={emp.q2_done} />
                  </td>
                  <td className="p-3 text-center">
                    <CellIcon done={emp.q3_done} />
                  </td>
                  <td className="p-3 text-center">
                    <CellIcon done={emp.q4_done} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Recent Activity</h2>
          <Link to="/admin/audit-logs">
            <Button variant="outline" size="sm">
              View All Logs
            </Button>
          </Link>
        </div>
        <div className="space-y-4 rounded-xl border bg-card p-6">
          {(dash?.recent_audit_logs ?? []).map((log) => (
            <div key={log.id} className="flex gap-3">
              <div className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${entityDotColor(log.entity)}`} />
              <div>
                <p className="text-sm">{log.change_description}</p>
                <p className="text-xs text-muted-foreground">
                  {log.changed_by_name} · {new Date(log.changed_at).toLocaleString()}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
