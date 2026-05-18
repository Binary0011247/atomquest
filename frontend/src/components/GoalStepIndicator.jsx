const STEPS = ["draft", "submitted", "approved"]

export default function GoalStepIndicator({ status }) {
  const normalized = status?.toLowerCase() ?? "draft"
  const isReturned = normalized === "returned"

  const activeIndex = isReturned
    ? 1
    : normalized === "approved"
      ? 2
      : normalized === "submitted"
        ? 1
        : 0

  return (
    <div className="flex flex-wrap items-center gap-1 text-[10px] text-muted-foreground">
      {STEPS.map((step, index) => {
        const isActive = !isReturned && index <= activeIndex
        const isReturnStep = isReturned && index === 1
        return (
          <div key={step} className="flex items-center gap-1">
            <span
              className={`rounded-full px-2 py-0.5 ${
                isReturnStep
                  ? "bg-orange-100 text-orange-800"
                  : isActive
                    ? "bg-primary/10 font-medium text-primary"
                    : "bg-muted"
              }`}
            >
              {isReturnStep ? "returned" : step}
            </span>
            {index < STEPS.length - 1 && <span>→</span>}
          </div>
        )
      })}
      {isReturned && <span className="text-orange-600">→ edit → resubmit</span>}
    </div>
  )
}
