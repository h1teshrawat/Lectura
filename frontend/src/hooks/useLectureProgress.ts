import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { ProgressEvent } from "@/types/api";

/**
 * Follow a lecture's processing progress with Server-Sent Events.
 *
 * The browser's built-in EventSource keeps one HTTP connection open and the
 * server pushes an event whenever something changes. We close it ourselves
 * once the job is done or failed (otherwise EventSource would reconnect).
 */
export function useLectureProgress(lectureId: string | undefined, enabled = true) {
  const [event, setEvent] = useState<ProgressEvent | null>(null);
  const [connectionLost, setConnectionLost] = useState(false);

  useEffect(() => {
    if (!lectureId || !enabled) return;
    const source = new EventSource(api.progressUrl(lectureId));

    source.addEventListener("progress", (message) => {
      const data = JSON.parse((message as MessageEvent<string>).data) as ProgressEvent;
      setEvent(data);
      setConnectionLost(false);
      if (data.status === "done" || data.status === "failed") source.close();
    });
    // EventSource retries automatically; we just show a hint while it's disconnected.
    source.onerror = () => {
      if (source.readyState !== EventSource.CLOSED) setConnectionLost(true);
    };

    return () => source.close();
  }, [lectureId, enabled]);

  return { event, connectionLost };
}
