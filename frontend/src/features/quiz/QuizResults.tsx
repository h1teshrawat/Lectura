import { motion } from "framer-motion";
import { Check, Clock, PartyPopper, RotateCcw, Sparkles, X } from "lucide-react";

import { TimestampButton } from "@/components/TimestampButton";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";
import { formatTimestamp } from "@/lib/format";
import type { QuizQuestion, QuizResult } from "@/types/api";

function verdict(percent: number): string {
  if (percent >= 90) return "Outstanding!";
  if (percent >= 75) return "Great work!";
  if (percent >= 50) return "Good effort, keep practising.";
  return "Worth another look at the lecture.";
}

/** Circular score indicator: the ring fills up to the percentage. */
function ScoreRing({ percent }: { percent: number }) {
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const color = percent >= 75 ? "var(--success)" : percent >= 50 ? "var(--accent)" : "var(--warning)";
  return (
    <div className="relative size-36">
      <svg viewBox="0 0 120 120" className="size-full -rotate-90">
        <circle cx="60" cy="60" r={radius} fill="none" stroke="var(--subtle)" strokeWidth="10" />
        <motion.circle
          cx="60"
          cy="60"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference * (1 - percent / 100) }}
          transition={{ duration: 1.1, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center">
        <span className="text-3xl font-semibold tabular-nums">{Math.round(percent)}%</span>
      </div>
    </div>
  );
}

export function QuizResults({ result, questions, seconds, onRetryWrong, onNewQuiz, retrying }: {
  result: QuizResult;
  questions: QuizQuestion[];
  seconds: number;
  onRetryWrong: () => void;
  onNewQuiz: () => void;
  retrying: boolean;
}) {
  const byId = new Map(questions.map((q) => [q.id, q]));
  const wrong = result.results.filter((r) => !r.is_correct);
  const skipped = wrong.filter((r) => r.selected_index === null).length;

  return (
    <div className="space-y-6">
      <motion.section
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col items-center rounded-3xl border border-border bg-surface px-6 py-8 text-center sm:flex-row sm:gap-8 sm:text-left"
      >
        <ScoreRing percent={result.percent} />
        <div className="mt-5 sm:mt-0">
          <p className="text-sm font-medium text-accent">Quiz complete</p>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight">{verdict(result.percent)}</h2>
          <p className="mt-1 text-muted">
            You scored {result.score} out of {result.total}.
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-x-4 gap-y-1 text-sm sm:justify-start">
            <span className="flex items-center gap-1 text-success"><Check className="size-4" /> {result.score} correct</span>
            <span className="flex items-center gap-1 text-danger"><X className="size-4" /> {wrong.length - skipped} wrong</span>
            {skipped > 0 && <span className="text-muted">{skipped} timed out</span>}
            <span className="flex items-center gap-1 text-muted"><Clock className="size-4" /> {formatTimestamp(seconds)}</span>
          </div>
          <div className="mt-6 flex flex-wrap justify-center gap-2 sm:justify-start">
            {wrong.length > 0 && (
              <Button onClick={onRetryWrong} loading={retrying} icon={<RotateCcw className="size-4" />}>
                Retry wrong answers ({wrong.length})
              </Button>
            )}
            <Button variant="secondary" onClick={onNewQuiz} icon={<Sparkles className="size-4" />}>
              New quiz
            </Button>
          </div>
        </div>
      </motion.section>

      {wrong.length === 0 ? (
        <div className="flex items-center justify-center gap-2 rounded-2xl bg-success-soft px-4 py-4 text-sm font-medium text-success">
          <PartyPopper className="size-5" /> Perfect score: nothing to review!
        </div>
      ) : (
        <section>
          <h3 className="mb-3 text-sm font-semibold">Review your mistakes</h3>
          <div className="space-y-3">
            {wrong.map((r, i) => {
              const q = byId.get(r.question_id);
              if (!q) return null;
              return (
                <motion.article
                  key={r.question_id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 + i * 0.05 }}
                  className="rounded-2xl border border-border bg-surface p-5"
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="font-medium leading-snug">{q.question}</p>
                    <TimestampButton seconds={q.start_seconds} />
                  </div>
                  <div className="mt-3 space-y-1.5 text-sm">
                    <p className={cn("flex gap-2", "text-danger")}>
                      <X className="mt-0.5 size-4 shrink-0" />
                      <span>
                        <span className="font-medium">Your answer: </span>
                        {r.selected_index === null ? "No answer (time ran out)" : q.options[r.selected_index]}
                      </span>
                    </p>
                    <p className="flex gap-2 text-success">
                      <Check className="mt-0.5 size-4 shrink-0" />
                      <span>
                        <span className="font-medium">Correct: </span>
                        {q.options[r.correct_index]}
                      </span>
                    </p>
                  </div>
                  <p className="mt-3 text-sm leading-relaxed text-muted">{r.explanation}</p>
                </motion.article>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
