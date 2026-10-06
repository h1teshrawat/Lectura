import { AnimatePresence, motion } from "framer-motion";
import {
  AudioLines,
  Clock,
  EllipsisVertical,
  ExternalLink,
  Layers,
  Library,
  ListChecks,
  Plus,
  Search,
  Trash,
  X,
} from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router";
import { toast } from "sonner";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { Menu } from "@/components/ui/Menu";
import { SelectField } from "@/components/ui/SelectField";
import { Skeleton } from "@/components/ui/Skeleton";
import { exportItems } from "@/features/export/ExportMenu";
import { lecturePath } from "@/features/home/RecentLectures";
import { useDeleteLecture, useLectures } from "@/hooks/queries";
import { formatDuration, formatRelativeDate } from "@/lib/format";
import type { LectureSummary } from "@/types/api";

type SortOrder = "newest" | "oldest" | "title";

const STATUS: Record<LectureSummary["status"], { tone: "accent" | "danger"; label: string } | null> = {
  done: null,
  processing: { tone: "accent", label: "Processing" },
  queued: { tone: "accent", label: "Queued" },
  failed: { tone: "danger", label: "Failed" },
};

export function LibraryPage() {
  const [search, setSearch] = useState("");
  // useDeferredValue keeps typing smooth: the search request follows a moment later.
  const deferredSearch = useDeferredValue(search.trim());
  const { data, isLoading, isFetching } = useLectures(deferredSearch || undefined);
  const [sort, setSort] = useState<SortOrder>("newest");
  const [toDelete, setToDelete] = useState<LectureSummary | null>(null);
  const deleteLecture = useDeleteLecture();

  const lectures = useMemo(() => {
    const list = [...(data ?? [])];
    if (sort === "oldest") list.reverse();
    if (sort === "title") list.sort((a, b) => a.title.localeCompare(b.title));
    return list;
  }, [data, sort]);

  function confirmDelete() {
    if (!toDelete) return;
    deleteLecture.mutate(toDelete.id, {
      onSuccess: () => {
        toast.success("Lecture deleted", { description: toDelete.title });
        setToDelete(null);
      },
      onError: (error) => toast.error("Couldn't delete the lecture", { description: error.message }),
    });
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Library</h1>
          <p className="mt-1 text-sm text-muted">
            {data ? `${data.length} lecture${data.length === 1 ? "" : "s"}` : "Your processed lectures"}
            {deferredSearch && ` matching "${deferredSearch}"`}
          </p>
        </div>
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <label className="flex h-9 min-w-0 flex-1 items-center gap-2 rounded-lg border border-border bg-surface px-3 text-sm transition-colors focus-within:border-accent/60 sm:w-64 sm:flex-none">
            <Search className="size-4 shrink-0 text-faint" aria-hidden />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search lectures"
              aria-label="Search lectures"
              className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-faint"
            />
            {search && (
              <button type="button" onClick={() => setSearch("")} aria-label="Clear search" className="text-faint hover:text-fg">
                <X className="size-4" />
              </button>
            )}
          </label>
          <SelectField<SortOrder>
            label="Sort"
            value={sort}
            onChange={setSort}
            options={[
              { value: "newest", label: "Newest" },
              { value: "oldest", label: "Oldest" },
              { value: "title", label: "Title A–Z" },
            ]}
          />
          <Link to="/">
            <Button size="sm" className="h-9" icon={<Plus className="size-4" />}>
              New
            </Button>
          </Link>
        </div>
      </div>

      <div className="mt-8">
        {isLoading ? (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }, (_, i) => (
              <div key={i} className="space-y-3">
                <Skeleton className="aspect-video w-full rounded-2xl" />
                <Skeleton className="h-4 w-4/5" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            ))}
          </div>
        ) : lectures.length === 0 ? (
          deferredSearch ? (
            <EmptyState
              icon={<Search className="size-6" />}
              title="No matching lectures"
              description={`Nothing in your library matches "${deferredSearch}".`}
              action={<Button variant="secondary" onClick={() => setSearch("")}>Clear search</Button>}
            />
          ) : (
            <EmptyState
              icon={<Library className="size-6" />}
              title="Your library is empty"
              description="Process your first lecture and it will appear here, ready to revise."
              action={<Link to="/"><Button icon={<Plus className="size-4" />}>Add a lecture</Button></Link>}
            />
          )
        ) : (
          <motion.div
            layout
            className={`grid gap-5 transition-opacity sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 ${isFetching ? "opacity-70" : ""}`}
          >
            <AnimatePresence initial={false}>
              {lectures.map((lecture, i) => (
                <LectureCard key={lecture.id} lecture={lecture} index={i} onDelete={() => setToDelete(lecture)} />
              ))}
            </AnimatePresence>
          </motion.div>
        )}
      </div>

      <ConfirmDialog
        open={toDelete !== null}
        title="Delete this lecture?"
        description={
          <>
            <span className="font-medium text-fg">{toDelete?.title}</span> will be removed with its notes,
            flashcards, quiz history and chat. This can't be undone.
          </>
        }
        confirmLabel="Delete"
        loading={deleteLecture.isPending}
        onConfirm={confirmDelete}
        onCancel={() => setToDelete(null)}
      />
    </div>
  );
}

function LectureCard({ lecture, index, onDelete }: { lecture: LectureSummary; index: number; onDelete: () => void }) {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const status = STATUS[lecture.status];
  const busy = lecture.status === "queued" || lecture.status === "processing";
  const meta = [lecture.channel, formatRelativeDate(lecture.created_at)].filter(Boolean).join(" · ");

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0, transition: { delay: Math.min(index * 0.03, 0.3) } }}
      exit={{ opacity: 0, scale: 0.95 }}
      className={`group relative flex flex-col rounded-2xl border border-border bg-surface transition-[border-color,box-shadow,translate] hover:-translate-y-0.5 hover:border-border-strong hover:shadow-lg hover:shadow-black/5 ${menuOpen ? "z-30" : ""}`}
    >
      <Link to={lecturePath(lecture)} className="absolute inset-0 z-0 rounded-2xl" aria-label={`Open ${lecture.title}`} />

      {/* Only the image is clipped to the rounded corners, so the actions menu can overflow the card. */}
      <div className="pointer-events-none relative grid aspect-video place-items-center overflow-hidden rounded-t-2xl bg-subtle">
        {lecture.thumbnail_url ? (
          <img
            src={lecture.thumbnail_url}
            alt=""
            loading="lazy"
            className="size-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
          />
        ) : (
          <AudioLines className="size-8 text-faint" />
        )}
        {lecture.duration_seconds ? (
          <span className="absolute right-2 bottom-2 flex items-center gap-1 rounded-md bg-black/75 px-1.5 py-0.5 text-xs font-medium text-white">
            <Clock className="size-3" /> {formatDuration(lecture.duration_seconds)}
          </span>
        ) : null}
        {status && (
          <Badge tone={status.tone} className="absolute top-2 left-2 shadow-sm">
            {status.label}
          </Badge>
        )}
      </div>

      {/* Clicks pass through to the card link, except on the actions menu. */}
      <div className="pointer-events-none flex flex-1 flex-col p-4">
        <div className="flex items-start gap-2">
          <h2 className="line-clamp-2 min-w-0 flex-1 leading-snug font-medium">{lecture.title}</h2>
          <div className="pointer-events-auto relative z-10 -mt-1 -mr-2">
            <Menu
              label="Lecture actions"
              // While open, the card is raised above its neighbours so the menu isn't covered.
              onOpenChange={setMenuOpen}
              items={[
                { label: "Open", icon: <ExternalLink className="size-4" />, onSelect: () => navigate(lecturePath(lecture)) },
                ...(lecture.status === "done" ? ["divider" as const, ...exportItems(lecture.id)] : []),
                "divider",
                {
                  label: busy ? "Delete (wait until processed)" : "Delete",
                  icon: <Trash className="size-4" />,
                  danger: true,
                  onSelect: busy ? undefined : onDelete,
                },
              ]}
              trigger={({ open, toggle }) => (
                <button
                  type="button"
                  onClick={toggle}
                  aria-label="Lecture actions"
                  aria-expanded={open}
                  className="grid size-8 place-items-center rounded-lg text-faint transition-colors hover:bg-subtle hover:text-fg"
                >
                  <EllipsisVertical className="size-4" />
                </button>
              )}
            />
          </div>
        </div>
        {meta && <p className="mt-1 truncate text-sm text-muted">{meta}</p>}
        {lecture.status === "done" && (
          <div className="mt-auto flex gap-3 pt-3 text-xs text-muted">
            <span className="flex items-center gap-1"><Layers className="size-3.5" /> {lecture.flashcard_count} cards</span>
            <span className="flex items-center gap-1"><ListChecks className="size-3.5" /> {lecture.quiz_count} questions</span>
          </div>
        )}
      </div>
    </motion.article>
  );
}
