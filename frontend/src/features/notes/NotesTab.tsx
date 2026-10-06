import { BookOpen, ChevronsUpDown, CircleCheck, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { CopyButton } from "@/components/ui/CopyButton";
import { EmptyState } from "@/components/ui/EmptyState";
import { NoteSectionCard } from "@/features/notes/NoteSectionCard";
import { RichText } from "@/features/notes/RichText";
import { notesToMarkdown } from "@/lib/notesMarkdown";
import type { LectureNotes } from "@/types/api";

export function NotesTab({ notes }: { notes: LectureNotes | null }) {
  const [openSections, setOpenSections] = useState<Set<number>>(
    () => new Set(notes?.sections.map((_, i) => i) ?? []),
  );
  const [glossaryFilter, setGlossaryFilter] = useState("");
  const markdown = useMemo(() => (notes ? notesToMarkdown(notes) : ""), [notes]);

  if (!notes) {
    return (
      <EmptyState
        icon={<BookOpen className="size-6" />}
        title="No notes yet"
        description="Notes appear here once processing has finished."
      />
    );
  }

  const allOpen = openSections.size === notes.sections.length;
  const glossary = notes.glossary.filter((d) =>
    `${d.term} ${d.definition}`.toLowerCase().includes(glossaryFilter.trim().toLowerCase()),
  );

  function toggle(index: number) {
    setOpenSections((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  return (
    <div className="space-y-6">
      {/* Overview */}
      <section className="rounded-2xl border border-border bg-surface p-5 sm:p-6">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-xl font-semibold tracking-tight text-balance">{notes.title}</h2>
          <CopyButton text={markdown} label="Copy all" successMessage="All notes copied as Markdown" />
        </div>
        <RichText text={notes.overview} className="mt-3 text-[15px] text-muted" />

        <h3 className="mt-6 mb-3 text-xs font-semibold tracking-wider text-faint uppercase">Key takeaways</h3>
        <ul className="space-y-2.5">
          {notes.key_takeaways.map((takeaway) => (
            <li key={takeaway} className="flex gap-2.5 text-[15px]">
              <CircleCheck className="mt-0.5 size-[18px] shrink-0 text-accent" aria-hidden />
              <span className="leading-relaxed">{takeaway}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* Sections */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">
            Sections <span className="font-normal text-faint">({notes.sections.length})</span>
          </h3>
          <Button
            variant="ghost"
            size="sm"
            icon={<ChevronsUpDown className="size-4" />}
            onClick={() => setOpenSections(allOpen ? new Set() : new Set(notes.sections.map((_, i) => i)))}
          >
            {allOpen ? "Collapse all" : "Expand all"}
          </Button>
        </div>
        <div className="space-y-3">
          {notes.sections.map((section, index) => (
            <NoteSectionCard
              key={`${section.start_seconds}-${section.title}`}
              section={section}
              index={index}
              open={openSections.has(index)}
              onToggle={() => toggle(index)}
            />
          ))}
        </div>
      </section>

      {/* Glossary */}
      {notes.glossary.length > 0 && (
        <section className="rounded-2xl border border-border bg-surface p-5 sm:p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-semibold">
              Glossary <span className="font-normal text-faint">({notes.glossary.length})</span>
            </h3>
            {notes.glossary.length > 6 && (
              <label className="flex h-8 items-center gap-2 rounded-lg border border-border px-2.5 text-sm">
                <Search className="size-3.5 text-faint" aria-hidden />
                <input
                  value={glossaryFilter}
                  onChange={(e) => setGlossaryFilter(e.target.value)}
                  placeholder="Filter terms"
                  aria-label="Filter glossary"
                  className="w-32 bg-transparent outline-none placeholder:text-faint"
                />
              </label>
            )}
          </div>
          <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
            {glossary.map((definition) => (
              <div key={definition.term} className="text-sm">
                <dt className="font-semibold">{definition.term}</dt>
                <dd className="mt-0.5 leading-relaxed text-muted">{definition.definition}</dd>
              </div>
            ))}
          </dl>
          {glossary.length === 0 && <p className="text-sm text-muted">No terms match "{glossaryFilter}".</p>}
        </section>
      )}
    </div>
  );
}
