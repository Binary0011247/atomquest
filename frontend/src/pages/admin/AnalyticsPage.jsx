import { useCallback, useEffect, useState } from "react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import api from "@/api/axios"
import LoadingSpinner from "@/components/LoadingSpinner"
import { Button } from "@/components/ui/button"
import { useToast } from "@/context/ToastContext"
import usePageTitle from "@/hooks/usePageTitle"

const QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
const PIE_COLORS = ["#3b82f6", "#8b5cf6", "#f97316", "#22c55e", "#94a3b8"]
const MEDALS = ["🥇", "🥈", "🥉", "4.", "5."]

function scoreColor(score) {
  if (score == null) return "bg-gray-200 text-gray-500"
  if (score >= 90) return "bg-green-700 text-white"
  if (score >= 70) return "bg-green-200 text-green-900"
  if (score >= 50) return "bg-yellow-200 text-yellow-900"
  if (score >= 30) return "bg-orange-200 text-orange-900"
  return "bg-red-200 text-red-900"
}

function scoreBadgeClass(score) {
  if (score >= 90) return "bg-green-100 text-green-800"
  if (score >= 60) return "bg-yellow-100 text-yellow-800"
  return "bg-red-100 text-red-800"
}

function thrustBarColor(score) {
  if (score >= 90) return "#22c55e"
  if (score >= 60) return "#eab308"
  return "#ef4444"
}

function statusLabel(score) {
  if (score == null) return "No data"
  if (score >= 90) return "Exceeding"
  if (score >= 60) return "On Track"
  return "At Risk"
}

export default function AnalyticsPage() {
  usePageTitle("Analytics")
  const toast = useToast()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data: overview } = await api.get("/admin/analytics/overview")
      setData(overview)
    } catch {
      toast.error("Failed to load analytics")
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  async function viewEmployee(id) {
    try {
      const { data: emp } = await api.get(`/admin/analytics/employee/${id}`)
      setDetail(emp)
    } catch {
      toast.error("Could not load employee details")
    }
  }

  if (loading) return <LoadingSpinner fullPage />

  if (!data) {
    return <p className="text-muted-foreground">No analytics data available.</p>
  }

  const orgScore = data.org_avg_score ?? 0
  const avgCheckin =
    data.goal_achievement_trend?.length > 0
      ? Math.round(
          data.goal_achievement_trend.reduce((a, t) => a + (t.avg_score || 0), 0) /
            data.goal_achievement_trend.length,
        )
      : 0

  const thrustChart = (data.thrust_area_distribution ?? []).map((t) => ({
    name: t.thrust_area,
    score: t.avg_score,
    fill: thrustBarColor(t.avg_score),
  }))

  return (
    <div className="space-y-10">
      <h1 className="text-2xl font-semibold">Analytics Dashboard</h1>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Org Average Score"
          value={`${orgScore}%`}
          className={scoreBadgeClass(orgScore)}
        />
        <KpiCard label="Total Check-ins Completed" value={data.total_checkins_completed ?? 0} />
        <KpiCard
          label="At Risk Employees"
          value={data.at_risk_employees?.length ?? 0}
          className={(data.at_risk_employees?.length ?? 0) > 0 ? "text-red-600" : ""}
        />
        <KpiCard
          label="Top Thrust Area"
          value={data.top_thrust_area ?? "—"}
          sub={`${avgCheckin}% avg across quarters`}
        />
      </section>

      <section className="rounded-xl border bg-card p-6">
        <h2 className="mb-4 text-lg font-semibold">Organization Score Trend</h2>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data.goal_achievement_trend ?? []}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="quarter" />
            <YAxis domain={[0, 100]} />
            <Tooltip formatter={(v) => [`${v}%`, "Avg Score"]} />
            <ReferenceLine y={60} stroke="#ef4444" strokeDasharray="4 4" label="At Risk Threshold" />
            <ReferenceLine y={90} stroke="#22c55e" strokeDasharray="4 4" label="Target" />
            <Line type="monotone" dataKey="avg_score" stroke="#3b82f6" strokeWidth={2} dot={{ r: 5 }} />
          </LineChart>
        </ResponsiveContainer>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border bg-card p-6">
          <h2 className="mb-4 text-lg font-semibold">Performance by Thrust Area</h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={thrustChart} layout="vertical" margin={{ left: 80 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" domain={[0, 100]} />
              <YAxis type="category" dataKey="name" width={75} />
              <Tooltip formatter={(v) => [`${v}%`, "Avg Score"]} />
              <Bar dataKey="score" radius={4}>
                {thrustChart.map((entry) => (
                  <Cell key={entry.name} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-xl border bg-card p-6">
          <h2 className="mb-4 text-lg font-semibold">Goal Distribution by Type</h2>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={data.uom_type_distribution ?? []}
                dataKey="count"
                nameKey="uom_type"
                cx="50%"
                cy="50%"
                outerRadius={90}
                label={({ uom_type, percentage }) => `${uom_type} ${percentage}%`}
              >
                {(data.uom_type_distribution ?? []).map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="rounded-xl border bg-card p-6">
        <h2 className="mb-4 text-lg font-semibold">Manager Effectiveness</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50 text-left">
                <th className="p-3">Manager Name</th>
                <th className="p-3">Team Size</th>
                <th className="p-3">Avg Approval Time</th>
                <th className="p-3">Check-in Review Rate</th>
                <th className="p-3">Team Avg Score</th>
              </tr>
            </thead>
            <tbody>
              {[...(data.manager_effectiveness ?? [])]
                .sort((a, b) => b.team_avg_score - a.team_avg_score)
                .map((m) => (
                  <tr key={m.manager_id} className="border-b">
                    <td className="p-3 font-medium">{m.manager_name}</td>
                    <td className="p-3">{m.team_size}</td>
                    <td className="p-3">{m.avg_approval_time_days} days</td>
                    <td className="p-3">{m.checkin_comment_rate}%</td>
                    <td className={`p-3 font-medium ${scoreBadgeClass(m.team_avg_score)}`}>
                      {m.team_avg_score}%
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-xl border bg-card p-6">
        <h2 className="mb-4 text-lg font-semibold">Employee Performance Heatmap</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="p-2 text-left">Employee</th>
                {QUARTERS.map((q) => (
                  <th key={q} className="p-2 text-center">
                    {q}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(data.employee_heatmap ?? []).map((row) => (
                <tr key={row.employee_id} className="border-b">
                  <td className="p-2 font-medium">{row.employee_name}</td>
                  {QUARTERS.map((q) => {
                    const key = `${q.toLowerCase()}_score`
                    const score = row[key]
                    return (
                      <td key={q} className="p-1">
                        <div
                          title={`${row.employee_name} — ${q}: ${score != null ? `${score}%` : "N/A"} (${statusLabel(score)})`}
                          className={`rounded px-2 py-2 text-center text-xs font-medium ${scoreColor(score)}`}
                        >
                          {score != null ? `${score}%` : "—"}
                        </div>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border bg-card p-6">
          <h2 className="mb-4 text-lg font-semibold">Top 5 Performers</h2>
          <div className="space-y-3">
            {(data.top_performers ?? []).map((p, i) => (
              <div
                key={p.employee_id}
                className="flex items-center justify-between rounded-lg border border-green-200 bg-green-50 p-4"
              >
                <div>
                  <p className="font-medium">
                    {MEDALS[i] ?? `${i + 1}.`} {p.employee_name}
                  </p>
                  <p className="text-sm text-muted-foreground">{p.manager_name}</p>
                </div>
                <span className={`rounded-full px-3 py-1 text-sm font-semibold ${scoreBadgeClass(p.avg_score)}`}>
                  {p.avg_score}%
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border bg-card p-6">
          <h2 className="mb-4 text-lg font-semibold">At Risk Employees</h2>
          <div className="space-y-3">
            {(data.at_risk_employees ?? []).length === 0 && (
              <p className="text-sm text-muted-foreground">No employees currently at risk.</p>
            )}
            {(data.at_risk_employees ?? []).map((e) => (
              <div
                key={e.employee_id}
                className="flex items-center justify-between rounded-lg border border-red-200 bg-red-50 p-4"
              >
                <div>
                  <p className="font-medium">{e.employee_name}</p>
                  <p className="text-sm text-muted-foreground">
                    {e.manager_name} · {e.at_risk_goals} at-risk goals
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-red-100 px-3 py-1 text-sm font-semibold text-red-800">
                    {e.avg_score}%
                  </span>
                  <Button size="sm" variant="outline" onClick={() => viewEmployee(e.employee_id)}>
                    View Details
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {detail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border bg-card p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">{detail.employee.name}</h2>
              <Button variant="outline" size="sm" onClick={() => setDetail(null)}>
                Close
              </Button>
            </div>
            <p className="text-sm text-muted-foreground">
              Overall: {detail.overall_avg_score}% · Best: {detail.best_quarter} · Worst:{" "}
              {detail.worst_quarter}
            </p>
            <ul className="mt-4 space-y-2 text-sm">
              {detail.goal_details?.map((g) => (
                <li key={g.goal_title} className="rounded border p-3">
                  <p className="font-medium">{g.goal_title}</p>
                  <p className="text-muted-foreground">
                    {g.thrust_area} · trend: {g.trend}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}

function KpiCard({ label, value, sub, className = "" }) {
  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${className}`}>{value}</p>
      {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
    </div>
  )
}
