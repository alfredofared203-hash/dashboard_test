export type DurationFormat = "clock" | "compact";

export function formatDuration(seconds: number, format: DurationFormat = "clock"): string {
  const safeSeconds = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const remainingSeconds = safeSeconds % 60;

  if (format === "compact") {
    if (hours > 0) return `${hours}h ${minutes}m ${String(remainingSeconds).padStart(2, "0")}s`;
    return `${minutes}m ${String(remainingSeconds).padStart(2, "0")}s`;
  }

  const clock = [minutes, remainingSeconds]
    .map((part) => String(part).padStart(2, "0"))
    .join(":");
  return hours > 0 ? `${String(hours).padStart(2, "0")}:${clock}` : clock;
}
