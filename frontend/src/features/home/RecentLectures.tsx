import { ArrowRight, AudioLines } from "lucide-react";
import { Link } from "react-router";

import { Badge } from "@/components/ui/Badge";
import { useLectures } from "@/hooks/queries";
import { formatDuration, formatRelativeDate } from "@/lib/format";
import type { LectureSummary } from "@/types/api";

const STATUS_BADGE: Record<LectureSummary["status"], { tone: "success" | "accent" | "danger"; label: string }> = {
  done: { tone: "success", label: "Ready" },
  processing: { tone: "accent", label: "Processing" },
  queued: { tone: "accent", label: "Queued" },
  failed: { tone: "danger", label: "Failed" },
};

export function lecturePath(lecture: Pick<LectureSummary, "id" | "status">): string {
  return lecture.status === "done" ? `/lectures/${lecture.id}` : `/lectures/${lecture.id}/processing`;
}

/** The three most recent lectures, so you can jump back in quickly. */
export function RecentLectures() {
  const { data } = useLectures();
  const recent = (data ?? []).slice(0, 3);
  if (!recent.length) return null;

  return (
    <section className="mx-auto max-w-6xl px-4 pt-12 sm:px-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold tracking-tight">Continue learning</h2>
        <Link to="/library" className="flex items-center gap-1 text-sm font-medium text-muted hover:text-fg">
          View library <ArrowRight className="size-4" />
        </Link>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {recent.map((lecture) => {
          const badge = STATUS_BADGE[lecture.status];
          return (
            <Link
              key={lecture.id}
              to={lecturePath(lecture)}
              className="flex items-center gap-3 rounded-xl border border-border bg-surface p-2.5 transition-colors hover:border-border-strong hover:bg-subtle/50"
            >
              <div className="grid aspect-video w-24 shrink-0 place-items-center overflow-hidden rounded-lg bg-subtle">
                {lecture.thumbnail_url ? (
                  <img src={lecture.thumbnail_url} alt="" loading="lazy" className="size-full object-cover" />
                ) : (
                  <AudioLines className="size-5 text-faint" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{lecture.title}</p>
                <div className="mt-1 flex items-center gap-2 text-xs text-muted">
                  <Badge tone={badge.tone}>{badge.label}</Badge>
                  <span className="truncate">
                    {[formatDuration(lecture.duration_seconds), formatRelativeDate(lecture.created_at)]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
