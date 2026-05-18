import { useCallback, useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"

import api from "@/api/axios"
import ProgressScoreBar from "@/components/ProgressScoreBar"
import { Button } from "@/components/ui/button"
import usePageTitle from "@/hooks/usePageTitle"
import { useAuth } from "@/context/AuthContext"
import { getCurrentQuarter } from "@/utils/scoreCalculator"

const QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

function CommentModal({ open, onClose, employee, goalEntry, checkin, onSubmit, submitting }) {
  const [comment, setComment] = useState("")

  useEffect(() => {
    if (open) setComment(checkin?.manager_comment ?? "")
  }, [open, checkin])

  if (!open || !goalEntry) return null

  const goal = goalEntry.goal
  const score = checkin?.progress_score ?? 0

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-xl border bg-card p-6 shadow-lg">
        <h2 className="text-lg font-semibold">Add Check-in Comment</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {employee.employee_name} · {goal.title}
        </p>
        <div className="mt-3 space-y-1 text-sm">
          <p>Target: {goal.target_value ?? goal.target_date ?? "—"}</p>
          <p>
            Actual: {checkin?.actual_value ?? checkin?.actual_date ?? "—"}
          </p>
          <ProgressScoreBar score={score} size="sm" />
        </div>
        <label className="mt-4 block text-sm">
          Manager comment (required)
          <textarea
            className="mt-1 w-full rounded-md border px-3 py-2"
            rows={4}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Provide feedback on this check-in..."
          />
        </label>
        <div className="mt-4 flex gap-2">
          <Button variant="outline" className="flex-1" onClick={onClose}>
            Cancel
          </Button>
          <Button
            className="flex-1"
            disabled={submitting || !comment.trim()}
            onClick={() => onSubmit(comment.trim())}
          >
            {submitting ? "Saving..." : "Submit Comment"}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function TeamCheckinView() {
  usePageTitle("Team Check-ins")
  const { logout } = useAuth()
  const [quarter, setQuarter] = useState(getCurrentQuarter())
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [expanded, setExpanded] = useState({})
  const [modal, setModal] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const loadTeam = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const { data } = await api.get(`/checkins/team/${quarter}`)
      setReports(data)
    } catch {
      setError("Failed to load team check-ins")
    } finally {
      setLoading(false)
    }
  }, [quarter])

  useEffect(() => {
    loadTeam()
  }, [loadTeam])

  const submittedCount = useMemo(
    () => reports.filter((r) => r.completed_checkins > 0).length,
    [reports],
  )

  const atRiskGoals = useMemo(() => {
    const risks = []
    reports.forEach((emp) => {
      emp.goals.forEach((g) => {
        const checkin = g.checkins?.[0]
        if (checkin?.progress_score != null && checkin.progress_score < 60) {
          risks.push({
            employee: emp.employee_name,
            goal: g.goal.title,
            score: checkin.progress_score,
          })
        }
      })
    })
    return risks
  }, [reports])

  async function submitComment(comment) {
    if (!modal?.checkin?.id) return
    setSubmitting(true)
    try {
      await api.post(`/checkins/${modal.checkin.id}/manager-comment`, {
        manager_comment: comment,
      })
      setModal(null)
      await loadTeam()
    } catch (err) {
      setError(err.response?.data?.detail ?? "Failed to save comment")
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        Loading team check-ins...
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-muted/20">
      <header className="border-b bg-card px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-primary">AtomQuest</p>
            <h1 className="text-xl font-semibold">Team Check-ins</h1>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/manager/dashboard" className="text-sm text-primary hover:underline">
              ← Dashboard
            </Link>
            <Button variant="outline" size="sm" onClick={logout}>
              Log out
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-6 py-8">
        {error && (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        <div className="flex flex-wrap gap-2 border-b pb-2">
          {QUARTERS.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => setQuarter(q)}
              className={`rounded-lg px-4 py-2 text-sm font-medium ${
                quarter === q ? "bg-primary text-primary-foreground" : "bg-muted"
              }`}
            >
              {q}
            </button>
          ))}
        </div>

        <div className="rounded-xl border bg-card p-4">
          <p className="text-sm text-muted-foreground">
            <span className="font-semibold text-foreground">{submittedCount}</span> of{" "}
            <span className="font-semibold text-foreground">{reports.length}</span> employees have
            submitted check-ins for {quarter}
          </p>
        </div>

        {atRiskGoals.length > 0 && (
          <section className="rounded-xl border-2 border-red-200 bg-red-50/60 p-5">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-red-900">
              <span>⚠</span> At Risk Goals ({atRiskGoals.length})
            </h2>
            <ul className="mt-3 space-y-2 text-sm text-red-800">
              {atRiskGoals.map((item, i) => (
                <li key={i}>
                  {item.employee} — {item.goal} ({item.score}%)
                </li>
              ))}
            </ul>
          </section>
        )}

        <div className="space-y-4">
          {reports.map((employee) => (
            <div key={employee.employee_id} className="rounded-xl border bg-card shadow-sm">
              <button
                type="button"
                className="flex w-full items-center justify-between p-5 text-left"
                onClick={() =>
                  setExpanded((e) => ({
                    ...e,
                    [employee.employee_id]: !e[employee.employee_id],
                  }))
                }
              >
                <div>
                  <h3 className="font-semibold">{employee.employee_name}</h3>
                  <p className="text-sm text-muted-foreground">{employee.employee_email}</p>
                </div>
                <div className="w-48 space-y-1">
                  <ProgressScoreBar score={employee.average_progress} size="sm" />
                  <p className="text-xs text-muted-foreground">
                    {employee.completed_checkins}/{employee.total_required_checkins} submitted
                  </p>
                </div>
              </button>

              {expanded[employee.employee_id] && (
                <div className="border-t px-5 pb-5">
                  <table className="mt-4 w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="pb-2">Goal</th>
                        <th className="pb-2">Target</th>
                        <th className="pb-2">Actual</th>
                        <th className="pb-2">Score</th>
                        <th className="pb-2">Status</th>
                        <th className="pb-2">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {employee.goals.map((entry) => {
                        const checkin = entry.checkins?.[0]
                        const goal = entry.goal
                        const atRisk = checkin?.progress_score != null && checkin.progress_score < 60
                        return (
                          <tr key={goal.id} className="border-b last:border-0">
                            <td className="py-3">
                              {atRisk && <span className="mr-1 text-red-500">⚠</span>}
                              {goal.title}
                            </td>
                            <td className="py-3">{goal.target_value ?? goal.target_date ?? "—"}</td>
                            <td className="py-3">
                              {checkin
                                ? checkin.actual_value ?? checkin.actual_date ?? "—"
                                : "—"}
                            </td>
                            <td className="py-3">
                              {checkin?.progress_score != null ? `${checkin.progress_score}%` : "—"}
                            </td>
                            <td className="py-3">{checkin?.status ?? "not submitted"}</td>
                            <td className="py-3">
                              {checkin ? (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() =>
                                    setModal({ employee, goalEntry: entry, checkin })
                                  }
                                >
                                  {checkin.manager_comment ? "Edit Comment" : "Add Comment"}
                                </Button>
                              ) : (
                                <span className="text-xs text-muted-foreground">No check-in</span>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                  {employee.goals.some((g) => g.checkins?.[0]?.manager_comment) && (
                    <div className="mt-4 space-y-2">
                      {employee.goals.map((entry) =>
                        entry.checkins?.[0]?.manager_comment ? (
                          <p key={entry.goal.id} className="text-xs text-muted-foreground">
                            <span className="font-medium">{entry.goal.title}:</span>{" "}
                            {entry.checkins[0].manager_comment}
                          </p>
                        ) : null,
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </main>

      <CommentModal
        open={Boolean(modal)}
        onClose={() => setModal(null)}
        employee={modal?.employee}
        goalEntry={modal?.goalEntry}
        checkin={modal?.checkin}
        onSubmit={submitComment}
        submitting={submitting}
      />
    </div>
  )
}
