/**
 * Goal progress score and weightage helpers (mirrors backend/utils.py).
 */

export function calculateProgressScore(
  uomType,
  targetValue,
  actualValue,
  targetDate,
  actualDate,
) {
  if (uomType === "numeric_min") {
    if (targetValue == null || actualValue == null || targetValue === 0) {
      return 0
    }
    return Math.round((actualValue / targetValue) * 100 * 100) / 100
  }

  if (uomType === "numeric_max") {
    if (targetValue == null || actualValue == null) {
      return 0
    }
    if (actualValue === 0) {
      return 100
    }
    return Math.round((targetValue / actualValue) * 100 * 100) / 100
  }

  if (uomType === "timeline") {
    if (!targetDate || !actualDate) {
      return 0
    }
    const target = new Date(targetDate)
    const actual = new Date(actualDate)
    return actual <= target ? 100 : 0
  }

  if (uomType === "zero") {
    if (actualValue == null) {
      return 0
    }
    return actualValue === 0 ? 100 : 0
  }

  return 0
}

export function getScoreColor(score) {
  if (score >= 90) {
    return "green"
  }
  if (score >= 60) {
    return "yellow"
  }
  return "red"
}

export function getCurrentQuarter() {
  const month = new Date().getMonth() + 1
  const quarterMap = {
    7: "Q1",
    8: "Q1",
    9: "Q1",
    10: "Q2",
    11: "Q2",
    12: "Q2",
    1: "Q3",
    2: "Q3",
    3: "Q3",
    4: "Q4",
  }
  return quarterMap[month] ?? "Q1"
}

export function getWeightageStatus(goals) {
  const total = Math.round(
    (goals ?? []).reduce((sum, goal) => sum + (goal.weightage ?? 0), 0) * 100,
  ) / 100

  return {
    total,
    remaining: Math.round((100 - total) * 100) / 100,
    isValid: total === 100,
    isOver: total > 100,
  }
}
