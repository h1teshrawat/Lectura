import { apiFetch } from "@/lib/api";
import type { ChatStreamEvent } from "@/types/api";

/**
 * Send a chat message and receive the answer as a stream of Server-Sent Events.
 *
 * The browser's EventSource only supports GET requests, so for this POST we
 * read the response body ourselves: decode bytes to text, split on blank
 * lines (one SSE "block" each), and parse the `event:` and `data:` lines.
 */
export async function streamChat(
  lectureId: string,
  message: string,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await apiFetch(`/api/lectures/${lectureId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal,
  });
  if (!response.body) throw new Error("The server sent no response body.");

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = parseBlock(block);
      if (event) onEvent(event);
    }
  }
}

function parseBlock(block: string): ChatStreamEvent | null {
  let type = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) type = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (!dataLines.length) return null;
  return { type, data: JSON.parse(dataLines.join("\n")) } as ChatStreamEvent;
}
