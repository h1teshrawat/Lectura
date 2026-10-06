import { KeyRound, Server } from "lucide-react";
import type { ReactNode } from "react";

import { useHealth } from "@/hooks/queries";

/** Warns when the backend isn't running or no LLM API key is configured. */
export function ServerStatusBanner() {
  const { data, isError } = useHealth();

  if (isError) {
    return (
      <Banner icon={<Server className="size-4" />}>
        <strong className="font-semibold">The backend isn't running.</strong> Open a terminal in{" "}
        <code className="font-mono text-xs">backend/</code>, activate the venv and run{" "}
        <code className="font-mono text-xs">uvicorn app.main:app --reload</code>. This page reconnects by itself.
      </Banner>
    );
  }

  const missingKey =
    data && ((data.llm_provider === "groq" && !data.groq_configured) ||
      (data.llm_provider === "gemini" && !data.gemini_configured));
  if (missingKey) {
    return (
      <Banner icon={<KeyRound className="size-4" />}>
        <strong className="font-semibold">No API key for {data.llm_provider}.</strong> Add{" "}
        <code className="font-mono text-xs">{data.llm_provider.toUpperCase()}_API_KEY</code> to{" "}
        <code className="font-mono text-xs">backend/.env</code> and restart the backend.
      </Banner>
    );
  }
  return null;
}

function Banner({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <div className="border-b border-warning/20 bg-warning-soft text-warning">
      <div className="mx-auto flex max-w-7xl items-start gap-2.5 px-4 py-2.5 text-sm sm:px-6">
        <span className="mt-0.5 shrink-0">{icon}</span>
        <p>{children}</p>
      </div>
    </div>
  );
}
