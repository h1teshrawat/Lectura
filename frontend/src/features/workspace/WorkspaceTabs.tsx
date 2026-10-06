import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";

export interface TabItem<T extends string> {
  id: T;
  label: string;
  icon: LucideIcon;
  count?: number;
}

/** Notion/Linear-style tabs with a sliding underline. */
export function WorkspaceTabs<T extends string>({ tabs, active, onChange }: {
  tabs: TabItem<T>[];
  active: T;
  onChange: (id: T) => void;
}) {
  return (
    <div
      role="tablist"
      className="flex gap-1 overflow-x-auto overflow-y-hidden border-b border-border [scrollbar-width:none]"
    >
      {tabs.map(({ id, label, icon: Icon, count }) => {
        const selected = id === active;
        return (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(id)}
            className={cn(
              "relative flex h-11 shrink-0 items-center gap-2 px-3 text-sm font-medium transition-colors",
              selected ? "text-fg" : "text-muted hover:text-fg",
            )}
          >
            <Icon className="size-4" aria-hidden />
            {label}
            {count !== undefined && count > 0 && (
              <span className="rounded-md bg-subtle px-1.5 text-xs text-muted tabular-nums">{count}</span>
            )}
            {selected && (
              <motion.span
                layoutId="workspace-tab-underline"
                className="absolute inset-x-1 bottom-0 h-0.5 rounded-full bg-accent"
                transition={{ type: "spring", stiffness: 500, damping: 35 }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
