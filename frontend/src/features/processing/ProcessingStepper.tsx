import { AnimatePresence, motion } from "framer-motion";
import { AudioLines, Check, Database, Download, FileText, Layers, ListChecks, LoaderCircle, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";
import type { Stage } from "@/types/api";

interface StepInfo {
  stage: Stage;
  label: string;
  description: string;
  icon: LucideIcon;
}

export const STEPS: StepInfo[] = [
  { stage: "fetching", label: "Fetching", description: "Reading the video and looking for captions", icon: Download },
  { stage: "transcribing", label: "Transcribing", description: "Turning speech into timestamped text", icon: AudioLines },
  { stage: "notes", label: "Generating notes", description: "Summarising each part, then the whole lecture", icon: FileText },
  { stage: "flashcards", label: "Creating flashcards", description: "Question-and-answer cards for revision", icon: Layers },
  { stage: "quiz", label: "Building the quiz", description: "Multiple-choice questions with quality checks", icon: ListChecks },
  { stage: "indexing", label: "Indexing for chat", description: "Preparing the lecture for your questions", icon: Database },
];

type StepState = "done" | "active" | "pending" | "failed";

function stepState(index: number, currentIndex: number, status: string): StepState {
  if (status === "done") return "done";
  if (index < currentIndex) return "done";
  if (index === currentIndex) return status === "failed" ? "failed" : "active";
  return "pending";
}

/** The vertical list of processing stages with live status. */
export function ProcessingStepper({ stage, status, message }: { stage: Stage; status: string; message: string }) {
  const currentIndex = STEPS.findIndex((s) => s.stage === stage);

  return (
    <ol className="relative">
      {STEPS.map((step, index) => {
        const state = stepState(index, currentIndex, status);
        const Icon = step.icon;
        const isLast = index === STEPS.length - 1;
        return (
          <li key={step.stage} className="relative flex gap-4 pb-6 last:pb-0">
            {/* Connector line */}
            {!isLast && (
              <span className="absolute top-10 bottom-1 left-[19px] w-px bg-border" aria-hidden>
                <motion.span
                  className="block w-px origin-top bg-accent"
                  initial={false}
                  animate={{ height: state === "done" ? "100%" : "0%" }}
                  transition={{ duration: 0.4 }}
                />
              </span>
            )}

            <motion.span
              layout
              className={cn(
                "relative z-10 grid size-10 shrink-0 place-items-center rounded-xl border transition-colors duration-300",
                state === "done" && "border-accent bg-accent text-accent-fg",
                state === "active" && "border-accent bg-accent-soft text-accent",
                state === "pending" && "border-border bg-surface text-faint",
                state === "failed" && "border-danger bg-danger-soft text-danger",
              )}
            >
              <AnimatePresence mode="wait" initial={false}>
                {state === "done" ? (
                  <motion.span key="done" initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 500, damping: 25 }}>
                    <Check className="size-5" strokeWidth={2.5} />
                  </motion.span>
                ) : (
                  <motion.span key="icon" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                    <Icon className="size-[18px]" />
                  </motion.span>
                )}
              </AnimatePresence>
              {state === "active" && (
                <span className="absolute inset-0 animate-ping rounded-xl border border-accent/40" aria-hidden />
              )}
            </motion.span>

            <div className="min-w-0 flex-1 pt-1.5">
              <p className={cn("font-medium", state === "pending" ? "text-faint" : "text-fg")}>{step.label}</p>
              <AnimatePresence mode="wait" initial={false}>
                {state === "active" ? (
                  <motion.p
                    key={message}
                    initial={{ opacity: 0, y: 3 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="mt-0.5 flex items-center gap-1.5 text-sm text-accent"
                  >
                    <LoaderCircle className="size-3.5 shrink-0 animate-spin" />
                    <span className="truncate">{message}</span>
                  </motion.p>
                ) : (
                  <motion.p key="description" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-0.5 text-sm text-muted">
                    {step.description}
                  </motion.p>
                )}
              </AnimatePresence>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
