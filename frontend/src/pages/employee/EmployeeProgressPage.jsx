import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"

import api from "@/api/axios"
import LoadingSpinner from "@/components/LoadingSpinner"
import { Button } from "@/components/ui/button"
import { useToast } from "@/context/ToastContext"
import usePageTitle from "@/hooks/usePageTitle"

const QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

export default function EmployeeProgressPage() {
  usePageTitle("My Progress")
  const toast = useToast()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const { data: progress } = await api.get("/reports/my-progress")
      setData(progress)
    } catch {
      toast.error("Failed to load progress report")
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  if (loading) return <LoadingSpinner fullPage />

  if (!data) {
    return (
      <div className="text-center text-muted-foreground">
        <p>No progress data yet.</p>
        <Link to="/employee/goals/new">
          <Button className="mt-4">Start by creating your first goal →</Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold">My Progress</h1>

      <div className="grid gap-4 sm:grid-cols-4">
        <Stat label="Total Goals" value={data.total_goals} />
        <Stat label="Approved" value={data.approved_goals} />
        <Stat label="Overall Avg" value={`${data.overall_avg}%`} />
        <Stat label="At Risk Goals" value={data.goals_at_risk} warn={data.goals_at_risk > 0} />
      </div>

      <section className="rounded-xl border bg-card p-6">
        <h2 className="mb-4 font-semibold">Quarter Scores</h2>
        <div className="grid grid-cols-4 gap-4">
          {QUARTERS.map((q) => (
            <div key={q} className="rounded-lg border p-4 text-center">
              <p className="text-sm text-muted-foreground">{q}</p>
              <p className="text-xl font-semibold">
                {data.quarter_scores?.[q] != null ? `${data.quarter_scores[q]}%` : "—"}
              </p>
            </div>
          ))}
        </div>
      </section>

      {data.best_performing_goal && (
        <section className="rounded-xl border border-green-200 bg-green-50 p-6">
          <h2 className="font-semibold text-green-900">Best Performing Goal</h2>
          <p className="mt-2">
            {data.best_performing_goal.title} — {data.best_performing_goal.score}%
          </p>
        </section>
      )}

      {data.needs_attention?.length > 0 && (
        <section className="rounded-xl border border-red-200 bg-red-50 p-6">
          <h2 className="mb-3 font-semibold text-red-900">Needs Attention</h2>
          <ul className="space-y-2 text-sm">
            {data.needs_attention.map((g) => (
              <li key={g.title}>
                {g.title} — <span className="font-medium">{g.score}%</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

function Stat({ label, value, warn }) {
  return (
    <div className={`rounded-xl border bg-card p-4 ${warn ? "border-red-200" : ""}`}>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`text-2xl font-semibold ${warn ? "text-red-600" : ""}`}>{value}</p>
    </div>
  )
}
