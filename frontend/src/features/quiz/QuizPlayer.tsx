import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Check, CircleCheck, CircleX, Timer, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { TimestampButton } from "@/components/TimestampButton";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Kbd } from "@/components/ui/Kbd";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { cn } from "@/lib/cn";
import type { QuizQuestion } from "@/types/api";

const LETTERS = ["A", "B", "C", "D"];
const DIFFICULTY_TONE = { easy: "success", medium: "accent", hard: "warning" } as const;

/** Plays one quiz: one question at a time with instant feedback. */
export function QuizPlayer({ questions, secondsPerQuestion, onFinish, submitting }: {
  questions: QuizQuestion[];
  secondsPerQuestion: number;
  onFinish: (answers: (number | null)[], seconds: number) => void;
  submitting: boolean;
}) {
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<(number | null | undefined)[]>(() => questions.map(() => undefined));
  const [timeLeft, setTimeLeft] = useState(secondsPerQuestion);
  const startedAt = useRef(Date.now());

  const question = questions[index];
  const answer = answers[index];
  const revealed = answer !== undefined; // null = time ran out
  const isLast = index === questions.length - 1;
  const score = answers.filter((a, i) => a !== undefined && a === questions[i].correct_index).length;

  function choose(option: number | null) {
    if (revealed) return;
    setAnswers((current) => current.map((a, i) => (i === index ? option : a)));
  }

  function next() {
    if (!revealed || submitting) return;
    if (isLast) {
      onFinish(answers.map((a) => a ?? null), Math.round((Date.now() - startedAt.current) / 1000));
    } else {
      setIndex((i) => i + 1);
      setTimeLeft(secondsPerQuestion);
    }
  }

  // Per-question countdown: when it reaches 0 the question counts as skipped.
  useEffect(() => {
    if (!secondsPerQuestion || revealed) return;
    if (timeLeft <= 0) {
      choose(null);
      return;
    }
    const timer = setTimeout(() => setTimeLeft((t) => t - 1), 1000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeLeft, revealed, secondsPerQuestion]);

  useKeyboardShortcuts({
    "1": () => choose(0), "2": () => choose(1), "3": () => choose(2), "4": () => choose(3),
    a: () => choose(0), b: () => choose(1), c: () => choose(2), d: () => choose(3),
    Enter: next,
    ArrowRight: next,
  });

  const correct = revealed && answer === question.correct_index;

  return (
    <div className="space-y-5">
      {/* Progress: one segment per question, coloured by result */}
      <div className="flex items-center gap-3">
        <div className="flex flex-1 gap-1">
          {questions.map((q, i) => {
            const a = answers[i];
            return (
              <span
                key={q.id}
                className={cn(
                  "h-1.5 flex-1 rounded-full transition-colors duration-300",
                  a === undefined ? (i === index ? "bg-accent/40" : "bg-subtle") : a === q.correct_index ? "bg-success" : "bg-danger",
                )}
              />
            );
          })}
        </div>
        <span className="text-sm text-muted tabular-nums">
          {index + 1}/{questions.length}
        </span>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={question.id}
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -24 }}
          transition={{ duration: 0.2 }}
          className="rounded-3xl border border-border bg-surface p-5 sm:p-7"
        >
          <div className="flex items-center justify-between gap-2">
            <Badge tone={DIFFICULTY_TONE[question.difficulty]}>{question.difficulty}</Badge>
            <div className="flex items-center gap-3 text-sm">
              <span className="text-muted tabular-nums">Score {score}</span>
              {secondsPerQuestion > 0 && (
                <span
                  className={cn(
                    "flex items-center gap-1 rounded-lg px-2 py-0.5 font-mono font-medium tabular-nums",
                    revealed ? "bg-subtle text-faint" : timeLeft <= 5 ? "bg-danger-soft text-danger" : "bg-subtle text-muted",
                  )}
                >
                  <Timer className="size-3.5" /> {revealed ? "--" : `${timeLeft}s`}
                </span>
              )}
            </div>
          </div>

          <h2 className="mt-4 text-lg leading-snug font-semibold text-balance sm:text-xl">{question.question}</h2>

          <div className="mt-6 space-y-2.5">
            {question.options.map((option, i) => {
              const isCorrect = i === question.correct_index;
              const isChosen = i === answer;
              const state = !revealed ? "idle" : isCorrect ? "correct" : isChosen ? "wrong" : "dimmed";
              return (
                <motion.button
                  key={option}
                  type="button"
                  onClick={() => choose(i)}
                  disabled={revealed}
                  animate={
                    state === "wrong"
                      ? { x: [0, -7, 7, -5, 5, 0] }
                      : state === "correct" && isChosen
                        ? { scale: [1, 1.025, 1] }
                        : {}
                  }
                  transition={{ duration: 0.4 }}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-2xl border px-4 py-3.5 text-left text-[15px] transition-colors duration-200",
                    state === "idle" && "border-border hover:border-accent/60 hover:bg-accent-soft/40",
                    state === "correct" && "border-success bg-success-soft text-fg",
                    state === "wrong" && "border-danger bg-danger-soft text-fg",
                    state === "dimmed" && "border-border opacity-50",
                  )}
                >
                  <span
                    className={cn(
                      "grid size-7 shrink-0 place-items-center rounded-lg border font-mono text-xs font-semibold",
                      state === "correct" ? "border-success bg-success text-white"
                        : state === "wrong" ? "border-danger bg-danger text-white"
                          : "border-border text-muted",
                    )}
                  >
                    {state === "correct" ? <Check className="size-4" /> : state === "wrong" ? <X className="size-4" /> : LETTERS[i]}
                  </span>
                  <span className="min-w-0 flex-1">{option}</span>
                </motion.button>
              );
            })}
          </div>

          {/* Feedback */}
          <AnimatePresence>
            {revealed && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                className="overflow-hidden"
              >
                <div className={cn("mt-5 rounded-2xl p-4", correct ? "bg-success-soft" : "bg-danger-soft")}>
                  <p className={cn("flex items-center gap-2 font-semibold", correct ? "text-success" : "text-danger")}>
                    {correct ? <CircleCheck className="size-5" /> : <CircleX className="size-5" />}
                    {correct ? "Correct!" : answer === null ? "Time's up!" : "Not quite."}
                  </p>
                  <p className="mt-1.5 text-sm leading-relaxed">{question.explanation}</p>
                  <div className="mt-3 flex items-center gap-2 text-xs text-muted">
                    Explained at <TimestampButton seconds={question.start_seconds} />
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </AnimatePresence>

      <div className="flex items-center justify-between gap-3">
        <p className="hidden items-center gap-1.5 text-xs text-faint sm:flex">
          Answer with <Kbd>1</Kbd>–<Kbd>4</Kbd>, continue with <Kbd>Enter</Kbd>
        </p>
        <Button
          size="lg"
          onClick={next}
          disabled={!revealed}
          loading={submitting}
          className="ml-auto w-full sm:w-auto"
        >
          {isLast ? "See results" : "Next question"}
          {!submitting && <ArrowRight className="size-4" />}
        </Button>
      </div>
    </div>
  );
}
