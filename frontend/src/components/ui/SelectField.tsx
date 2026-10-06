import { ChevronsUpDown } from "lucide-react";
import type { ReactNode } from "react";

interface Option<T extends string> {
  value: T;
  label: string;
}

/** A compact labelled dropdown (native <select>, so it works well on phones). */
export function SelectField<T extends string>({
  label,
  icon,
  value,
  options,
  onChange,
}: {
  label: string;
  icon?: ReactNode;
  value: T;
  options: Option<T>[];
  onChange: (value: T) => void;
}) {
  return (
    <label className="relative inline-flex h-9 items-center gap-2 rounded-lg border border-border bg-surface pr-8 pl-3 text-sm transition-colors hover:border-border-strong">
      <span className="flex items-center gap-1.5 text-muted">
        {icon}
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        className="absolute inset-0 cursor-pointer bg-surface text-fg opacity-0"
        aria-label={label}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <span className="font-medium">{options.find((o) => o.value === value)?.label}</span>
      <ChevronsUpDown className="pointer-events-none absolute right-2.5 size-3.5 text-faint" aria-hidden />
    </label>
  );
}
