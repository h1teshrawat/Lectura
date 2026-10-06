import { useMemo } from "react";
import Markdown, { type Options } from "react-markdown";

/**
 * Renders a short piece of Markdown text and highlights key terms in it.
 *
 * The highlighting is a tiny "remark plugin": react-markdown first turns the
 * text into a syntax tree, our plugin splits text nodes around each key term
 * and wraps the term in a <mark>, then react-markdown renders the tree.
 */

interface MdNode {
  type: string;
  value?: string;
  children?: MdNode[];
  data?: { hName?: string; hProperties?: Record<string, unknown> };
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function buildTermPattern(terms: string[]): RegExp | null {
  const cleaned = [...new Set(terms.map((t) => t.trim()).filter((t) => t.length >= 3))]
    .sort((a, b) => b.length - a.length); // longest first: "gradient descent" before "gradient"
  if (!cleaned.length) return null;
  // \p{L}/\p{N} lookarounds work like word boundaries, but also for Hindi (Devanagari).
  return new RegExp(`(?<![\\p{L}\\p{N}])(${cleaned.map(escapeRegExp).join("|")})(?![\\p{L}\\p{N}])`, "giu");
}

function highlightPlugin(pattern: RegExp | null) {
  return () => (tree: MdNode) => {
    if (!pattern) return;
    const walk = (node: MdNode) => {
      if (!node.children) return;
      const next: MdNode[] = [];
      for (const child of node.children) {
        if (child.type === "text" && child.value) {
          let last = 0;
          for (const match of child.value.matchAll(pattern)) {
            const start = match.index ?? 0;
            if (start > last) next.push({ type: "text", value: child.value.slice(last, start) });
            next.push({
              type: "highlight",
              data: { hName: "mark", hProperties: { className: "term-highlight" } },
              children: [{ type: "text", value: match[0] }],
            });
            last = start + match[0].length;
          }
          if (last < child.value.length) next.push({ type: "text", value: child.value.slice(last) });
        } else {
          if (child.type !== "inlineCode" && child.type !== "code") walk(child);
          next.push(child);
        }
      }
      node.children = next;
    };
    walk(tree);
  };
}

// Notes text is short and plain: keep paragraphs, emphasis and code; render lists simply.
const COMPONENTS: Options["components"] = {
  p: ({ children }) => <p className="leading-relaxed">{children}</p>,
  code: ({ children }) => <code className="rounded bg-subtle px-1 py-0.5 font-mono text-[0.85em]">{children}</code>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-accent underline underline-offset-2">
      {children}
    </a>
  ),
};

export function RichText({ text, terms = [], className }: { text: string; terms?: string[]; className?: string }) {
  const plugins = useMemo<Options["remarkPlugins"]>(
    () => [highlightPlugin(buildTermPattern(terms))],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [terms.join("\u0000")],
  );
  return (
    <div className={className}>
      <Markdown remarkPlugins={plugins} components={COMPONENTS}>
        {text}
      </Markdown>
    </div>
  );
}
