import { useCallback, useEffect, useMemo, useState } from "react"

import {
  approveAll,
  getManagerDashboard,
  getPendingApprovals,
  reviewGoal,
} from "@/api/approvals"
import { handleApiError } from "@/api/apiError"
import LoadingSpinner from "@/components/LoadingSpinner"
import { Button } from "@/components/ui/button"
import { useToast } from "@/context/ToastContext"
import usePageTitle from "@/hooks/usePageTitle"

const STATUS_LABELS = {
  not_started: { label: "Not Started", className: "bg-gray-100 text-gray-700" },
  partial: { label: "In Progress", className: "bg-yellow-100 text-yellow-800" },
  submitted: { label: "Awaiting Approval", className: "bg-blue-100 text-blue-800" },
  approved: { label: "All Approved ✅", className: "bg-green-100 text-green-800" },
  has_returned: { label: "Revision Needed", className: "bg-orange-100 text-orange-800" },
}

const UOM_LABELS = {
  numeric_min: "Numeric Min",
  numeric_max: "Numeric Max",
  timeline: "Timeline",
  zero: "Zero Based",
}

function formatTarget(goal) {
  if (goal.uom_type === "timeline" && goal.target_date) {
    return goal.target_date
  }
  if (goal.uom_type === "zero") return "Zero = success"
  if (goal.target_value != null) return String(goal.target_value)
  return "—"
}

function buildApprovePayload(goal, editFields) {
  const body = { action: "approved" }
  if (
    (goal.uom_type === "numeric_min" || goal.uom_type === "numeric_max") &&
    editFields.edited_target_value !== "" &&
    Number(editFields.edited_target_value) !== goal.target_value
  ) {
    body.edited_target_value = Number(editFields.edited_target_value)
  }
  if (
    goal.uom_type === "timeline" &&
    editFields.edited_target_date !== "" &&
    editFields.edited_target_date !== goal.target_date
  ) {
    body.edited_target_date = editFields.edited_target_date
  }
  if (
    editFields.edited_weightage !== "" &&
    Number(editFields.edited_weightage) !== goal.weightage
  ) {
    body.edited_weightage = Number(editFields.edited_weightage)
  }
  return body
}

function Modal({ open, onClose, title, children }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl border bg-card p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            disabled={false}
            className="text-muted-foreground hover:text-foreground"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

export default function ManagerDashboard() {
  usePageTitle("Team Overview")
  const toast = useToast()
  const [dashboard, setDashboard] = useState(null)
  const [pendingGroups, setPendingGroups] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedEmployee, setExpandedEmployee] = useState(null)
  const [activeGoal, setActiveGoal] = useState(null)
  const [activeMember, setActiveMember] = useState(null)
  const [modalMode, setModalMode] = useState(null)
  const [bulkConfirm, setBulkConfirm] = useState(null)
  const [approvingEmployeeId, setApprovingEmployeeId] = useState(null)
  const [returnComment, setReturnComment] = useState("")
  const [editFields, setEditFields] = useState({
    edited_target_value: "",
    edited_target_date: "",
    edited_weightage: "",
  })
  const [submitting, setSubmitting] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [dashRes, pendingRes] = await Promise.all([
        getManagerDashboard(),
        getPendingApprovals(),
      ])
      setDashboard(dashRes.data)
      setPendingGroups(pendingRes.data.groups ?? [])
    } catch (err) {
      handleApiError(err, toast)
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    loadData()
  }, [loadData])

  const fullyApproved = useMemo(() => {
    if (!dashboard?.team_summary) return 0
    return dashboard.team_summary.filter((m) => m.submission_status === "approved").length
  }, [dashboard])

  function openApprove(goal, member) {
    setActiveGoal(goal)
    setActiveMember(member)
    setModalMode("approve")
    setEditFields({
      edited_target_value: "",
      edited_target_date: "",
      edited_weightage: "",
    })
  }

  function openReturn(goal, member) {
    setActiveGoal(goal)
    setActiveMember(member)
    setModalMode("return")
    setReturnComment("")
  }

  function closeModal() {
    if (submitting) return
    setActiveGoal(null)
    setActiveMember(null)
    setModalMode(null)
    setReturnComment("")
    setEditFields({
      edited_target_value: "",
      edited_target_date: "",
      edited_weightage: "",
    })
  }

  async function confirmApprove() {
    if (!activeGoal) return
    setSubmitting(true)
    try {
      const body = buildApprovePayload(activeGoal, editFields)
      await reviewGoal(activeGoal.id, body)
      toast.success("Goal approved and locked ✅")
      closeModal()
      await loadData()
    } catch (err) {
      handleApiError(err, toast)
    } finally {
      setSubmitting(false)
    }
  }

  async function confirmReturn() {
    if (!activeGoal || !returnComment.trim()) return
    setSubmitting(true)
    try {
      await reviewGoal(activeGoal.id, {
        action: "returned",
        comment: returnComment.trim(),
      })
      toast.warning("Goal returned to employee ↩️")
      closeModal()
      await loadData()
    } catch (err) {
      handleApiError(err, toast)
    } finally {
      setSubmitting(false)
    }
  }

  function openBulkConfirm(employeeId, employeeName, count) {
    setBulkConfirm({ employeeId, employeeName, count })
  }

  function closeBulkConfirm() {
    if (approvingEmployeeId) return
    setBulkConfirm(null)
  }

  async function confirmBulkApprove() {
    if (!bulkConfirm) return
    setApprovingEmployeeId(bulkConfirm.employeeId)
    try {
      const data = await approveAll(bulkConfirm.employeeId)
      toast.success(
        `✅ All ${data.approved_count} goals approved for ${data.employee_name}`,
      )
      setBulkConfirm(null)
      await loadData()
    } catch (err) {
      handleApiError(err, toast)
    } finally {
      setApprovingEmployeeId(null)
    }
  }

  const totalPending = dashboard?.pending_approvals_count ?? 0
  const isBulkLoading = (employeeId) => approvingEmployeeId === employeeId
  const anyActionLoading = submitting || approvingEmployeeId != null

  if (loading) return <LoadingSpinner fullPage />

  const goal = activeGoal
  const uom = goal?.uom_type

  return (
    <div className="mx-auto max-w-5xl space-y-8 pb-8">
      <h1 className="text-2xl font-semibold">Manager Dashboard</h1>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard icon="👥" label="Team Members" value={dashboard?.total_team_members ?? 0} />
        <StatCard
          icon="⏳"
          label="Pending Approvals"
          value={dashboard?.pending_approvals_count ?? 0}
          highlight={(dashboard?.pending_approvals_count ?? 0) > 0}
        />
        <StatCard icon="✅" label="Fully Approved" value={fullyApproved} />
      </div>

      {totalPending === 0 && (dashboard?.team_summary?.length ?? 0) > 0 && (
        <div className="rounded-xl border border-green-200 bg-green-50 px-6 py-4 text-center text-green-900">
          <p className="text-lg font-semibold">🎉 All team goals have been reviewed!</p>
        </div>
      )}

      {pendingGroups.length > 0 && (
        <section className="rounded-xl border-2 border-blue-200 bg-blue-50/40 p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-blue-900">
              ⏳ Pending Approvals
              <span className="rounded-full bg-blue-600 px-2.5 py-0.5 text-sm text-white">
                {totalPending}
              </span>
            </h2>
            {pendingGroups.length === 1 && (
              <ApproveAllButton
                label={`✅ Approve All (${pendingGroups[0].submitted_goals_count})`}
                loading={isBulkLoading(pendingGroups[0].employee_id)}
                disabled={anyActionLoading && !isBulkLoading(pendingGroups[0].employee_id)}
                onClick={() =>
                  openBulkConfirm(
                    pendingGroups[0].employee_id,
                    pendingGroups[0].employee_name,
                    pendingGroups[0].submitted_goals_count,
                  )
                }
              />
            )}
          </div>

          <div className="space-y-6">
            {pendingGroups.map((group) => (
              <div key={group.employee_id} className="space-y-3">
                {pendingGroups.length > 1 && (
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-blue-900">
                      {group.employee_name}{" "}
                      <span className="font-normal text-muted-foreground">
                        ({group.submitted_goals_count} goals)
                      </span>
                    </p>
                    <ApproveAllButton
                      label={`✅ Approve All (${group.submitted_goals_count})`}
                      loading={isBulkLoading(group.employee_id)}
                      disabled={anyActionLoading && !isBulkLoading(group.employee_id)}
                      onClick={() =>
                        openBulkConfirm(
                          group.employee_id,
                          group.employee_name,
                          group.submitted_goals_count,
                        )
                      }
                    />
                  </div>
                )}
                {group.goals.map((g) => (
                  <PendingGoalCard
                    key={g.id}
                    item={{
                      goal: g,
                      employee_id: group.employee_id,
                      employee_name: group.employee_name,
                      employee_email: group.employee_email,
                    }}
                    disabled={anyActionLoading}
                    onApprove={() =>
                      openApprove(g, {
                        employee_id: group.employee_id,
                        employee_name: group.employee_name,
                        employee_email: group.employee_email,
                      })
                    }
                    onReturn={() =>
                      openReturn(g, {
                        employee_id: group.employee_id,
                        employee_name: group.employee_name,
                        employee_email: group.employee_email,
                      })
                    }
                  />
                ))}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Team overview */}
      <section>
        <h2 className="mb-4 text-lg font-semibold">👥 Team Overview</h2>
        <div className="space-y-4">
          {(dashboard?.team_summary ?? []).length === 0 && (
            <p className="text-center text-muted-foreground">No employees assigned to you yet.</p>
          )}
          {(dashboard?.team_summary ?? []).map((member) => {
            const status = STATUS_LABELS[member.submission_status] ?? STATUS_LABELS.not_started
            const expanded = expandedEmployee === member.employee_id
            const submittedCount = member.submitted_goals ?? 0
            return (
              <div key={member.employee_id} className="flex flex-col rounded-xl border bg-card p-5 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="font-medium">{member.employee_name}</h3>
                    <p className="text-sm text-muted-foreground">{member.employee_email}</p>
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
                    {submittedCount > 0 && (
                      <ApproveAllButton
                        label={`✅ Approve All (${submittedCount})`}
                        loading={isBulkLoading(member.employee_id)}
                        disabled={anyActionLoading && !isBulkLoading(member.employee_id)}
                        onClick={() =>
                          openBulkConfirm(
                            member.employee_id,
                            member.employee_name,
                            submittedCount,
                          )
                        }
                      />
                    )}
                    <span className={`rounded-full px-3 py-1 text-xs font-medium ${status.className}`}>
                      {status.label}
                    </span>
                  </div>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  {member.total_goals} goals | {member.total_weightage}% total weightage
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  className="mt-3"
                  onClick={() =>
                    setExpandedEmployee(expanded ? null : member.employee_id)
                  }
                >
                  {expanded ? "Hide Goals" : "View All Goals"}
                </Button>

                {expanded && (
                  <div className="mt-4 border-t pt-4">
                    {submittedCount > 0 && (
                      <div className="mb-3 flex justify-end">
                        <ApproveAllButton
                          label={`✅ Approve All (${submittedCount})`}
                          loading={isBulkLoading(member.employee_id)}
                          disabled={anyActionLoading && !isBulkLoading(member.employee_id)}
                          onClick={() =>
                            openBulkConfirm(
                              member.employee_id,
                              member.employee_name,
                              submittedCount,
                            )
                          }
                        />
                      </div>
                    )}
                    <div className="overflow-x-auto">
                    {member.goals.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No goals yet.</p>
                    ) : (
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-left text-muted-foreground">
                            <th className="p-2">Goal Title</th>
                            <th className="p-2">Thrust Area</th>
                            <th className="p-2">UoM</th>
                            <th className="p-2">Target</th>
                            <th className="p-2">Weightage</th>
                            <th className="p-2">Status</th>
                            <th className="p-2">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {member.goals.map((g) => (
                            <tr key={g.id} className="border-b">
                              <td className="p-2 font-medium">{g.title}</td>
                              <td className="p-2">{g.thrust_area}</td>
                              <td className="p-2">{UOM_LABELS[g.uom_type] ?? g.uom_type}</td>
                              <td className="p-2">{formatTarget(g)}</td>
                              <td className="p-2">{g.weightage}%</td>
                              <td className="p-2">
                                <GoalRowStatus status={g.status} isLocked={g.is_locked} />
                              </td>
                              <td className="p-2">
                                <GoalRowActions
                                  goal={g}
                                  disabled={anyActionLoading}
                                  onApprove={() => openApprove(g, member)}
                                  onReturn={() => openReturn(g, member)}
                                />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                    </div>
                  </div>
                )}

              </div>
            )
          })}
        </div>
      </section>

      {/* Approve modal */}
      <Modal open={modalMode === "approve"} onClose={closeModal} title="Review & Approve Goal">
        {goal && (
          <div className="space-y-4">
            <div className="rounded-lg bg-muted/50 p-4 text-sm">
              <p>
                <span className="font-medium">Goal Title:</span> {goal.title}
              </p>
              <p>
                <span className="font-medium">Thrust Area:</span> {goal.thrust_area}
              </p>
              <p>
                <span className="font-medium">UoM Type:</span> {UOM_LABELS[uom] ?? uom}
              </p>
              <p>
                <span className="font-medium">Current Target:</span> {formatTarget(goal)}
              </p>
              <p>
                <span className="font-medium">Weightage:</span> {goal.weightage}%
              </p>
              {activeMember && (
                <p className="mt-1 text-muted-foreground">
                  {activeMember.employee_name ?? activeMember.employee_email}
                </p>
              )}
            </div>

            <div className="space-y-3 border-t pt-4">
              <p className="text-sm font-medium">Optional: Edit before approving</p>
              {(uom === "numeric_min" || uom === "numeric_max") && (
                <label className="block text-sm">
                  Edit Target Value
                  <input
                    type="number"
                    className="mt-1 w-full rounded-md border px-3 py-2"
                    placeholder={goal.target_value != null ? String(goal.target_value) : ""}
                    value={editFields.edited_target_value}
                    disabled={submitting}
                    onChange={(e) =>
                      setEditFields((f) => ({ ...f, edited_target_value: e.target.value }))
                    }
                  />
                </label>
              )}
              {uom === "timeline" && (
                <label className="block text-sm">
                  Edit Target Date
                  <input
                    type="date"
                    className="mt-1 w-full rounded-md border px-3 py-2"
                    placeholder={goal.target_date ?? ""}
                    value={editFields.edited_target_date}
                    disabled={submitting}
                    onChange={(e) =>
                      setEditFields((f) => ({ ...f, edited_target_date: e.target.value }))
                    }
                  />
                </label>
              )}
              <label className="block text-sm">
                Edit Weightage
                <input
                  type="number"
                  min={10}
                  max={100}
                  className="mt-1 w-full rounded-md border px-3 py-2"
                  placeholder={String(goal.weightage)}
                  value={editFields.edited_weightage}
                  disabled={submitting}
                  onChange={(e) =>
                    setEditFields((f) => ({ ...f, edited_weightage: e.target.value }))
                  }
                />
              </label>
              <p className="text-xs text-muted-foreground">Leave fields empty to approve as-is</p>
            </div>

            <div className="flex gap-2 pt-2">
              <Button variant="outline" className="flex-1" disabled={submitting} onClick={closeModal}>
                Cancel
              </Button>
              <Button className="flex-1" disabled={submitting} onClick={confirmApprove}>
                {submitting ? <LoadingSpinner size="sm" /> : "Confirm Approve"}
              </Button>
            </div>
          </div>
        )}
      </Modal>

      <Modal open={Boolean(bulkConfirm)} onClose={closeBulkConfirm} title="Approve All Goals?">
        {bulkConfirm && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              You are about to approve all {bulkConfirm.count} submitted goals for{" "}
              <span className="font-medium text-foreground">{bulkConfirm.employeeName}</span>.
              All goals will be locked and cannot be edited without Admin intervention.
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                className="flex-1"
                disabled={approvingEmployeeId != null}
                onClick={closeBulkConfirm}
              >
                Cancel
              </Button>
              <Button
                className="flex-1 bg-green-600 hover:bg-green-700"
                disabled={approvingEmployeeId != null}
                onClick={confirmBulkApprove}
              >
                {approvingEmployeeId ? (
                  <span className="flex items-center justify-center gap-2">
                    <LoadingSpinner size="sm" /> Approving...
                  </span>
                ) : (
                  "Approve All"
                )}
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Return modal */}
      <Modal open={modalMode === "return"} onClose={closeModal} title="Return Goal for Revision">
        {goal && (
          <div className="space-y-4">
            <p className="font-medium">{goal.title}</p>
            <label className="block text-sm font-medium">
              Reason for returning (required)
              <textarea
                className="mt-1 w-full rounded-md border px-3 py-2"
                rows={5}
                style={{ minHeight: 100 }}
                placeholder="Explain what needs to be changed..."
                value={returnComment}
                disabled={submitting}
                onChange={(e) => setReturnComment(e.target.value)}
              />
            </label>
            <p className="text-xs text-muted-foreground">{returnComment.length} characters</p>
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" disabled={submitting} onClick={closeModal}>
                Cancel
              </Button>
              <Button
                className="flex-1"
                variant="destructive"
                disabled={submitting || !returnComment.trim()}
                onClick={confirmReturn}
              >
                {submitting ? "Returning..." : "Return to Employee"}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

function PendingGoalCard({ item, onApprove, onReturn, disabled }) {
  const g = item.goal
  return (
    <article className="rounded-lg border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="text-sm font-medium text-muted-foreground">
            {item.employee_name} · {item.employee_email}
          </p>
          <h3 className="text-lg font-bold">{g.title}</h3>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs">{g.thrust_area}</span>
            <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700">
              {UOM_LABELS[g.uom_type] ?? g.uom_type}
            </span>
          </div>
          <p className="text-sm">
            Target: {formatTarget(g)} · Weightage: {g.weightage}%
          </p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" disabled={disabled} onClick={onApprove}>
            ✅ Approve
          </Button>
          <Button size="sm" variant="outline" disabled={disabled} onClick={onReturn}>
            ↩️ Return
          </Button>
        </div>
      </div>
    </article>
  )
}

function GoalRowStatus({ status, isLocked }) {
  if (status === "approved") return <span className="text-green-700">Approved 🔒</span>
  if (status === "returned") return <span className="text-orange-700">Returned ↩️</span>
  if (status === "submitted") return <span className="text-blue-700">Pending</span>
  if (status === "draft") return <span className="text-gray-500">Not Submitted Yet</span>
  return <span>{status}</span>
}

function GoalRowActions({ goal, onApprove, onReturn, disabled }) {
  if (goal.status === "submitted") {
    return (
      <div className="flex gap-1">
        <Button size="sm" variant="ghost" disabled={disabled} onClick={onApprove}>
          Approve
        </Button>
        <Button size="sm" variant="ghost" disabled={disabled} onClick={onReturn}>
          Return
        </Button>
      </div>
    )
  }
  if (goal.status === "approved") return <span className="text-xs text-green-700">Approved 🔒</span>
  if (goal.status === "returned") return <span className="text-xs text-orange-700">Returned ↩️</span>
  if (goal.status === "draft") return <span className="text-xs text-gray-500">Not Submitted Yet</span>
  return null
}

function ApproveAllButton({ label, onClick, loading, disabled, className = "" }) {
  return (
    <Button
      size="sm"
      className={`shrink-0 whitespace-nowrap bg-green-600 text-white hover:bg-green-700 ${className}`}
      disabled={disabled || loading}
      onClick={onClick}
    >
      {loading ? (
        <span className="flex items-center justify-center gap-2">
          <LoadingSpinner size="sm" />
          Approving...
        </span>
      ) : (
        label
      )}
    </Button>
  )
}

function StatCard({ icon, label, value, highlight }) {
  return (
    <div
      className={`rounded-xl border p-5 shadow-sm ${
        highlight ? "border-red-200 bg-red-50" : "bg-card"
      }`}
    >
      <p className="text-sm text-muted-foreground">
        {icon} {label}
      </p>
      <p className={`mt-1 text-3xl font-semibold ${highlight ? "text-red-700" : ""}`}>{value}</p>
    </div>
  )
}
