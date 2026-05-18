import { Fragment, useCallback, useEffect, useState } from "react"

import api from "@/api/axios"
import { Button } from "@/components/ui/button"
import usePageTitle from "@/hooks/usePageTitle"

export default function AuditLogPage() {
  usePageTitle("Audit Logs")
  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(50)
  const [expanded, setExpanded] = useState({})
  const [filters, setFilters] = useState({
    entity: "",
    from_date: "",
    to_date: "",
    search: "",
  })
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, page_size: pageSize }
      if (filters.entity) params.entity = filters.entity
      if (filters.from_date) params.from_date = filters.from_date
      if (filters.to_date) params.to_date = filters.to_date
      if (filters.search) params.search = filters.search
      const { data } = await api.get("/admin/audit-logs", { params })
      setLogs(data.logs)
      setTotal(data.total)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, filters])

  useEffect(() => {
    load()
  }, [load])

  async function exportCsv() {
    const params = { page: 1, page_size: 500 }
    if (filters.entity) params.entity = filters.entity
    if (filters.from_date) params.from_date = filters.from_date
    if (filters.to_date) params.to_date = filters.to_date
    if (filters.search) params.search = filters.search
    const { data } = await api.get("/admin/audit-logs", { params })
    const header = "Timestamp,Entity,Entity ID,Changed By,Description\n"
    const rows = data.logs
      .map(
        (l) =>
          `"${l.changed_at}","${l.entity}",${l.entity_id},"${l.changed_by_name}","${l.change_description.replace(/"/g, '""')}"`,
      )
      .join("\n")
    const blob = new Blob([header + rows], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `audit_logs_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Audit Logs</h1>

      <div className="flex flex-wrap gap-3 rounded-xl border bg-card p-4">
        <select
          className="rounded-md border px-3 py-2 text-sm"
          value={filters.entity}
          onChange={(e) => setFilters((f) => ({ ...f, entity: e.target.value }))}
        >
          <option value="">All entities</option>
          <option value="goal">Goal</option>
          <option value="checkin">Checkin</option>
          <option value="user">User</option>
          <option value="admin">Admin</option>
        </select>
        <input
          type="date"
          className="rounded-md border px-3 py-2 text-sm"
          value={filters.from_date}
          onChange={(e) => setFilters((f) => ({ ...f, from_date: e.target.value }))}
        />
        <input
          type="date"
          className="rounded-md border px-3 py-2 text-sm"
          value={filters.to_date}
          onChange={(e) => setFilters((f) => ({ ...f, to_date: e.target.value }))}
        />
        <input
          type="search"
          placeholder="Search by user name"
          className="rounded-md border px-3 py-2 text-sm"
          value={filters.search}
          onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
        />
        <Button
          variant="outline"
          onClick={() => {
            setFilters({ entity: "", from_date: "", to_date: "", search: "" })
            setPage(1)
          }}
        >
          Reset
        </Button>
        <Button onClick={() => { setPage(1); load() }}>Apply</Button>
        <Button variant="secondary" onClick={exportCsv}>
          Export CSV
        </Button>
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50 text-left">
                <th className="p-3 w-8" />
                <th className="p-3">Timestamp</th>
                <th className="p-3">Entity</th>
                <th className="p-3">Action</th>
                <th className="p-3">Changed By</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <Fragment key={log.id}>
                  <tr
                    className="cursor-pointer border-b hover:bg-muted/30"
                    onClick={() =>
                      setExpanded((e) => ({ ...e, [log.id]: !e[log.id] }))
                    }
                  >
                    <td className="p-3">{expanded[log.id] ? "▼" : "▶"}</td>
                    <td className="p-3">{new Date(log.changed_at).toLocaleString()}</td>
                    <td className="p-3 capitalize">{log.entity}</td>
                    <td className="p-3 max-w-md truncate">{log.change_description}</td>
                    <td className="p-3">{log.changed_by_name}</td>
                  </tr>
                  {expanded[log.id] && (
                    <tr className="border-b bg-muted/20">
                      <td colSpan={5} className="p-3 text-sm text-muted-foreground">
                        {log.change_description}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Page {page} of {totalPages} ({total} total)
        </p>
        <div className="flex gap-2">
          <Button variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Previous
          </Button>
          <Button
            variant="outline"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
