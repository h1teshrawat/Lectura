import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/cn";

export interface MenuItem {
  label: string;
  icon?: ReactNode;
  description?: string;
  /** A link (e.g. a file download) ... */
  href?: string;
  /** ... or an action. */
  onSelect?: () => void;
  danger?: boolean;
}

/** A small dropdown menu that closes on outside click or Escape. */
export function Menu({ trigger, items, align = "right", label, onOpenChange }: {
  trigger: (props: { open: boolean; toggle: () => void }) => ReactNode;
  items: (MenuItem | "divider")[];
  align?: "left" | "right";
  label: string;
  /** Lets the parent react, e.g. raise a card above its neighbours while the menu is open. */
  onOpenChange?: (open: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    onOpenChange?.(open);
  }, [open, onOpenChange]);

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const itemClass = (danger?: boolean) =>
    cn(
      "flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors",
      danger ? "text-danger hover:bg-danger-soft" : "text-fg hover:bg-subtle",
    );

  return (
    <div ref={rootRef} className="relative" onClick={(e) => e.stopPropagation()}>
      {trigger({ open, toggle: () => setOpen((o) => !o) })}
      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            aria-label={label}
            initial={{ opacity: 0, scale: 0.96, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -4 }}
            transition={{ duration: 0.12 }}
            className={cn(
              "absolute top-full z-50 mt-1.5 w-60 origin-top rounded-xl border border-border bg-surface p-1.5 shadow-xl shadow-black/10",
              align === "right" ? "right-0" : "left-0",
            )}
          >
            {items.map((item, i) =>
              item === "divider" ? (
                <div key={`divider-${i}`} className="my-1 h-px bg-border" />
              ) : item.href ? (
                <a key={item.label} role="menuitem" href={item.href} className={itemClass(item.danger)} onClick={() => setOpen(false)}>
                  <MenuItemContent item={item} />
                </a>
              ) : (
                <button
                  key={item.label}
                  type="button"
                  role="menuitem"
                  className={itemClass(item.danger)}
                  onClick={() => {
                    setOpen(false);
                    item.onSelect?.();
                  }}
                >
                  <MenuItemContent item={item} />
                </button>
              ),
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function MenuItemContent({ item }: { item: MenuItem }) {
  return (
    <>
      {item.icon && <span className="mt-0.5 shrink-0 opacity-80">{item.icon}</span>}
      <span className="min-w-0">
        <span className="block font-medium">{item.label}</span>
        {item.description && <span className="block text-xs text-muted">{item.description}</span>}
      </span>
    </>
  );
}
