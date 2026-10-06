import { Play } from "lucide-react";

import { usePlayer } from "@/features/workspace/PlayerContext";
import { cn } from "@/lib/cn";
import { formatTimestamp } from "@/lib/format";

/** A small time chip. Clicking it jumps the video player to that moment. */
export function TimestampButton({ seconds, className }: { seconds: number; className?: string }) {
  const { canSeek, seekTo } = usePlayer();
  const label = formatTimestamp(seconds);
  const base = cn(
    "inline-flex h-6 shrink-0 items-center gap-1 rounded-md px-1.5 font-mono text-xs font-medium tabular-nums",
    className,
  );

  if (!canSeek) {
    return <span className={cn(base, "bg-subtle text-muted")}>{label}</span>;
  }
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation(); // don't also toggle the section it's in
        seekTo(seconds);
      }}
      title={`Play from ${label}`}
      className={cn(base, "bg-accent-soft text-accent transition-colors hover:bg-accent hover:text-accent-fg")}
    >
      <Play className="size-3 fill-current" aria-hidden />
      {label}
    </button>
  );
}
