import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";

/** Copies text to the clipboard and briefly shows a check mark. */
export function CopyButton({ text, label = "Copy", successMessage = "Copied to clipboard" }: {
  text: string;
  label?: string;
  successMessage?: string;
}) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 1800);
    return () => clearTimeout(timer);
  }, [copied]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success(successMessage);
    } catch {
      toast.error("Couldn't copy. Your browser blocked clipboard access.");
    }
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={copy}
      icon={copied ? <Check className="size-4 text-success" /> : <Copy className="size-4" />}
      aria-label={label}
    >
      <span className="hidden sm:inline">{copied ? "Copied" : label}</span>
    </Button>
  );
}
