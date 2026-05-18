import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"

import api from "@/api/axios"
import LoadingSpinner from "@/components/LoadingSpinner"
import { Button } from "@/components/ui/button"
import { useToast } from "@/context/ToastContext"
import usePageTitle from "@/hooks/usePageTitle"

const QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

export default function ManagerTeamProgressPage() {
  usePageTitle("Team Progress")
  const toast = useToast()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const { data: summary } = await api.get("/reports/team-summary")
      setData(summary)
    } catch {
      toast.error("Failed to load team summary")
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
      <p className="text-center text-muted-foreground">
        No employees assigned to you yet. Contact your admin to assign team members.
      </p>
    )
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold">Team Progress</h1>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Team Avg Score" value={`${data.team_avg_score}%`} />
        <Stat
          label="Pending Approvals"
          value={data.pending_my_actions?.approvals ?? 0}
          warn={(data.pending_my_actions?.approvals ?? 0) > 0}
        />
        <Stat
          label="Check-in Reviews"
          value={data.pending_my_actions?.checkin_reviews ?? 0}
        />
      </div>

      {data.top_performer && (
        <section className="rounded-xl border border-green-200 bg-green-50 p-6">
          <h2 className="font-semibold">Top Performer</h2>
          <p className="mt-1">
            {data.top_performer.name} — {data.top_performer.score}%
          </p>
        </section>
      )}

      <section className="rounded-xl border bg-card p-6">
        <h2 className="mb-4 font-semibold">Quarter Completion Rates</h2>
        <div className="grid grid-cols-4 gap-4">
          {QUARTERS.map((q) => (
            <div key={q} className="rounded-lg border p-4 text-center">
              <p className="text-sm text-muted-foreground">{q}</p>
              <p className="text-xl font-semibold">{data.quarter_completion_rates?.[q] ?? 0}%</p>
            </div>
          ))}
        </div>
      </section>

      {data.needs_support?.length > 0 ? (
        <section className="rounded-xl border border-orange-200 bg-orange-50 p-6">
          <h2 className="mb-3 font-semibold">Needs Support</h2>
          <ul className="space-y-2">
            {data.needs_support.map((e) => (
              <li key={e.name} className="flex justify-between text-sm">
                <span>{e.name}</span>
                <span className="font-medium text-red-700">{e.score}%</span>
              </li>
            ))}
          </ul>
          <Link to="/manager/dashboard" className="mt-4 inline-block">
            <Button size="sm" variant="outline">
              Review team goals
            </Button>
          </Link>
        </section>
      ) : (
        <p className="text-sm text-muted-foreground">All team members are on track.</p>
      )}
    </div>
  )
}

function Stat({ label, value, warn }) {
  return (
    <div className={`rounded-xl border bg-card p-4 ${warn ? "border-orange-200" : ""}`}>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`text-2xl font-semibold ${warn ? "text-orange-700" : ""}`}>{value}</p>
    </div>
  )
}
