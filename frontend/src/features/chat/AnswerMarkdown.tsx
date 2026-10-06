import { useMemo } from "react";
import Markdown, { type Options } from "react-markdown";

import { TimestampButton } from "@/components/TimestampButton";

/**
 * Renders an assistant answer as Markdown, turning citations like [4:05],
 * [4:05 - 5:10] or [1:02:05, 7:30] into clickable timestamp chips.
 *
 * Like the key-term highlighter, this is a small remark plugin: it finds
 * citations in text nodes of the Markdown syntax tree and replaces them with
 * <cite> elements that we render as TimestampButtons.
 */

interface MdNode {
  type: string;
  value?: string;
  children?: MdNode[];
  data?: { hName?: string; hProperties?: Record<string, unknown> };
}

const TIME = String.raw`\d{1,2}:\d{2}(?::\d{2})?`;
// Accepts [4:05] and the full-width 【4:05】 / ［4:05］ brackets some models (e.g. gpt-oss) prefer.
const CITATION = new RegExp(String.raw`[\[【［](${TIME}(?:\s*[-–—,;]\s*${TIME})*)[\]】］]`, "g");
const TIME_IN_GROUP = new RegExp(TIME, "g");

function toSeconds(stamp: string): number {
  return stamp.split(":").reduce((total, part) => total * 60 + Number(part), 0);
}

/** Start times cited in a "[...]" group: "4:05 - 5:10" -> [245], "1:00, 7:30" -> [60, 450]. */
function citedStarts(group: string): number[] {
  return group
    .split(/[,;]/)
    .map((part) => part.match(TIME_IN_GROUP)?.[0])
    .filter((stamp): stamp is string => Boolean(stamp))
    .map(toSeconds);
}

function citationPlugin() {
  return (tree: MdNode) => {
    const walk = (node: MdNode) => {
      if (!node.children) return;
      const next: MdNode[] = [];
      for (const child of node.children) {
        if (child.type !== "text" || !child.value) {
          if (child.type !== "inlineCode" && child.type !== "code") walk(child);
          next.push(child);
          continue;
        }
        let last = 0;
        for (const match of child.value.matchAll(CITATION)) {
          const index = match.index ?? 0;
          if (index > last) next.push({ type: "text", value: child.value.slice(last, index) });
          for (const seconds of citedStarts(match[1])) {
            next.push({ type: "citation", data: { hName: "cite", hProperties: { dataSeconds: seconds } } });
          }
          last = index + match[0].length;
        }
        if (last < child.value.length) next.push({ type: "text", value: child.value.slice(last) });
      }
      node.children = next;
    };
    walk(tree);
  };
}

const COMPONENTS: Options["components"] = {
  p: ({ children }) => <p className="leading-relaxed [&:not(:first-child)]:mt-3">{children}</p>,
  ul: ({ children }) => <ul className="mt-2 list-disc space-y-1.5 pl-5 marker:text-faint">{children}</ul>,
  ol: ({ children }) => <ol className="mt-2 list-decimal space-y-1.5 pl-5 marker:text-faint">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  code: ({ children }) => <code className="rounded bg-subtle px-1 py-0.5 font-mono text-[0.85em]">{children}</code>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-accent underline underline-offset-2">
      {children}
    </a>
  ),
  cite: ({ node }) => (
    <TimestampButton seconds={Number(node?.properties?.dataSeconds ?? 0)} className="mx-0.5 align-[1px]" />
  ),
};

export function AnswerMarkdown({ text }: { text: string }) {
  const plugins = useMemo<Options["remarkPlugins"]>(() => [citationPlugin], []);
  return (
    <div className="text-[15px]">
      <Markdown remarkPlugins={plugins} components={COMPONENTS}>
        {text}
      </Markdown>
    </div>
  );
}
