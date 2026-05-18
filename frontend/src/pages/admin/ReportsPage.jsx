import { useCallback, useEffect, useState } from "react"

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import api from "@/api/axios"
import { Button } from "@/components/ui/button"
import usePageTitle from "@/hooks/usePageTitle"

const PIE_COLORS = ["#22c55e", "#3b82f6", "#f97316", "#94a3b8"]

function scoreCellClass(score) {
  if (score == null) return ""
  if (score >= 90) return "bg-green-100"
  if (score >= 60) return "bg-yellow-100"
  return "bg-red-100"
}

export default function ReportsPage() {
  usePageTitle("Reports")
  const [achievement, setAchievement] = useState([])
  const [completion, setCompletion] = useState(null)
  const [dash, setDash] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [a, c, d] = await Promise.all([
        api.get("/admin/reports/achievement"),
        api.get("/admin/reports/completion"),
        api.get("/admin/dashboard"),
      ])
      setAchievement(a.data)
      setCompletion(c.data)
      setDash(d.data)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function exportCsv() {
    const res = await api.get("/admin/reports/achievement/export", { responseType: "blob" })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement("a")
    a.href = url
    a.download = `achievement_report_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
  }

  const checkinChartData = Object.entries(dash?.checkin_completion_rates ?? {}).map(
    ([quarter, rate]) => ({ quarter, rate }),
  )

  const pieData = Object.entries(completion?.goal_status_distribution ?? {}).map(
    ([name, value]) => ({ name, value }),
  )

  if (loading) return <p className="text-muted-foreground">Loading reports...</p>

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Reports</h1>
        <Button onClick={exportCsv}>Export CSV</Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border bg-card p-4">
          <h2 className="mb-4 font-medium">Check-in Completion by Quarter</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={checkinChartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="quarter" />
              <YAxis domain={[0, 100]} />
              <Tooltip />
              <Bar dataKey="rate" fill="#3b82f6" name="Completion %" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="rounded-xl border bg-card p-4">
          <h2 className="mb-4 font-medium">Goal Status Distribution</h2>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label>
                {pieData.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-xl border bg-card p-4">
          <h2 className="mb-3 font-medium">Goals by Thrust Area</h2>
          <table className="w-full text-sm">
            <tbody>
              {Object.entries(completion?.thrust_area_distribution ?? {}).map(([k, v]) => (
                <tr key={k} className="border-b">
                  <td className="py-2">{k}</td>
                  <td className="py-2 text-right font-medium">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="rounded-xl border bg-card p-4">
          <h2 className="mb-3 font-medium">Goals by UoM Type</h2>
          <table className="w-full text-sm">
            <tbody>
              {Object.entries(completion?.uom_type_distribution ?? {}).map(([k, v]) => (
                <tr key={k} className="border-b">
                  <td className="py-2">{k}</td>
                  <td className="py-2 text-right font-medium">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <section>
        <h2 className="mb-4 text-lg font-semibold">Achievement Report</h2>
        <div className="overflow-x-auto rounded-xl border bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50 text-left">
                <th className="p-2">Employee</th>
                <th className="p-2">Goal</th>
                <th className="p-2">Target</th>
                <th className="p-2">Q1</th>
                <th className="p-2">Q2</th>
                <th className="p-2">Q3</th>
                <th className="p-2">Q4</th>
                <th className="p-2">Overall</th>
              </tr>
            </thead>
            <tbody>
              {achievement.map((row, i) => (
                <tr key={i} className="border-b">
                  <td className="p-2">{row.employee_name}</td>
                  <td className="p-2">{row.goal_title}</td>
                  <td className="p-2">{row.target_value ?? row.target_date ?? "—"}</td>
                  {["q1_score", "q2_score", "q3_score", "q4_score", "overall_score"].map((key) => (
                    <td key={key} className={`p-2 text-center ${scoreCellClass(row[key])}`}>
                      {row[key] != null ? `${row[key]}%` : "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
