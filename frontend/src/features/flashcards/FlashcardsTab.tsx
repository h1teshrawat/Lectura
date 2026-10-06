import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, ArrowRight, Check, Layers, PartyPopper, RotateCcw, Shuffle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Kbd } from "@/components/ui/Kbd";
import { Segmented } from "@/components/ui/Segmented";
import { Skeleton } from "@/components/ui/Skeleton";
import { Flashcard3D } from "@/features/flashcards/Flashcard3D";
import { buildQueue, removeAt, requeue, shuffle, type StudyMode } from "@/features/flashcards/session";
import { queryKeys, useFlashcardProgress } from "@/hooks/queries";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { api } from "@/lib/api";
import type { CardProgress, Flashcard, FlashcardProgress, ReviewResult } from "@/types/api";

/** Replace one card's progress in the cached summary and recount the totals. */
function withUpdatedCard(summary: FlashcardProgress, updated: CardProgress): FlashcardProgress {
  const cards = summary.cards.map((c) => (c.card_id === updated.card_id ? updated : c));
  return {
    ...summary,
    cards,
    new: cards.filter((c) => c.box === 0).length,
    learning: cards.filter((c) => c.box > 0 && !c.is_mastered).length,
    mastered: cards.filter((c) => c.is_mastered).length,
    due_now: cards.filter((c) => c.is_due).length,
  };
}

export function FlashcardsTab({ lectureId, cards }: { lectureId: string; cards: Flashcard[] }) {
  const queryClient = useQueryClient();
  const { data: progress, isLoading } = useFlashcardProgress(lectureId);
  const progressById = useMemo(
    () => new Map((progress?.cards ?? []).map((p) => [p.card_id, p])),
    [progress],
  );
  const cardsById = useMemo(() => new Map(cards.map((c) => [c.id, c])), [cards]);

  const [mode, setMode] = useState<StudyMode>("due");
  const [queue, setQueue] = useState<string[] | null>(null);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [direction, setDirection] = useState(1);
  const [stats, setStats] = useState({ gotIt: 0, again: 0 });

  function startSession(nextMode: StudyMode, shuffled = false) {
    const ids = buildQueue(cards, progressById, nextMode);
    setMode(nextMode);
    setQueue(shuffled ? shuffle(ids) : ids);
    setIndex(0);
    setFlipped(false);
    setStats({ gotIt: 0, again: 0 });
  }

  // Build the first session once the saved progress has loaded.
  useEffect(() => {
    if (progress && queue === null) startSession(progress.due_now > 0 ? "due" : "all");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [progress]);

  const review = useMutation({
    mutationFn: ({ cardId, result }: { cardId: string; result: ReviewResult }) =>
      api.reviewCard(lectureId, cardId, result),
    onSuccess: (updated) =>
      queryClient.setQueryData<FlashcardProgress>(queryKeys.flashcardProgress(lectureId), (old) =>
        old ? withUpdatedCard(old, updated) : old,
      ),
    onError: (error) => toast.error("Couldn't save your answer", { description: error.message }),
  });

  const resetProgress = useMutation({
    mutationFn: () => api.resetFlashcardProgress(lectureId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.flashcardProgress(lectureId) });
      setQueue(null); // rebuilt by the effect above when fresh progress arrives
      toast.success("Flashcard progress reset");
    },
  });

  const currentId = queue?.[index];
  const current = currentId ? cardsById.get(currentId) : undefined;

  function go(step: 1 | -1) {
    if (!queue) return;
    const next = Math.min(Math.max(index + step, 0), queue.length - 1);
    if (next === index) return;
    setDirection(step);
    setIndex(next);
    setFlipped(false);
  }

  function grade(result: ReviewResult) {
    if (!queue || !currentId || !flipped) return;
    review.mutate({ cardId: currentId, result });
    setStats((s) => (result === "got_it" ? { ...s, gotIt: s.gotIt + 1 } : { ...s, again: s.again + 1 }));
    const nextQueue = result === "got_it" ? removeAt(queue, index) : requeue(queue, index);
    setDirection(1);
    setQueue(nextQueue);
    setIndex(Math.min(index, Math.max(nextQueue.length - 1, 0)));
    setFlipped(false);
  }

  useKeyboardShortcuts(
    {
      " ": () => current && setFlipped((f) => !f),
      ArrowRight: () => go(1),
      ArrowLeft: () => go(-1),
      "1": () => grade("again"),
      "2": () => grade("got_it"),
    },
    Boolean(current),
  );

  if (!cards.length) {
    return (
      <EmptyState icon={<Layers className="size-6" />} title="No flashcards" description="This lecture has no flashcards." />
    );
  }
  if (isLoading || !progress || queue === null) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-20 w-full rounded-2xl" />
        <Skeleton className="h-80 w-full rounded-3xl" />
      </div>
    );
  }

  const masteredPercent = Math.round((progress.mastered / Math.max(progress.total, 1)) * 100);
  const sessionDone = stats.gotIt;
  const sessionPercent = Math.round((sessionDone / Math.max(sessionDone + queue.length, 1)) * 100);

  return (
    <div className="space-y-5">
      {/* Overall progress */}
      <section className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold">
              {progress.mastered} of {progress.total} mastered
            </p>
            <p className="mt-0.5 text-xs text-muted">
              {progress.new} new Â· {progress.learning} learning Â· {progress.due_now} due now
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Segmented
              id="flashcard-mode"
              value={mode}
              onChange={(value) => startSession(value)}
              options={[
                { value: "due", label: `Due (${progress.due_now})` },
                { value: "all", label: `All (${progress.total})` },
              ]}
            />
            <Button
              variant="secondary"
              size="sm"
              className="h-10"
              onClick={() => startSession(mode, true)}
              icon={<Shuffle className="size-4" />}
              aria-label="Shuffle cards"
            >
              <span className="hidden sm:inline">Shuffle</span>
            </Button>
          </div>
        </div>
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-subtle">
          <motion.div
            className="h-full rounded-full bg-success"
            initial={false}
            animate={{ width: `${masteredPercent}%` }}
            transition={{ type: "spring", stiffness: 80, damping: 20 }}
          />
        </div>
      </section>

      {current ? (
        <>
          {/* Session progress */}
          <div className="flex items-center gap-3 text-sm text-muted">
            <span className="tabular-nums">
              {queue.length} card{queue.length === 1 ? "" : "s"} left
            </span>
            <div className="h-1 flex-1 overflow-hidden rounded-full bg-subtle">
              <motion.div className="h-full bg-accent" animate={{ width: `${sessionPercent}%` }} />
            </div>
            <span className="tabular-nums">
              <span className="text-success">âœ“ {stats.gotIt}</span> Â· <span className="text-warning">â†» {stats.again}</span>
            </span>
          </div>

          {/* The card */}
          <AnimatePresence mode="wait" custom={direction} initial={false}>
            <motion.div
              key={`${current.id}-${stats.gotIt + stats.again}`}
              custom={direction}
              initial={{ opacity: 0, x: 40 * direction }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -40 * direction }}
              transition={{ duration: 0.2 }}
            >
              <Flashcard3D
                card={current}
                progress={progressById.get(current.id)}
                flipped={flipped}
                onFlip={() => setFlipped((f) => !f)}
              />
            </motion.div>
          </AnimatePresence>

          {/* Controls */}
          <div className="flex items-center justify-between gap-2">
            <Button variant="ghost" onClick={() => go(-1)} disabled={index === 0} aria-label="Previous card" icon={<ArrowLeft className="size-4" />} />
            <AnimatePresence mode="wait" initial={false}>
              {flipped ? (
                <motion.div
                  key="grade"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="flex flex-1 justify-center gap-2"
                >
                  <Button
                    variant="secondary"
                    size="lg"
                    onClick={() => grade("again")}
                    icon={<RotateCcw className="size-4 text-warning" />}
                    className="flex-1 sm:flex-none"
                  >
                    Review again <Kbd className="ml-1 hidden sm:inline-flex">1</Kbd>
                  </Button>
                  <Button
                    size="lg"
                    onClick={() => grade("got_it")}
                    icon={<Check className="size-4" />}
                    className="flex-1 bg-success hover:bg-success hover:brightness-110 sm:flex-none"
                  >
                    Got it <Kbd onColor className="ml-1 hidden sm:inline-flex">2</Kbd>
                  </Button>
                </motion.div>
              ) : (
                <motion.div key="flip" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex flex-1 justify-center">
                  <Button size="lg" onClick={() => setFlipped(true)} className="w-full sm:w-auto">
                    Show answer <Kbd onColor className="ml-1 hidden sm:inline-flex">Space</Kbd>
                  </Button>
                </motion.div>
              )}
            </AnimatePresence>
            <Button variant="ghost" onClick={() => go(1)} disabled={index >= queue.length - 1} aria-label="Next card" icon={<ArrowRight className="size-4" />} />
          </div>

          <p className="hidden items-center justify-center gap-3 text-xs text-faint sm:flex">
            <span className="flex items-center gap-1"><Kbd>Space</Kbd> flip</span>
            <span className="flex items-center gap-1"><Kbd>â†</Kbd><Kbd>â†’</Kbd> navigate</span>
            <span className="flex items-center gap-1"><Kbd>1</Kbd> review again</span>
            <span className="flex items-center gap-1"><Kbd>2</Kbd> got it</span>
          </p>
        </>
      ) : (
        <SessionComplete
          reviewed={stats.gotIt + stats.again}
          gotIt={stats.gotIt}
          again={stats.again}
          dueLeft={progress.due_now}
          onStudyAll={() => startSession("all")}
          onShuffle={() => startSession("all", true)}
          onReset={() => {
            if (window.confirm("Reset spaced-repetition progress for all cards of this lecture?")) resetProgress.mutate();
          }}
        />
      )}
    </div>
  );
}

function SessionComplete({ reviewed, gotIt, again, dueLeft, onStudyAll, onShuffle, onReset }: {
  reviewed: number;
  gotIt: number;
  again: number;
  dueLeft: number;
  onStudyAll: () => void;
  onShuffle: () => void;
  onReset: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex flex-col items-center rounded-3xl border border-border bg-surface px-6 py-12 text-center"
    >
      <span className="mb-4 grid size-14 place-items-center rounded-2xl bg-success-soft text-success">
        <PartyPopper className="size-7" />
      </span>
      <h3 className="text-lg font-semibold">{reviewed ? "Session complete!" : "You're all caught up!"}</h3>
      <p className="mt-1.5 max-w-sm text-sm text-muted">
        {reviewed
          ? `You reviewed ${reviewed} card${reviewed === 1 ? "" : "s"}: ${gotIt} got it, ${again} to review again.`
          : "No cards are due right now. Cards come back for review after 1, 3, 7 and 14 days."}
        {dueLeft > 0 && reviewed > 0 ? ` ${dueLeft} card${dueLeft === 1 ? " is" : "s are"} still due.` : ""}
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <Button onClick={onStudyAll} icon={<Layers className="size-4" />}>Study all cards</Button>
        <Button variant="secondary" onClick={onShuffle} icon={<Shuffle className="size-4" />}>Shuffle all</Button>
        <Button variant="ghost" onClick={onReset} icon={<RotateCcw className="size-4" />}>Reset progress</Button>
      </div>
    </motion.div>
  );
}
