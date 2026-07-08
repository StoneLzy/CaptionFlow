export async function readApiError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    const detail = payload.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: string; loc?: unknown[] };
      const location = Array.isArray(first.loc)
        ? first.loc.filter((part) => typeof part === "string").join(".")
        : "";
      const message = first.msg ?? fallback;
      return location ? `${location}: ${message}` : message;
    }
  } catch {
    // Ignore JSON parse failures and fall back to the generic message.
  }
  return fallback;
}
