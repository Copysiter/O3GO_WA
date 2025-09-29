export function formatDate(d?: Date | string | number) {
  if (!d) return ""
  const dt = typeof d === "string" || typeof d === "number" ? new Date(d) : d
  if (Number.isNaN(dt.getTime())) return ""
  // YYYY-mm-dd
  return dt.toISOString().replace("T", " ").substring(0, 19)
}
