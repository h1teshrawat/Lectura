/**
 * Study-session logic for flashcards (pure functions, no React).
 *
 * A session is a queue of card IDs:
 *  - "Got it"        -> the card leaves the queue.
 *  - "Review again"  -> the card is put back a few places later, so it returns
 *                       soon in the same session (short-term spaced repetition).
 */

import type { CardProgress, Flashcard } from "@/types/api";

export type StudyMode = "due" | "all";

/** How many cards later a "Review again" card comes back. */
export const REQUEUE_GAP = 3;

export function buildQueue(cards: Flashcard[], progress: Map<string, CardProgress>, mode: StudyMode): string[] {
  if (mode === "all") return cards.map((card) => card.id);
  // Due mode: new cards and cards whose review date has arrived, weakest boxes first.
  return cards
    .filter((card) => progress.get(card.id)?.is_due ?? true)
    .sort((a, b) => (progress.get(a.id)?.box ?? 0) - (progress.get(b.id)?.box ?? 0))
    .map((card) => card.id);
}

export function removeAt(queue: string[], index: number): string[] {
  return [...queue.slice(0, index), ...queue.slice(index + 1)];
}

export function requeue(queue: string[], index: number, gap = REQUEUE_GAP): string[] {
  const rest = removeAt(queue, index);
  const position = Math.min(index + gap, rest.length);
  return [...rest.slice(0, position), queue[index], ...rest.slice(position)];
}

/** Fisher-Yates shuffle: every order is equally likely. */
export function shuffle<T>(items: T[]): T[] {
  const result = [...items];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}
