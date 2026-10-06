import { motion } from "framer-motion";

import { cn } from "@/lib/cn";

interface SegmentOption<T extends string | number> {
  value: T;
  label: string;
  disabled?: boolean;
}

/** A row of mutually exclusive choices with a sliding highlight (like iOS segmented controls). */
export function Segmented<T extends string | number>({ id, value, options, onChange, className }: {
  /** Unique per instance, so the sliding highlight animates within this control only. */
  id: string;
  value: T;
  options: SegmentOption<T>[];
  onChange: (value: T) => void;
  className?: string;
}) {
  return (
    <div role="radiogroup" className={cn("inline-flex rounded-xl border border-border bg-subtle p-1", className)}>
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={option.disabled}
            onClick={() => onChange(option.value)}
            className={cn(
              "relative h-8 flex-1 rounded-lg px-3 text-sm font-medium whitespace-nowrap transition-colors disabled:opacity-40",
              selected ? "text-fg" : "text-muted hover:text-fg",
            )}
          >
            {selected && (
              <motion.span
                layoutId={`segmented-${id}`}
                className="absolute inset-0 rounded-lg bg-surface shadow-sm ring-1 ring-border"
                transition={{ type: "spring", stiffness: 500, damping: 38 }}
              />
            )}
            <span className="relative">{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}
