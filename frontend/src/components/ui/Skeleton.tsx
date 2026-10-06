import { cn } from "@/lib/cn";

/** A grey shimmering placeholder shown while content loads. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-pulse rounded-lg bg-subtle", className)} />;
}
