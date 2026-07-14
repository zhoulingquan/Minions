export function parseErrorDetail(
  error: unknown,
): Record<string, unknown> | null {
  if (!(error instanceof Error)) return null;
  const msg = error.message;
  // Try " - " separator first (from request.ts formatted errors)
  const idx = msg.indexOf(" - ");
  if (idx !== -1) {
    try {
      const parsed: unknown = JSON.parse(msg.slice(idx + 3));
      if (typeof parsed === "object" && parsed !== null) {
        const record = parsed as Record<string, unknown>;
        const detail = record.detail;
        return typeof detail === "object" && detail !== null
          ? (detail as Record<string, unknown>)
          : record;
      }
    } catch {
      // fall through to raw JSON attempt
    }
  }
  // Fallback: try parsing the entire message as JSON
  try {
    const parsed: unknown = JSON.parse(msg);
    if (typeof parsed === "object" && parsed !== null) {
      const record = parsed as Record<string, unknown>;
      const detail = record.detail;
      return typeof detail === "object" && detail !== null
        ? (detail as Record<string, unknown>)
        : record;
    }
  } catch {
    // not JSON
  }
  return null;
}
