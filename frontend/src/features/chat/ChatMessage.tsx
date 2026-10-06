import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, CircleAlert, FileSearch, LoaderCircle, RotateCcw } from "lucide-react";
import { useState } from "react";

import { LogoMark } from "@/components/layout/Logo";
import { TimestampButton } from "@/components/TimestampButton";
import { Button } from "@/components/ui/Button";
import { AnswerMarkdown } from "@/features/chat/AnswerMarkdown";
import { cn } from "@/lib/cn";
import type { ChatSource } from "@/types/api";

export interface UiMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: ChatSource[];
  /** e.g. "Searching the lecture..." before the first words arrive */
  status?: string;
  streaming?: boolean;
  stopped?: boolean;
  error?: { message: string; hint?: string | null };
}

export function ChatMessage({ message, onRetry }: { message: UiMessage; onRetry?: () => void }) {
  if (message.role === "user") {
    return (
      <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-md bg-accent px-4 py-2.5 text-[15px] leading-relaxed whitespace-pre-wrap text-accent-fg">
          {message.content}
        </p>
      </motion.div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3">
      <LogoMark className="mt-0.5 size-7 shrink-0" />
      <div className="min-w-0 flex-1">
        {message.error ? (
          <div className="rounded-2xl bg-danger-soft px-4 py-3 text-sm text-danger">
            <p className="flex items-center gap-2 font-medium">
              <CircleAlert className="size-4 shrink-0" /> {message.error.message}
            </p>
            {message.error.hint && <p className="mt-1 opacity-90">{message.error.hint}</p>}
            {onRetry && (
              <Button variant="ghost" size="sm" className="mt-2 -ml-2 text-danger" onClick={onRetry} icon={<RotateCcw className="size-3.5" />}>
                Try again
              </Button>
            )}
          </div>
        ) : (
          <>
            {message.status && !message.content && (
              <p className="flex items-center gap-2 py-1 text-sm text-muted">
                <LoaderCircle className="size-4 animate-spin" /> {message.status}
              </p>
            )}
            {message.content && (
              <div className={cn(message.streaming && "streaming-cursor")}>
                <AnswerMarkdown text={message.content} />
              </div>
            )}
            {message.stopped && <p className="mt-1 text-xs text-faint">Stopped.</p>}
            {!message.streaming && message.sources.length > 0 && <Sources sources={message.sources} />}
          </>
        )}
      </div>
    </motion.div>
  );
}

function Sources({ sources }: { sources: ChatSource[] }) {
  const [open, setOpen] = useState(false);
  const ordered = [...sources].sort((a, b) => a.start - b.start);

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex items-center gap-1.5 rounded-md text-xs font-medium text-muted hover:text-fg"
      >
        <FileSearch className="size-3.5" />
        Based on {sources.length} transcript excerpt{sources.length === 1 ? "" : "s"}
        <ChevronDown className={cn("size-3.5 transition-transform", open && "rotate-180")} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.ul
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            {ordered.map((source) => (
              <li key={source.start} className="mt-2 flex gap-2.5 rounded-xl border border-border bg-bg/60 p-3 text-sm">
                <TimestampButton seconds={source.start} />
                <p className="line-clamp-3 min-w-0 flex-1 text-muted">{source.text}</p>
                <span className="shrink-0 font-mono text-[11px] text-faint" title="Similarity to your question">
                  {Math.round(source.similarity * 100)}%
                </span>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
