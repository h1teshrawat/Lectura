import { ListChecks, Play, Timer } from "lucide-react";
import { useState, type ReactNode } from "react";

import { Button } from "@/components/ui/Button";
import { Segmented } from "@/components/ui/Segmented";
import type { QuizDifficulty } from "@/types/api";

export interface QuizOptions {
  count: number;
  difficulty: QuizDifficulty;
  /** Seconds per question, 0 = no timer */
  secondsPerQuestion: number;
}

const COUNTS = [5, 10, 15, 20];

export function QuizSetup({ bankSize, onStart, loading }: {
  bankSize: number;
  onStart: (options: QuizOptions) => void;
  loading: boolean;
}) {
  const [options, setOptions] = useState<QuizOptions>({
    count: Math.min(10, bankSize),
    difficulty: "mixed",
    secondsPerQuestion: 0,
  });

  return (
    <div className="rounded-3xl border border-border bg-surface p-6 sm:p-8">
      <div className="flex items-start gap-4">
        <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-accent-soft text-accent">
          <ListChecks className="size-6" />
        </span>
        <div>
          <h2 className="text-lg font-semibold">Test your understanding</h2>
          <p className="mt-0.5 text-sm text-muted">
            {bankSize} quality-checked questions from this lecture. Each answer comes with an explanation and a link to
            the exact moment in the video.
          </p>
        </div>
      </div>

      <div className="mt-7 space-y-5">
        <Field label="Number of questions">
          <Segmented
            id="quiz-count"
            className="w-full sm:w-auto"
            value={options.count}
            onChange={(count) => setOptions((o) => ({ ...o, count }))}
            options={COUNTS.map((n) => ({
              value: n,
              label: String(n),
              disabled: n > bankSize && n !== COUNTS.find((c) => c >= bankSize),
            }))}
          />
        </Field>
        <Field label="Difficulty">
          <Segmented
            id="quiz-difficulty"
            className="w-full sm:w-auto"
            value={options.difficulty}
            onChange={(difficulty) => setOptions((o) => ({ ...o, difficulty }))}
            options={[
              { value: "mixed", label: "Mixed" },
              { value: "easy", label: "Easy" },
              { value: "medium", label: "Medium" },
              { value: "hard", label: "Hard" },
            ]}
          />
        </Field>
        <Field label="Timer" icon={<Timer className="size-3.5" />}>
          <Segmented
            id="quiz-timer"
            className="w-full sm:w-auto"
            value={options.secondsPerQuestion}
            onChange={(secondsPerQuestion) => setOptions((o) => ({ ...o, secondsPerQuestion }))}
            options={[
              { value: 0, label: "Off" },
              { value: 30, label: "30 s / question" },
              { value: 60, label: "60 s / question" },
            ]}
          />
        </Field>
      </div>

      <Button
        size="lg"
        className="mt-8 w-full sm:w-auto"
        loading={loading}
        onClick={() => onStart({ ...options, count: Math.min(options.count, bankSize) })}
        icon={<Play className="size-4 fill-current" />}
      >
        Start quiz
      </Button>
    </div>
  );
}

function Field({ label, icon, children }: { label: string; icon?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <span className="flex items-center gap-1.5 text-sm font-medium text-muted">
        {icon}
        {label}
      </span>
      {children}
    </div>
  );
}
