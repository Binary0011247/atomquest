import { useEffect, useState } from "react"

import { getScoreColor } from "@/utils/scoreCalculator"

const SIZE_CLASSES = {
  sm: { bar: "h-2", text: "text-xs" },
  md: { bar: "h-3", text: "text-sm" },
  lg: { bar: "h-4", text: "text-base" },
}

const COLOR_CLASSES = {
  green: "bg-green-500",
  yellow: "bg-amber-400",
  red: "bg-red-500",
}

export default function ProgressScoreBar({ score = 0, showLabel = true, size = "md" }) {
  const [width, setWidth] = useState(0)
  const numericScore = score ?? 0
  const color = getScoreColor(numericScore)
  const displayPercent = Math.min(numericScore, 100)
  const exceeded = numericScore > 100
  const sizeClass = SIZE_CLASSES[size] ?? SIZE_CLASSES.md

  useEffect(() => {
    const timer = setTimeout(() => setWidth(displayPercent), 50)
    return () => clearTimeout(timer)
  }, [displayPercent])

  return (
    <div className="flex w-full items-center gap-3">
      <div className={`relative flex-1 overflow-hidden rounded-full bg-muted ${sizeClass.bar}`}>
        <div
          className={`${sizeClass.bar} rounded-full transition-all duration-700 ease-out ${COLOR_CLASSES[color]}`}
          style={{ width: `${width}%` }}
        />
      </div>
      {showLabel && (
        <div className={`flex shrink-0 items-center gap-2 ${sizeClass.text}`}>
          <span className="font-medium tabular-nums">{numericScore.toFixed(1)}%</span>
          {exceeded && (
            <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
              Exceeded
            </span>
          )}
        </div>
      )}
    </div>
  )
}
