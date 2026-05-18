import { useCallback, useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"

import api from "@/api/axios"
import ButtonSpinner from "@/components/ButtonSpinner"
import LoadingSpinner from "@/components/LoadingSpinner"
import ProgressScoreBar from "@/components/ProgressScoreBar"
import { Button } from "@/components/ui/button"
import usePageTitle from "@/hooks/usePageTitle"
import { useAuth } from "@/context/AuthContext"
import { calculateProgressScore, getCurrentQuarter, getScoreColor } from "@/utils/scoreCalculator"

const QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

const STATUS_OPTIONS = [
  { value: "not_started", label: "Not Started" },
  { value: "on_track", label: "On Track" },
  { value: "completed", label: "Completed" },
]

function isAutoSyncedCheckin(checkin) {
  return checkin?.employee_note?.startsWith("Auto-synced from primary owner")
}

function CheckinStatusBadge({ status }) {
  const styles = {
    not_started: "bg-gray-100 text-gray-700",
    on_track: "bg-blue-100 text-blue-800",
    completed: "bg-green-100 text-green-800",
  }
  const label = STATUS_OPTIONS.find((o) => o.value === status)?.label ?? status
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${styles[status] ?? styles.not_started}`}>
      {label}
    </span>
  )
}

export default function CheckinPage() {
  usePageTitle("Check-ins")
  const { logout } = useAuth()
  const [quarter, setQuarter] = useState(getCurrentQuarter())
  const [phaseInfo, setPhaseInfo] = useState(null)
  const [goals, setGoals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [savingId, setSavingId] = useState(null)
  const [forms, setForms] = useState({})

  const loadPhase = useCallback(async () => {
    try {
      const { data } = await api.get("/admin/current-phase")
      setPhaseInfo(data)
      if (data.phase === "checkin" && data.active_quarter) {
        setQuarter(data.active_quarter)
      }
    } catch {
      setPhaseInfo(null)
    }
  }, [])

  useEffect(() => {
    loadPhase()
  }, [loadPhase])

  const loadCheckins = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const { data } = await api.get(`/checkins/my/${quarter}`)
      setGoals(data)
      const initial = {}
      data.forEach((entry) => {
        const checkin = entry.checkins?.[0]
        const goal = entry.goal
        initial[goal.id] = {
          actual_value: checkin?.actual_value ?? "",
          actual_date: checkin?.actual_date ?? "",
          status: checkin?.status ?? "not_started",
          employee_note: checkin?.employee_note ?? "",
          zero_incidents: checkin?.actual_value === 0,
          checkin_id: checkin?.id ?? null,
          existing: checkin,
        }
      })
      setForms(initial)
    } catch {
      setError("Failed to load check-ins")
    } finally {
      setLoading(false)
    }
  }, [quarter])

  useEffect(() => {
    loadCheckins()
  }, [loadCheckins])

  function updateForm(goalId, field, value) {
    setForms((prev) => ({
      ...prev,
      [goalId]: { ...prev[goalId], [field]: value },
    }))
  }

  function previewScore(goal, form) {
    if (!form) return 0
    let actualValue = form.actual_value === "" ? null : Number(form.actual_value)
    if (goal.uom_type === "zero") {
      actualValue = form.zero_incidents ? 0 : 1
    }
    return calculateProgressScore(
      goal.uom_type,
      goal.target_value,
      actualValue,
      goal.target_date,
      form.actual_date || null,
    )
  }

  async function saveCheckin(goal) {
    if (savingId) return
    const form = forms[goal.id]
    if (!form) return
    setSavingId(goal.id)
    setError("")
    try {
      let actualValue = form.actual_value === "" ? null : Number(form.actual_value)
      if (goal.uom_type === "zero") {
        actualValue = form.zero_incidents ? 0 : 1
      }
      const payload = {
        quarter,
        actual_value: goal.uom_type === "timeline" ? null : actualValue,
        actual_date: goal.uom_type === "timeline" ? form.actual_date || null : null,
        status: form.status,
        employee_note: form.employee_note || null,
      }
      await api.post(`/checkins/${goal.id}`, payload)
      await loadCheckins()
    } catch (err) {
      setError(err.response?.data?.detail ?? "Failed to save check-in")
    } finally {
      setSavingId(null)
    }
  }

  const activeQuarter = phaseInfo?.active_quarter ?? getCurrentQuarter()
  const phase = phaseInfo?.phase ?? "checkin"
  const formsDisabled =
    phase === "goal_setting" ||
    phase === "closed" ||
    (phase === "checkin" && quarter !== activeQuarter)

  function quarterTabTitle(q) {
    if (phase !== "checkin") return undefined
    if (q !== activeQuarter) return "This quarter's window is not open"
    return undefined
  }

  if (loading) return <LoadingSpinner fullPage />

  return (
    <div className="min-h-screen bg-muted/20">
      <header className="border-b bg-card px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-primary">AtomQuest</p>
            <h1 className="text-xl font-semibold">Quarterly Check-ins</h1>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/employee/dashboard" className="text-sm text-primary hover:underline">
              ← Dashboard
            </Link>
            <Button variant="outline" size="sm" onClick={logout}>
              Log out
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-6 py-8">
        {phase === "goal_setting" && (
          <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
            📋 Goal Setting Phase — Check-ins are not open yet. Focus on creating and submitting
            your goals. Q1 check-ins open in July.
          </div>
        )}
        {phase === "checkin" && (
          <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">
            ✅ {activeQuarter} Check-in Window is Open
          </div>
        )}
        {phase === "closed" && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            ⏸️ No check-in window is currently active. Next window opens soon.
            {phaseInfo?.next_phase && (
              <span className="mt-1 block text-xs">{phaseInfo.next_phase}</span>
            )}
          </div>
        )}

        {error && (
          <div className="flex flex-wrap items-center gap-3 rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">
            <p className="flex-1">{error}</p>
            <Button variant="outline" size="sm" onClick={loadCheckins}>
              Retry
            </Button>
          </div>
        )}

        <div className="flex flex-wrap gap-2 border-b pb-2">
          {QUARTERS.map((q) => {
            const isInactiveTab = phase === "checkin" && q !== activeQuarter
            return (
              <button
                key={q}
                type="button"
                title={quarterTabTitle(q)}
                onClick={() => setQuarter(q)}
                disabled={phase === "goal_setting" || phase === "closed"}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  quarter === q
                    ? "bg-primary text-primary-foreground"
                    : isInactiveTab
                      ? "cursor-not-allowed bg-muted/60 text-muted-foreground/60"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                } ${q === activeQuarter && phase === "checkin" ? "ring-2 ring-primary/30" : ""}`}
              >
                {q}
                {q === activeQuarter && phase === "checkin" && (
                  <span className="ml-1 text-xs opacity-80">(active)</span>
                )}
              </button>
            )
          })}
        </div>

        {goals.length === 0 ? (
          <p className="text-center text-muted-foreground">
            No approved goals available for check-ins. Goals must be approved and locked first.
          </p>
        ) : (
          <div className="space-y-6">
            {goals.map((entry) => {
              const goal = entry.goal
              const form = forms[goal.id] ?? {}
              const existing = entry.checkins?.[0]
              const score = previewScore(goal, form)
              const color = getScoreColor(score)
              const isSharedChild = goal.is_shared && goal.parent_shared_goal_id
              const synced = isAutoSyncedCheckin(existing)

              return (
                <div
                  key={goal.id}
                  className={`rounded-xl border bg-card p-6 shadow-sm ${
                    goal.is_shared ? "border-l-4 border-l-blue-500" : ""
                  }`}
                >
                  <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-lg font-semibold">{goal.title}</h2>
                        {goal.is_shared && (
                          <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800">
                            📌 Shared
                          </span>
                        )}
                        {synced && (
                          <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
                            🔄 Synced from primary owner
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {goal.thrust_area} · {goal.uom_type.replace("_", " ")}
                        {goal.target_value != null && ` · target ${goal.target_value}`}
                        {goal.target_date && ` · due ${goal.target_date}`}
                      </p>
                      {isSharedChild && (
                        <p className="mt-1 text-xs text-muted-foreground">
                          Check-ins are synced from the primary goal owner.
                        </p>
                      )}
                    </div>
                    <CheckinStatusBadge status={form.status} />
                  </div>

                  <fieldset disabled={isSharedChild || formsDisabled} className="contents">
                  <div className="grid gap-4 md:grid-cols-2">
                    {(goal.uom_type === "numeric_min" || goal.uom_type === "numeric_max") && (
                      <label className="block text-sm">
                        Actual value
                        <input
                          type="number"
                          className="mt-1 w-full rounded-md border px-3 py-2"
                          value={form.actual_value}
                          onChange={(e) => updateForm(goal.id, "actual_value", e.target.value)}
                        />
                      </label>
                    )}
                    {goal.uom_type === "timeline" && (
                      <label className="block text-sm">
                        Actual completion date
                        <input
                          type="date"
                          className="mt-1 w-full rounded-md border px-3 py-2"
                          value={form.actual_date}
                          onChange={(e) => updateForm(goal.id, "actual_date", e.target.value)}
                        />
                      </label>
                    )}
                    {goal.uom_type === "zero" && (
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={form.zero_incidents}
                          onChange={(e) => updateForm(goal.id, "zero_incidents", e.target.checked)}
                        />
                        Incident count = 0
                      </label>
                    )}
                    <label className="block text-sm">
                      Status
                      <select
                        className="mt-1 w-full rounded-md border px-3 py-2"
                        value={form.status}
                        onChange={(e) => updateForm(goal.id, "status", e.target.value)}
                      >
                        {STATUS_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>

                  <label className="mt-4 block text-sm">
                    Employee note (optional)
                    <textarea
                      className="mt-1 w-full rounded-md border px-3 py-2"
                      rows={2}
                      value={form.employee_note}
                      onChange={(e) => updateForm(goal.id, "employee_note", e.target.value)}
                    />
                  </label>
                  </fieldset>

                  <div className="mt-4 space-y-2">
                    <p className="text-sm font-medium">Progress preview</p>
                    <ProgressScoreBar score={score} size="md" />
                    <p
                      className={`text-xs capitalize ${
                        color === "green"
                          ? "text-green-600"
                          : color === "yellow"
                            ? "text-amber-600"
                            : "text-red-600"
                      }`}
                    >
                      Score color: {color}
                    </p>
                  </div>

                  <div className="mt-4 flex flex-wrap items-center gap-3">
                    <Button
                      onClick={() => saveCheckin(goal)}
                      disabled={savingId === goal.id || isSharedChild || formsDisabled}
                    >
                      {savingId === goal.id ? (
                        <span className="inline-flex items-center gap-2">
                          <ButtonSpinner />
                          Saving...
                        </span>
                      ) : existing ? (
                        "Update Check-in"
                      ) : (
                        "Save Check-in"
                      )}
                    </Button>
                    {existing && (
                      <span className="text-xs text-muted-foreground">
                        Last updated: {new Date(existing.updated_at).toLocaleString()}
                      </span>
                    )}
                  </div>

                  {existing?.manager_comment && (
                    <div className="mt-4 rounded-md border border-blue-200 bg-blue-50 px-4 py-3 text-sm">
                      <p className="font-medium text-blue-900">Manager comment</p>
                      <p className="mt-1 text-blue-800">{existing.manager_comment}</p>
                    </div>
                  )}

                  {existing?.progress_score != null && (
                    <div className="mt-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${
                          existing.score_color === "green"
                            ? "bg-green-100 text-green-800"
                            : existing.score_color === "yellow"
                              ? "bg-amber-100 text-amber-800"
                              : "bg-red-100 text-red-800"
                        }`}
                      >
                        Saved score: {existing.progress_score}%
                      </span>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </main>
    </div>
  )
}
