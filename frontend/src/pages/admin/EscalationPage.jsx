import { useCallback, useEffect, useState } from "react"

import api from "@/api/axios"
import { Button } from "@/components/ui/button"
import usePageTitle from "@/hooks/usePageTitle"

function SectionHeader({ color, title, count }) {
  const styles = {
    yellow: "border-amber-400 bg-amber-50 text-amber-900",
    orange: "border-orange-400 bg-orange-50 text-orange-900",
    red: "border-red-400 bg-red-50 text-red-900",
  }
  return (
    <div
      className={`flex items-center justify-between rounded-t-lg border-b-2 px-4 py-3 ${styles[color]}`}
    >
      <h2 className="text-lg font-semibold">{title}</h2>
      <span className="rounded-full bg-white/80 px-2.5 py-0.5 text-sm font-medium">{count}</span>
    </div>
  )
}

function EmptyRow({ cols, text }) {
  return (
    <tr>
      <td colSpan={cols} className="px-4 py-6 text-center text-sm text-muted-foreground">
        {text}
      </td>
    </tr>
  )
}

export default function EscalationPage() {
  usePageTitle("Escalations")
  const [data, setData] = useState({
    goal_not_submitted: [],
    approval_pending_too_long: [],
    checkin_not_logged: [],
    total_unresolved: 0,
  })
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [runMessage, setRunMessage] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data: res } = await api.get("/admin/escalations")
      setData(res)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function handleRunCheck() {
    setRunning(true)
    setRunMessage(null)
    try {
      const { data: res } = await api.post("/admin/escalations/run")
      setRunMessage(`Found ${res.new_escalations} new escalation(s).`)
      await load()
    } catch (err) {
      setRunMessage(err.response?.data?.detail || "Escalation check failed.")
    } finally {
      setRunning(false)
    }
  }

  async function handleResolve(id) {
    await api.post(`/admin/escalations/${id}/resolve`)
    await load()
  }

  if (loading) {
    return <p className="text-muted-foreground">Loading escalations...</p>
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Escalations</h1>
          <p className="text-sm text-muted-foreground">
            {data.total_unresolved} unresolved issue(s) requiring attention
          </p>
        </div>
        <Button onClick={handleRunCheck} disabled={running}>
          {running ? "Running…" : "🔄 Run Escalation Check Now"}
        </Button>
      </div>

      {runMessage && (
        <p className="rounded-md border border-primary/30 bg-primary/5 px-4 py-2 text-sm">
          {runMessage}
        </p>
      )}

      <section className="overflow-hidden rounded-lg border bg-card shadow-sm">
        <SectionHeader
          color="yellow"
          title="Goals Not Submitted"
          count={data.goal_not_submitted.length}
        />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">Employee</th>
                <th className="px-4 py-3 font-medium">Days Since Created</th>
                <th className="px-4 py-3 font-medium">Goal Count</th>
                <th className="px-4 py-3 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {data.goal_not_submitted.length === 0 ? (
                <EmptyRow cols={4} text="No unresolved goal submission escalations." />
              ) : (
                data.goal_not_submitted.map((row) => (
                  <tr key={row.id} className="border-b last:border-0">
                    <td className="px-4 py-3 font-medium">{row.employee_name}</td>
                    <td className="px-4 py-3">{row.days_since_created}</td>
                    <td className="px-4 py-3">{row.goal_count}</td>
                    <td className="px-4 py-3">
                      <Button size="sm" variant="outline" onClick={() => handleResolve(row.id)}>
                        Resolve
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="overflow-hidden rounded-lg border bg-card shadow-sm">
        <SectionHeader
          color="orange"
          title="Approvals Delayed"
          count={data.approval_pending_too_long.length}
        />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">Goal Title</th>
                <th className="px-4 py-3 font-medium">Employee</th>
                <th className="px-4 py-3 font-medium">Manager</th>
                <th className="px-4 py-3 font-medium">Days Waiting</th>
                <th className="px-4 py-3 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {data.approval_pending_too_long.length === 0 ? (
                <EmptyRow cols={5} text="No unresolved approval delays." />
              ) : (
                data.approval_pending_too_long.map((row) => (
                  <tr key={row.id} className="border-b last:border-0">
                    <td className="px-4 py-3 font-medium">{row.goal_title}</td>
                    <td className="px-4 py-3">{row.employee_name}</td>
                    <td className="px-4 py-3">{row.manager_name ?? "—"}</td>
                    <td className="px-4 py-3">{row.days_waiting}</td>
                    <td className="px-4 py-3">
                      <Button size="sm" variant="outline" onClick={() => handleResolve(row.id)}>
                        Resolve
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="overflow-hidden rounded-lg border bg-card shadow-sm">
        <SectionHeader
          color="red"
          title="Check-ins Missing"
          count={data.checkin_not_logged.length}
        />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">Employee</th>
                <th className="px-4 py-3 font-medium">Goal</th>
                <th className="px-4 py-3 font-medium">Quarter</th>
                <th className="px-4 py-3 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {data.checkin_not_logged.length === 0 ? (
                <EmptyRow cols={4} text="No unresolved check-in escalations." />
              ) : (
                data.checkin_not_logged.map((row) => (
                  <tr key={row.id} className="border-b last:border-0">
                    <td className="px-4 py-3 font-medium">{row.employee_name}</td>
                    <td className="px-4 py-3">{row.goal_title}</td>
                    <td className="px-4 py-3">{row.quarter}</td>
                    <td className="px-4 py-3">
                      <Button size="sm" variant="outline" onClick={() => handleResolve(row.id)}>
                        Resolve
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
