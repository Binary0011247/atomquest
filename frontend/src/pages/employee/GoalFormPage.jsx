import { useCallback, useEffect, useMemo, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"

import api from "@/api/axios"
import ButtonSpinner from "@/components/ButtonSpinner"
import LoadingSpinner from "@/components/LoadingSpinner"
import { Button } from "@/components/ui/button"
import { useToast } from "@/context/ToastContext"
import usePageTitle from "@/hooks/usePageTitle"
import { getWeightageStatus } from "@/utils/scoreCalculator"

const THRUST_AREAS = [
  "Sales",
  "Operations",
  "Safety",
  "HR",
  "Finance",
  "Technology",
  "Customer Service",
]

const UOM_OPTIONS = [
  {
    value: "numeric_min",
    icon: "📈",
    label: "Numeric Min",
    desc: "Higher is better (e.g. Revenue, Units Sold)",
  },
  {
    value: "numeric_max",
    icon: "📉",
    label: "Numeric Max",
    desc: "Lower is better (e.g. Cost, TAT)",
  },
  {
    value: "timeline",
    icon: "📅",
    label: "Timeline",
    desc: "Completion by a target date",
  },
  {
    value: "zero",
    icon: "🎯",
    label: "Zero Based",
    desc: "Zero = Success (e.g. Safety Incidents)",
  },
]

const emptyForm = {
  thrust_area: "",
  title: "",
  description: "",
  uom_type: "",
  target_value: "",
  target_date: "",
  weightage: "",
}

export default function GoalFormPage() {
  const { id } = useParams()
  const isEdit = Boolean(id)
  usePageTitle(isEdit ? "Edit Goal" : "Create Goal")
  const toast = useToast()
  const navigate = useNavigate()

  const [goals, setGoals] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})
  const [form, setForm] = useState(emptyForm)
  const [editStatus, setEditStatus] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [myGoals, goalRes] = await Promise.all([
        api.get("/goals/my"),
        isEdit ? api.get(`/goals/${id}`) : Promise.resolve(null),
      ])
      setGoals(myGoals.data.goals ?? [])

      if (isEdit && goalRes) {
        const goal = goalRes.data
        if (goal.is_locked || goal.status === "approved") {
          toast.error("This goal is locked and cannot be edited")
          navigate("/employee/dashboard", { replace: true })
          return
        }
        if (goal.status === "submitted") {
          toast.error("Submitted goals cannot be edited")
          navigate("/employee/dashboard", { replace: true })
          return
        }
        setEditStatus(goal.status)
        setForm({
          thrust_area: goal.thrust_area ?? "",
          title: goal.title ?? "",
          description: goal.description ?? "",
          uom_type: goal.uom_type ?? "",
          target_value: goal.target_value != null ? String(goal.target_value) : "",
          target_date: goal.target_date ?? "",
          weightage: goal.weightage != null ? String(goal.weightage) : "",
        })
      }
    } catch {
      toast.error(isEdit ? "Failed to load goal" : "Failed to load goals")
      if (isEdit) navigate("/employee/dashboard", { replace: true })
    } finally {
      setLoading(false)
    }
  }, [id, isEdit, navigate, toast])

  useEffect(() => {
    load()
  }, [load])

  const otherGoals = useMemo(
    () => (isEdit ? goals.filter((g) => String(g.id) !== String(id)) : goals),
    [goals, id, isEdit],
  )
  const otherTotal = useMemo(
    () => otherGoals.reduce((s, g) => s + (g.weightage ?? 0), 0),
    [otherGoals],
  )
  const projectedTotal = useMemo(() => {
    const w = Number(form.weightage) || 0
    return Math.round((otherTotal + w) * 100) / 100
  }, [otherTotal, form.weightage])
  const remaining = Math.round((100 - projectedTotal) * 100) / 100

  function validate() {
    const e = {}
    if (!form.title.trim()) e.title = "Title is required"
    if (!form.thrust_area.trim()) e.thrust_area = "Thrust area is required"
    if (!form.uom_type) e.uom_type = "Select a unit of measurement"
    if (
      (form.uom_type === "numeric_min" || form.uom_type === "numeric_max") &&
      form.target_value === ""
    ) {
      e.target_value = "Target value is required"
    }
    if (form.uom_type === "timeline" && !form.target_date) {
      e.target_date = "Target date is required"
    }
    const w = Number(form.weightage)
    if (!form.weightage || Number.isNaN(w)) {
      e.weightage = "Weightage is required"
    } else if (w < 10) {
      e.weightage = "Minimum weightage is 10%"
    } else if (projectedTotal > 100) {
      e.weightage = `This would bring your total to ${projectedTotal}% (max 100%)`
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (saving) return
    if (!validate()) return

    setSaving(true)
    const payload = {
      thrust_area: form.thrust_area.trim(),
      title: form.title.trim(),
      description: form.description.trim() || null,
      uom_type: form.uom_type,
      weightage: Number(form.weightage),
      target_value:
        form.uom_type === "numeric_min" || form.uom_type === "numeric_max"
          ? Number(form.target_value)
          : null,
      target_date: form.uom_type === "timeline" ? form.target_date : null,
    }

    try {
      if (isEdit) {
        await api.put(`/goals/${id}`, payload)
        if (editStatus === "returned") {
          await api.post(`/goals/${id}/submit`)
          toast.success("Goal updated and resubmitted for approval")
        } else {
          toast.success("Goal updated")
        }
      } else {
        await api.post("/goals/", payload)
        toast.success("Goal created successfully")
        setForm(emptyForm)
        setErrors({})
      }
      navigate("/employee/dashboard")
    } catch (err) {
      toast.error(err.response?.data?.detail ?? "Failed to save goal")
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingSpinner fullPage />

  return (
    <div className="mx-auto max-w-2xl space-y-6 pb-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{isEdit ? "Edit Goal" : "Create Goal"}</h1>
        <Link to="/employee/dashboard" className="text-sm text-primary hover:underline">
          ← Back to dashboard
        </Link>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <section className="space-y-4 rounded-xl border bg-card p-6">
          <label className="block text-sm font-medium">
            Thrust Area
            <select
              className={`mt-1 w-full rounded-md border px-3 py-2 ${errors.thrust_area ? "border-red-500" : ""}`}
              value={form.thrust_area}
              onChange={(e) => setForm((f) => ({ ...f, thrust_area: e.target.value }))}
            >
              <option value="">Select thrust area</option>
              {THRUST_AREAS.map((area) => (
                <option key={area} value={area}>
                  {area}
                </option>
              ))}
            </select>
            {errors.thrust_area && <p className="mt-1 text-xs text-red-600">{errors.thrust_area}</p>}
          </label>

          <Field
            label="Goal Title"
            value={form.title}
            error={errors.title}
            required
            onChange={(v) => setForm((f) => ({ ...f, title: v }))}
          />

          <label className="block text-sm font-medium">
            Description <span className="font-normal text-muted-foreground">(optional)</span>
            <textarea
              className="mt-1 w-full rounded-md border px-3 py-2"
              rows={3}
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
          </label>
        </section>

        <section className="space-y-4 rounded-xl border bg-card p-6">
          <p className="text-sm font-medium">Unit of Measurement</p>
          {errors.uom_type && <p className="text-xs text-red-600">{errors.uom_type}</p>}
          <div className="grid gap-3 sm:grid-cols-2">
            {UOM_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setForm((f) => ({ ...f, uom_type: opt.value }))}
                className={`rounded-lg border p-4 text-left transition-colors ${
                  form.uom_type === opt.value ? "border-primary ring-2 ring-primary/30" : "hover:bg-muted/50"
                }`}
              >
                <span className="text-2xl">{opt.icon}</span>
                <p className="mt-2 font-medium">{opt.label}</p>
                <p className="text-xs text-muted-foreground">{opt.desc}</p>
              </button>
            ))}
          </div>

          {(form.uom_type === "numeric_min" || form.uom_type === "numeric_max") && (
            <Field
              label="Target Value"
              type="number"
              value={form.target_value}
              error={errors.target_value}
              onChange={(v) => setForm((f) => ({ ...f, target_value: v }))}
            />
          )}
          {form.uom_type === "timeline" && (
            <Field
              label="Target Date"
              type="date"
              value={form.target_date}
              error={errors.target_date}
              onChange={(v) => setForm((f) => ({ ...f, target_date: v }))}
            />
          )}
        </section>

        <section className="space-y-3 rounded-xl border bg-card p-6">
          <Field
            label="Weightage (%)"
            type="number"
            min={10}
            max={100}
            value={form.weightage}
            error={errors.weightage}
            onChange={(v) => setForm((f) => ({ ...f, weightage: v }))}
          />
          <p className="text-sm text-muted-foreground">
            You have{" "}
            <span className={remaining < 0 ? "font-medium text-red-600" : "font-medium"}>
              {remaining < 0 ? 0 : remaining}%
            </span>{" "}
            remaining across all your goals
          </p>
          {projectedTotal > 100 && (
            <p className="text-sm text-red-600">
              Warning: total weightage would be {projectedTotal}% (maximum is 100%)
            </p>
          )}
        </section>

        <Button type="submit" className="w-full" size="lg" disabled={saving}>
          {saving ? (
            <span className="inline-flex items-center gap-2">
              <ButtonSpinner />
              Saving...
            </span>
          ) : isEdit
              ? editStatus === "returned"
                ? "Update & Resubmit"
                : "Update Goal"
              : "Save Goal"}
        </Button>
      </form>
    </div>
  )
}

function Field({ label, value, onChange, type = "text", error, required, min, max }) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <input
        type={type}
        min={min}
        max={max}
        required={required}
        className={`mt-1 w-full rounded-md border px-3 py-2 ${error ? "border-red-500" : ""}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </label>
  )
}
