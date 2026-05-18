/**
 * Normalize API errors into user-facing toasts.
 * 401 redirects are handled by the axios interceptor.
 */
export function handleApiError(err, toast) {
  const status = err.response?.status
  const detail = err.response?.data?.detail

  if (status === 401) {
    return
  }
  if (status === 403) {
    toast.error("You don't have permission to do this")
    return
  }
  if (status === 400) {
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg ?? JSON.stringify(d)).join(", ")
          : "Invalid request"
    toast.error(message)
    return
  }
  if (status >= 500) {
    toast.error("Server error. Please try again.")
    return
  }
  toast.error(typeof detail === "string" ? detail : "Something went wrong")
}
