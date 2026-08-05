/** Minimal JWT payload decoder (same idea as jwt-decode, no dependency). */

/**
 * @param {string} token Raw JWT access token (no "Bearer " prefix).
 * @returns {Record<string, unknown>}
 */
export function jwtDecode(token) {
  const parts = token.split(".");
  if (parts.length < 2) {
    throw new Error("Invalid token");
  }
  const base64Url = parts[1];
  const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
  const json = atob(padded);
  return JSON.parse(json);
}

/**
 * @param {string} passwordField Value from the Password input (Bearer or raw JWT).
 * @returns {string|null} JWT ``sub`` claim.
 */
export function extractSubFromPasswordField(passwordField) {
  let token = (passwordField || "").trim();
  if (!token) return null;
  if (token.toLowerCase().startsWith("bearer ")) {
    token = token.slice(7).trim();
  }
  if (!token.includes(".")) return null;
  try {
    const decoded = jwtDecode(token);
    const sub = decoded.sub;
    return typeof sub === "string" && sub.trim() ? sub.trim() : null;
  } catch {
    return null;
  }
}
