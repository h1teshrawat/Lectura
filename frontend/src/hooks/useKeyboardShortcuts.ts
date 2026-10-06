import { useEffect, useRef } from "react";

type Handlers = Record<string, (event: KeyboardEvent) => void>;

/**
 * Listen for keyboard shortcuts on the whole page, e.g. `{ " ": flip, ArrowRight: next }`.
 *
 * Shortcuts are ignored while typing in a text field or when Ctrl/Cmd/Alt is
 * held, so they never interfere with normal typing or browser shortcuts.
 */
export function useKeyboardShortcuts(handlers: Handlers, enabled = true): void {
  const handlersRef = useRef(handlers);
  useEffect(() => {
    handlersRef.current = handlers;
  });

  useEffect(() => {
    if (!enabled) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable='true']")) return;

      const handler = handlersRef.current[event.key] ?? handlersRef.current[event.key.toLowerCase()];
      if (handler) {
        event.preventDefault(); // e.g. stop Space from scrolling the page
        handler(event);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [enabled]);
}
