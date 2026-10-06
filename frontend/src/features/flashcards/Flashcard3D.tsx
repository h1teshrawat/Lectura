import { motion } from "framer-motion";
import type { CSSProperties, ReactNode } from "react";

import { TimestampButton } from "@/components/TimestampButton";
import { Kbd } from "@/components/ui/Kbd";
import { cn } from "@/lib/cn";
import type { CardProgress, Flashcard } from "@/types/api";

const BOX_LABELS = ["New", "Box 1", "Box 2", "Box 3", "Box 4", "Box 5"];

/**
 * A card with two faces. Flipping rotates the whole card 180° around the Y
 * axis; `backface-visibility: hidden` hides whichever face points away, and
 * `perspective` on the parent makes the rotation look three-dimensional.
 */
export function Flashcard3D({ card, progress, flipped, onFlip }: {
  card: Flashcard;
  progress?: CardProgress;
  flipped: boolean;
  onFlip: () => void;
}) {
  return (
    <div style={{ perspective: 1400 }}>
      <motion.div
        role="button"
        tabIndex={0}
        aria-label={flipped ? "Show question" : "Show answer"}
        onClick={onFlip}
        animate={{ rotateY: flipped ? 180 : 0 }}
        transition={{ type: "spring", stiffness: 220, damping: 24 }}
        style={{ transformStyle: "preserve-3d" }}
        className="relative h-72 cursor-pointer outline-none sm:h-80"
      >
        <Face>
          <div className="flex items-center justify-between text-xs font-medium">
            <span className="tracking-wider text-accent uppercase">Question</span>
            <span className="text-faint">
              {BOX_LABELS[progress?.box ?? 0]}
              {progress?.reviews ? ` · reviewed ${progress.reviews}×` : ""}
            </span>
          </div>
          <p className="my-auto py-4 text-center text-lg leading-relaxed font-medium text-balance sm:text-xl">
            {card.question}
          </p>
          <p className="flex items-center justify-center gap-1.5 text-xs text-faint">
            Click or press <Kbd>Space</Kbd> to reveal the answer
          </p>
        </Face>

        <Face back>
          <div className="flex items-center justify-between text-xs font-medium">
            <span className="tracking-wider text-success uppercase">Answer</span>
            <TimestampButton seconds={card.start_seconds} />
          </div>
          <p className="my-auto py-4 text-center text-base leading-relaxed text-balance sm:text-lg">{card.answer}</p>
          <p className="line-clamp-2 text-center text-xs text-faint">{card.question}</p>
        </Face>
      </motion.div>
    </div>
  );
}

function Face({ back = false, children }: { back?: boolean; children: ReactNode }) {
  const style: CSSProperties = {
    backfaceVisibility: "hidden",
    WebkitBackfaceVisibility: "hidden",
    transform: back ? "rotateY(180deg)" : undefined,
  };
  return (
    <div
      style={style}
      className={cn(
        "absolute inset-0 flex flex-col overflow-y-auto rounded-3xl border p-5 shadow-[0_12px_40px_-16px_rgba(0,0,0,0.25)] sm:p-7",
        back ? "border-success/25 bg-surface" : "border-border bg-surface",
      )}
    >
      {children}
    </div>
  );
}
