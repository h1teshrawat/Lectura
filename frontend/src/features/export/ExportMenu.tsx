import { ChevronDown, Download, FileDown, FileText, Layers } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Menu, type MenuItem } from "@/components/ui/Menu";
import { api } from "@/lib/api";

export function exportItems(lectureId: string): MenuItem[] {
  return [
    {
      label: "Notes as PDF",
      description: "Printable, with clickable timestamps",
      icon: <FileDown className="size-4" />,
      href: api.exportUrl(lectureId, "pdf"),
    },
    {
      label: "Notes as Markdown",
      description: "For Notion, Obsidian or GitHub",
      icon: <FileText className="size-4" />,
      href: api.exportUrl(lectureId, "md"),
    },
    {
      label: "Flashcards for Anki",
      description: "CSV: File → Import in Anki",
      icon: <Layers className="size-4" />,
      href: api.exportUrl(lectureId, "csv"),
    },
  ];
}

/** "Export" button with a dropdown of download formats. */
export function ExportMenu({ lectureId }: { lectureId: string }) {
  return (
    <Menu
      label="Export"
      align="left"
      items={exportItems(lectureId)}
      trigger={({ open, toggle }) => (
        <Button variant="secondary" size="sm" onClick={toggle} aria-expanded={open} icon={<Download className="size-4" />}>
          Export
          <ChevronDown className="size-3.5 text-faint" />
        </Button>
      )}
    />
  );
}
