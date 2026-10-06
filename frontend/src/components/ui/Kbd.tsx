import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/** A keyboard key hint, e.g. <Kbd>Space</Kbd>. Use `onColor` inside coloured (primary/success) buttons. */
export function Kbd({ children, onColor = false, className }: {
  children: ReactNode;
  onColor?: boolean;
  className?: string;
}) {
  return (
    <kbd
      className={cn(
        "inline-flex h-5 min-w-5 items-center justify-center rounded border px-1 font-mono text-[11px] font-medium",
        onColor
          ? "border-white/35 bg-white/15 text-current"
          : "border-border bg-surface text-muted shadow-[0_1px_0_var(--border)]",
        className,
      )}
    >
      {children}
    </kbd>
  );
}
