const STATUS_STYLES = {
  draft: "bg-gray-100 text-gray-700 border-gray-200",
  submitted: "bg-blue-100 text-blue-800 border-blue-200",
  approved: "bg-green-100 text-green-800 border-green-200",
  returned: "bg-orange-100 text-orange-800 border-orange-200",
}

const STATUS_LABELS = {
  draft: "Draft",
  submitted: "Pending Approval",
  approved: "Approved 🔒",
  returned: "Returned — Needs Revision",
}

export default function GoalStatusBadge({ status, isLocked = false }) {
  const normalized = status?.toLowerCase() ?? "draft"
  const label =
    normalized === "approved" && isLocked
      ? STATUS_LABELS.approved
      : STATUS_LABELS[normalized] ?? status

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${
        STATUS_STYLES[normalized] ?? STATUS_STYLES.draft
      }`}
    >
      {label}
    </span>
  )
}
