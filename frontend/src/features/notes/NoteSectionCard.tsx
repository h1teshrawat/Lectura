import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Quote } from "lucide-react";

import { TimestampButton } from "@/components/TimestampButton";
import { CopyButton } from "@/components/ui/CopyButton";
import { RichText } from "@/features/notes/RichText";
import { cn } from "@/lib/cn";
import { sectionToMarkdown } from "@/lib/notesMarkdown";
import type { NoteSection } from "@/types/api";

export function NoteSectionCard({ section, index, open, onToggle }: {
  section: NoteSection;
  index: number;
  open: boolean;
  onToggle: () => void;
}) {
  const terms = [...section.key_terms, ...section.definitions.map((d) => d.term)];
  const bodyId = `section-body-${index}`;

  return (
    <motion.article
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.03, 0.3) }}
      className={cn(
        "rounded-2xl border bg-surface transition-colors",
        open ? "border-border" : "border-border hover:border-border-strong",
      )}
    >
      <div
        role="button"
        tabIndex={0}
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={onToggle}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onToggle();
          }
        }}
        className="flex cursor-pointer items-center gap-3 rounded-2xl px-4 py-3.5 select-none sm:px-5"
      >
        <TimestampButton seconds={section.start_seconds} />
        <h3 className="min-w-0 flex-1 font-semibold leading-snug">{section.title}</h3>
        <ChevronDown
          className={cn("size-4 shrink-0 text-faint transition-transform duration-200", open && "rotate-180")}
          aria-hidden
        />
      </div>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={bodyId}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="space-y-4 px-4 pb-4 sm:px-5 sm:pb-5">
              <RichText text={section.summary} terms={terms} className="text-[15px] text-fg/90" />

              {section.key_points.length > 0 && (
                <ul className="space-y-2">
                  {section.key_points.map((point) => (
                    <li key={point} className="flex gap-2.5 text-[15px]">
                      <span className="mt-[9px] size-1.5 shrink-0 rounded-full bg-accent" aria-hidden />
                      <RichText text={point} terms={terms} className="min-w-0 flex-1" />
                    </li>
                  ))}
                </ul>
              )}

              {section.definitions.length > 0 && (
                <div className="space-y-2">
                  {section.definitions.map((definition) => (
                    <div key={definition.term} className="flex gap-2.5 rounded-xl bg-accent-soft/60 px-3.5 py-3 text-sm">
                      <Quote className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
                      <p>
                        <span className="font-semibold">{definition.term}</span>
                        <span className="text-muted">: </span>
                        {definition.definition}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                <div className="flex flex-wrap gap-1.5">
                  {section.key_terms.map((term) => (
                    <span key={term} className="rounded-md border border-border px-2 py-0.5 text-xs text-muted">
                      {term}
                    </span>
                  ))}
                </div>
                <CopyButton text={sectionToMarkdown(section)} label="Copy section" successMessage="Section copied" />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  );
}
