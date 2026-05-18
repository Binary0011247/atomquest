const SIZES = {
  sm: "h-4 w-4 border-2",
  md: "h-8 w-8 border-[3px]",
  lg: "h-12 w-12 border-4",
}

export default function LoadingSpinner({ fullPage = false, size = "md", className = "" }) {
  const spinner = (
    <div
      className={`animate-spin rounded-full border-primary border-t-transparent ${SIZES[size] ?? SIZES.md} ${className}`}
      role="status"
      aria-label="Loading"
    />
  )

  if (fullPage) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3 text-muted-foreground">
        {spinner}
        <p className="text-sm">Loading...</p>
      </div>
    )
  }

  return spinner
}
