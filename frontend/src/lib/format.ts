/** Formatting helpers for times, durations, sizes and dates. */

/** 75 -> "1:15", 3725 -> "1:02:05" (like YouTube). */
export function formatTimestamp(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const ss = String(s).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

/** 1120 -> "18 min", 3900 -> "1 h 5 min". */
export function formatDuration(seconds: number | null | undefined): string {
  if (!seconds) return "";
  const minutes = Math.round(seconds / 60);
  if (minutes < 1) return `${Math.round(seconds)} sec`;
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h} h ${m} min` : `${h} h`;
}

/** Remaining-time label for the processing screen. */
export function formatEta(seconds: number): string {
  if (seconds < 45) return "Less than a minute left";
  const minutes = Math.round(seconds / 60);
  return minutes === 1 ? "About 1 minute left" : `About ${minutes} minutes left`;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

/** "just now", "5 min ago", "yesterday", "12 Mar". */
export function formatRelativeDate(iso: string): string {
  // The API sends UTC times; add "Z" if the timezone is missing.
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
  const diff = (Date.now() - date.getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  if (diff < 172800) return "yesterday";
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}
