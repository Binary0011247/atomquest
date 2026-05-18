import { useCallback, useEffect, useMemo, useState } from "react"
import { Link, useNavigate } from "react-router-dom"

import api from "@/api/axios"
import LoadingSpinner from "@/components/LoadingSpinner"
import ProgressScoreBar from "@/components/ProgressScoreBar"
import { Button } from "@/components/ui/button"
import { useToast } from "@/context/ToastContext"
import usePageTitle from "@/hooks/usePageTitle"
import { getCurrentQuarter, getWeightageStatus } from "@/utils/scoreCalculator"

const UOM_LABELS = {
  numeric_min: "Numeric Min",
  numeric_max: "Numeric Max",
  timeline: "Timeline",
  zero: "Zero Based",
}

const QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

function formatTarget(goal) {
  if (goal.uom_type === "timeline" && goal.target_date) {
    return `Due: ${goal.target_date}`
  }
  if (goal.uom_type === "zero") return "Zero = success"
  if (goal.target_value != null) return `Target: ${goal.target_value}`
  return "—"
}

function isAutoSyncedCheckin(checkin) {
  return checkin?.employee_note?.startsWith("Auto-synced from primary owner")
}

function StatusBadge({ status, isLocked }) {
  const styles = {
    draft: "bg-gray-100 text-gray-700",
    submitted: "bg-blue-100 text-blue-800",
    approved: "bg-green-100 text-green-800",
    returned: "bg-orange-100 text-orange-800",
  }
  const labels = {
    draft: "Draft",
    submitted: "Pending Approval",
    approved: isLocked ? "Approved 🔒" : "Approved",
    returned: "Returned — Needs Revision",
  }
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[status] ?? styles.draft}`}>
      {labels[status] ?? status}
    </span>
  )
}

export default function EmployeeDashboard() {
  usePageTitle("My Goals")
  const toast = useToast()
  const navigate = useNavigate()
  const [goals, setGoals] = useState([])
  const [checkinEntries, setCheckinEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [submittingId, setSubmittingId] = useState(null)
  const [submittingAll, setSubmittingAll] = useState(false)

  const loadGoals = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const [goalsRes, checkinsRes] = await Promise.all([
        api.get("/goals/my"),
        api.get("/checkins/my").catch(() => ({ data: [] })),
      ])
      setGoals(goalsRes.data.goals ?? [])
      setCheckinEntries(checkinsRes.data ?? [])
    } catch (err) {
      const msg = err.response?.data?.detail ?? "Failed to load your goals"
      setLoadError(msg)
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    loadGoals()
  }, [loadGoals])

  const personalGoals = useMemo(() => goals.filter((g) => !g.is_shared), [goals])
  const sharedGoals = useMemo(() => goals.filter((g) => g.is_shared), [goals])

  const checkinsByGoalId = useMemo(() => {
    const map = {}
    checkinEntries.forEach((entry) => {
      map[entry.goal.id] = entry.checkins ?? []
    })
    return map
  }, [checkinEntries])

  const weightage = useMemo(() => getWeightageStatus(goals), [goals])

  const hasDraftOrReturned = useMemo(
    () => personalGoals.some((g) => g.status === "draft" || g.status === "returned"),
    [personalGoals],
  )

  const barColor =
    weightage.total === 100
      ? "bg-green-500"
      : weightage.total > 100
        ? "bg-red-500"
        : weightage.total > 0
          ? "bg-yellow-500"
          : "bg-muted"

  async function submitOne(goal) {
    if (submittingId || submittingAll) return
    setSubmittingId(goal.id)
    try {
      await api.post(`/goals/${goal.id}/submit`)
      toast.success(`"${goal.title}" submitted for approval`)
      await loadGoals()
    } catch (err) {
      toast.error(err.response?.data?.detail ?? "Failed to submit goal")
    } finally {
      setSubmittingId(null)
    }
  }

  async function submitAll() {
    if (submittingAll || submittingId) return
    const count = personalGoals.filter(
      (g) => g.status === "draft" || g.status === "returned",
    ).length
    const confirmed = window.confirm(
      `Are you sure you want to submit all ${count} goals for manager approval? This cannot be undone.`,
    )
    if (!confirmed) return

    setSubmittingAll(true)
    try {
      await api.post("/goals/submit-all")
      toast.success("All goals submitted! Waiting for manager approval.")
      await loadGoals()
    } catch (err) {
      toast.error(err.response?.data?.detail ?? "Failed to submit all goals")
    } finally {
      setSubmittingAll(false)
    }
  }

  if (loading) return <LoadingSpinner fullPage />

  if (loadError) {
    return (
      <div className="flex flex-col items-center gap-4 py-16 text-center">
        <p className="text-destructive">{loadError}</p>
        <Button onClick={loadGoals}>Retry</Button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">My Goals</h1>
        <Link to="/employee/goals/new">
          <Button>➕ Add New Goal</Button>
        </Link>
      </div>

      <section className="rounded-xl border bg-card p-6 shadow-sm">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-medium">Total Weightage: {weightage.total}% / 100%</span>
          {weightage.isValid && (
            <span className="font-medium text-green-600">✅ Ready to Submit</span>
          )}
        </div>
        <div className="h-4 overflow-hidden rounded-full bg-muted">
          <div
            className={`h-full transition-all duration-300 ${barColor}`}
            style={{ width: `${Math.min(weightage.total, 100)}%` }}
          />
        </div>
        <p className="mt-2 text-sm text-muted-foreground">
          {weightage.isOver
            ? `Over by ${Math.abs(weightage.remaining)}% — reduce weightage on your goals`
            : weightage.isValid
              ? "All weightage allocated"
              : `${weightage.remaining}% remaining to allocate`}
        </p>
      </section>

      {sharedGoals.length > 0 && (
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">📌 Shared Goals (Pushed by Manager/Admin)</h2>
            <p className="text-sm text-muted-foreground">
              These goals are read-only. You can only adjust your weightage.
            </p>
          </div>
          {sharedGoals.map((goal) => (
            <SharedGoalCard
              key={goal.id}
              goal={goal}
              checkins={checkinsByGoalId[goal.id] ?? []}
              onWeightageSaved={loadGoals}
            />
          ))}
        </section>
      )}

      {personalGoals.length === 0 && sharedGoals.length === 0 ? (
        <section className="rounded-xl border border-dashed bg-card py-16 text-center">
          <p className="text-lg font-medium text-muted-foreground">You haven&apos;t created any goals yet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Use &apos;Add New Goal&apos; in the top right to create your first goal
          </p>
        </section>
      ) : personalGoals.length > 0 ? (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Your Goals ({personalGoals.length})</h2>
          {personalGoals.map((goal) => (
            <GoalCard
              key={goal.id}
              goal={goal}
              submitting={submittingId === goal.id}
              onEdit={() => navigate(`/employee/goals/edit/${goal.id}`)}
              onSubmit={() => submitOne(goal)}
            />
          ))}
        </section>
      ) : null}

      {personalGoals.length > 0 && hasDraftOrReturned && (
        <section className="rounded-xl border bg-card p-6">
          <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-between">
            <div>
              <p className="font-medium">Ready to send everything to your manager?</p>
              <p className="text-sm text-muted-foreground">
                All goals must total exactly 100% weightage before submitting.
              </p>
            </div>
            <div className="group relative">
              <Button
                size="lg"
                className="min-w-[200px]"
                disabled={!weightage.isValid || submittingAll}
                onClick={submitAll}
                title={
                  !weightage.isValid
                    ? `Allocate remaining ${weightage.remaining}% before submitting`
                    : undefined
                }
              >
                {submittingAll ? "Submitting..." : "Submit All Goals"}
              </Button>
              {!weightage.isValid && (
                <p className="pointer-events-none absolute -top-10 left-1/2 hidden w-64 -translate-x-1/2 rounded bg-gray-900 px-2 py-1 text-center text-xs text-white group-hover:block">
                  Allocate remaining {weightage.remaining}% before submitting
                </p>
              )}
            </div>
          </div>
        </section>
      )}
    </div>
  )
}

function ReadOnlyField({ label, value, tooltip }) {
  return (
    <div className="group relative">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p
        className="mt-1 cursor-not-allowed rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground"
        title={tooltip}
      >
        {value}
      </p>
      <span className="pointer-events-none absolute -top-8 left-0 z-10 hidden whitespace-nowrap rounded bg-gray-900 px-2 py-1 text-xs text-white group-hover:block">
        {tooltip}
      </span>
    </div>
  )
}

function SharedGoalCard({ goal, checkins, onWeightageSaved }) {
  const toast = useToast()
  const [weightage, setWeightage] = useState(goal.weightage)
  const [saving, setSaving] = useState(false)
  const activeQuarter = getCurrentQuarter()

  useEffect(() => {
    setWeightage(goal.weightage)
  }, [goal.weightage])

  async function saveWeightage() {
    const value = Number(weightage)
    if (Number.isNaN(value) || value < 10 || value > 100) {
      toast.error("Weightage must be between 10 and 100")
      return
    }
    setSaving(true)
    try {
      await api.put(`/goals/${goal.id}`, { weightage: value })
      toast.success("Weightage updated")
      onWeightageSaved()
    } catch (err) {
      toast.error(err.response?.data?.detail ?? "Failed to update weightage")
    } finally {
      setSaving(false)
    }
  }

  const checkinsByQuarter = useMemo(() => {
    const map = {}
    checkins.forEach((c) => {
      map[c.quarter] = c
    })
    return map
  }, [checkins])

  return (
    <article className="rounded-xl border border-l-4 border-l-blue-500 bg-card p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-3">
          <ReadOnlyField
            label="Goal Title"
            value={goal.title}
            tooltip="Shared goals cannot be modified. Contact your manager."
          />
          <div className="flex flex-wrap gap-2">
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
              {goal.thrust_area}
            </span>
            <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
              {UOM_LABELS[goal.uom_type] ?? goal.uom_type}
            </span>
          </div>
        </div>
        <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
          📌 Shared
        </span>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <ReadOnlyField
          label="Target"
          value={formatTarget(goal)}
          tooltip="Shared goals cannot be modified. Contact your manager."
        />
        <div>
          <p className="text-xs font-medium text-muted-foreground">Weightage (%)</p>
          <div className="mt-1 flex gap-2">
            <input
              type="number"
              min={10}
              max={100}
              className="w-24 rounded-md border px-3 py-2 text-sm"
              value={weightage}
              onChange={(e) => setWeightage(e.target.value)}
            />
            <Button size="sm" disabled={saving} onClick={saveWeightage}>
              {saving ? "Saving..." : "Save Weightage"}
            </Button>
          </div>
        </div>
      </div>

      <div className="mt-6 border-t pt-4">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold">Quarterly Check-ins</h4>
          <Link to="/employee/checkins" className="text-xs text-primary hover:underline">
            Full check-in page →
          </Link>
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {QUARTERS.map((q) => {
            const checkin = checkinsByQuarter[q]
            const synced = isAutoSyncedCheckin(checkin)
            return (
              <div
                key={q}
                className={`rounded-lg border p-3 text-sm ${
                  q === activeQuarter ? "border-primary/40 bg-primary/5" : ""
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{q}</span>
                  {synced && (
                    <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
                      🔄 Synced from primary owner
                    </span>
                  )}
                </div>
                {checkin ? (
                  <div className="mt-2 space-y-1 text-muted-foreground">
                    <p>Status: {checkin.status.replace("_", " ")}</p>
                    {checkin.actual_value != null && <p>Actual: {checkin.actual_value}</p>}
                    {checkin.actual_date && <p>Date: {checkin.actual_date}</p>}
                    {checkin.progress_score != null && (
                      <ProgressScoreBar score={checkin.progress_score} size="sm" />
                    )}
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-muted-foreground">No check-in yet</p>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </article>
  )
}

function GoalCard({ goal, submitting, onEdit, onSubmit }) {
  const isDraft = goal.status === "draft"
  const isReturned = goal.status === "returned"
  const isLocked = goal.status === "submitted" || goal.status === "approved"

  return (
    <article className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-lg font-bold">{goal.title}</h3>
          <div className="mt-2 flex flex-wrap gap-2">
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
              {goal.thrust_area}
            </span>
            <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
              {UOM_LABELS[goal.uom_type] ?? goal.uom_type}
            </span>
          </div>
        </div>
        <StatusBadge status={goal.status} isLocked={goal.is_locked} />
      </div>

      <div className="mt-3 flex flex-wrap gap-4 text-sm text-muted-foreground">
        <span>{formatTarget(goal)}</span>
        <span className="font-medium text-foreground">Weightage: {goal.weightage}%</span>
        {isLocked && <span title="Locked">🔒</span>}
      </div>

      {isReturned && goal.return_comment && (
        <div className="mt-4 rounded-md border border-yellow-300 bg-yellow-50 px-4 py-3 text-sm text-yellow-900">
          <p className="font-medium">Manager feedback</p>
          <p className="mt-1">{goal.return_comment}</p>
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {isDraft && (
          <>
            <Button size="sm" variant="outline" onClick={onEdit}>
              Edit
            </Button>
            <Button size="sm" disabled={submitting} onClick={onSubmit}>
              {submitting ? "Submitting..." : "Submit This Goal"}
            </Button>
          </>
        )}
        {isReturned && (
          <Button size="sm" onClick={onEdit}>
            Edit & Resubmit
          </Button>
        )}
      </div>
    </article>
  )
}
