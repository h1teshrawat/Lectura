/** Turn notes into Markdown text for the copy buttons. */

import { formatTimestamp } from "@/lib/format";
import type { LectureNotes, NoteSection } from "@/types/api";

export function sectionToMarkdown(section: NoteSection): string {
  const lines = [`## [${formatTimestamp(section.start_seconds)}] ${section.title}`, "", section.summary, ""];
  lines.push(...section.key_points.map((point) => `- ${point}`));
  if (section.definitions.length) {
    lines.push("", ...section.definitions.map((d) => `> **${d.term}**: ${d.definition}`));
  }
  return lines.join("\n");
}

export function notesToMarkdown(notes: LectureNotes): string {
  const parts = [
    `# ${notes.title}`,
    notes.overview,
    ["## Key takeaways", ...notes.key_takeaways.map((t) => `- ${t}`)].join("\n"),
    ...notes.sections.map(sectionToMarkdown),
  ];
  if (notes.glossary.length) {
    parts.push(["## Glossary", ...notes.glossary.map((d) => `- **${d.term}**: ${d.definition}`)].join("\n"));
  }
  return parts.join("\n\n") + "\n";
}
