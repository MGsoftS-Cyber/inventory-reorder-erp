/** HTTP adapter. Authentication cookies stay HttpOnly; only the CSRF token is held in memory. */
let csrfToken = "";
export function setCsrfToken(value) {
  csrfToken = value;
}

export async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    ...options,
    credentials: "same-origin",
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
      ...options.headers,
    },
  });
  if (response.status === 204) return null;
  const payload = await response.json();
  if (!response.ok) {
    const details = payload.error?.fields
      ?.map((field) => `${field.path}: ${field.message}`)
      .join(" ");
    const error = new Error(
      details ||
        payload.error?.message ||
        "The request could not be completed.",
    );
    error.status = response.status;
    throw error;
  }
  return payload;
}
