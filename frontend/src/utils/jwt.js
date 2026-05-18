/** Decode JWT payload without external dependencies. */
export function decodeJwt(token) {
  try {
    const parts = token.split(".")
    if (parts.length < 2) return null
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/")
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=")
    return JSON.parse(atob(padded))
  } catch {
    return null
  }
}

export function isTokenExpired(token) {
  const decoded = decodeJwt(token)
  if (!decoded?.exp) return true
  return decoded.exp < Date.now() / 1000
}
