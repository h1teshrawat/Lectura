import { useQuery } from "@tanstack/react-query";
import { ArrowUp, MessageSquare, Square, Trash } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { ChatMessage, type UiMessage } from "@/features/chat/ChatMessage";
import { streamChat } from "@/features/chat/streamChat";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { ChatEntry, LectureDetail } from "@/types/api";

const MAX_LENGTH = 2000;

function fromEntry(entry: ChatEntry): UiMessage {
  return { id: String(entry.id), role: entry.role, content: entry.content, sources: entry.sources };
}

/** Starter questions built from the lecture's own notes. */
function starterQuestions(lecture: LectureDetail): string[] {
  const notes = lecture.notes;
  const questions = ["Summarise this lecture in 5 bullet points"];
  const term = notes?.glossary[0]?.term ?? notes?.sections[0]?.key_terms[0];
  if (term) questions.push(`What is ${term}, in simple words?`);
  const middle = notes?.sections[Math.floor((notes.sections.length - 1) / 2)];
  if (middle) questions.push(`Explain "${middle.title}" with an example from the lecture`);
  const last = notes?.sections.at(-1);
  if (last && last !== middle) questions.push(`What does the lecture conclude about "${last.title}"?`);
  if (lecture.detected_language === "hi" || lecture.notes_language !== "english") {
    questions.push("इस लेक्चर का मुख्य विचार क्या है?");
  }
  return questions.slice(0, 4);
}

export function ChatTab({ lecture }: { lecture: LectureDetail }) {
  const history = useQuery({ queryKey: ["chat", lecture.id], queryFn: () => api.getChat(lecture.id) });
  const [messages, setMessages] = useState<UiMessage[] | null>(null);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const suggestions = useMemo(() => starterQuestions(lecture), [lecture]);

  // Show the saved conversation once it has loaded.
  useEffect(() => {
    if (history.data && messages === null) setMessages(history.data.map(fromEntry));
  }, [history.data, messages]);

  // Stop any answer still streaming when leaving the tab.
  useEffect(() => () => abortRef.current?.abort(), []);

  // Keep the newest message in view while the answer streams in.
  useEffect(() => {
    const box = scrollRef.current;
    if (box) box.scrollTo({ top: box.scrollHeight, behavior: streaming ? "auto" : "smooth" });
  }, [messages, streaming]);

  // Grow the text box with its content (up to ~6 lines).
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [input]);

  function updateAssistant(id: string, patch: (m: UiMessage) => Partial<UiMessage>) {
    setMessages((current) => (current ?? []).map((m) => (m.id === id ? { ...m, ...patch(m) } : m)));
  }

  async function send(text: string) {
    const question = text.trim().slice(0, MAX_LENGTH);
    if (!question || streaming) return;
    const assistantId = `assistant-${Date.now()}`;
    setMessages((current) => [
      ...(current ?? []),
      { id: `user-${Date.now()}`, role: "user", content: question, sources: [] },
      { id: assistantId, role: "assistant", content: "", sources: [], streaming: true, status: "Searching the lecture..." },
    ]);
    setInput("");
    setStreaming(true);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat(
        lecture.id,
        question,
        (event) => {
          switch (event.type) {
            case "status":
              updateAssistant(assistantId, () => ({ status: event.data.message }));
              break;
            case "sources":
              updateAssistant(assistantId, () => ({ sources: event.data.sources, status: "Writing the answer..." }));
              break;
            case "token":
              updateAssistant(assistantId, (m) => ({ content: m.content + event.data.text }));
              break;
            case "done":
              updateAssistant(assistantId, () => ({ content: event.data.answer, streaming: false, status: undefined }));
              break;
            case "error":
              updateAssistant(assistantId, () => ({ error: event.data, streaming: false }));
              break;
          }
        },
        controller.signal,
      );
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        updateAssistant(assistantId, () => ({ streaming: false, stopped: true, status: undefined }));
      } else {
        const message = error instanceof Error ? error.message : "Something went wrong.";
        const hint = error instanceof ApiError ? error.hint : undefined;
        updateAssistant(assistantId, () => ({ error: { message, hint }, streaming: false }));
      }
    } finally {
      // Safety net: never leave a message stuck in the "streaming" state.
      updateAssistant(assistantId, (m) => ({ streaming: false, status: m.content ? undefined : m.status }));
      setStreaming(false);
      abortRef.current = null;
    }
  }

  async function clearChat() {
    try {
      await api.clearChat(lecture.id);
      setMessages([]);
      history.refetch();
    } catch (error) {
      toast.error("Couldn't clear the chat", { description: error instanceof Error ? error.message : undefined });
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter adds a new line. Ignore Enter while an input
    // method (e.g. a Hindi keyboard) is still composing a word.
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      send(input);
    }
  }

  const lastUserQuestion = [...(messages ?? [])].reverse().find((m) => m.role === "user")?.content;

  return (
    <div className="flex h-[calc(100dvh-10rem)] min-h-[520px] flex-col overflow-hidden rounded-2xl border border-border bg-surface">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div>
          <p className="text-sm font-semibold">Chat with this lecture</p>
          <p className="text-xs text-muted">Answers come only from the transcript, with timestamps.</p>
        </div>
        {!!messages?.length && (
          <Button variant="ghost" size="sm" onClick={clearChat} disabled={streaming} icon={<Trash className="size-3.5" />}>
            <span className="hidden sm:inline">Clear</span>
          </Button>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 space-y-5 overflow-y-auto px-4 py-5">
        {messages === null ? (
          <div className="space-y-4">
            <Skeleton className="ml-auto h-10 w-2/3 rounded-2xl" />
            <Skeleton className="h-24 w-5/6 rounded-2xl" />
          </div>
        ) : messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <span className="mb-4 grid size-12 place-items-center rounded-2xl bg-accent-soft text-accent">
              <MessageSquare className="size-6" />
            </span>
            <p className="font-semibold">Ask anything about this lecture</p>
            <p className="mt-1 max-w-sm text-sm text-muted">
              Ask in English, Hindi or Hinglish. If the lecture doesn't cover something, LectureLens will tell you
              instead of making it up.
            </p>
            <div className="mt-6 grid w-full max-w-lg gap-2 sm:grid-cols-2">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => send(suggestion)}
                  className="rounded-xl border border-border px-3.5 py-2.5 text-left text-sm text-muted transition-colors hover:border-accent/50 hover:bg-accent-soft/40 hover:text-fg"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message, i) => (
            <ChatMessage
              key={message.id}
              message={message}
              onRetry={i === messages.length - 1 && lastUserQuestion ? () => send(lastUserQuestion) : undefined}
            />
          ))
        )}
      </div>

      {/* Composer */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="border-t border-border p-3"
      >
        <div className="flex items-end gap-2 rounded-xl border border-border bg-bg px-3 py-2 transition-colors focus-within:border-accent/60">
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            maxLength={MAX_LENGTH}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask a question about the lecture..."
            aria-label="Your question"
            className="max-h-40 min-h-6 flex-1 resize-none bg-transparent py-1 text-[15px] outline-none placeholder:text-faint"
          />
          {streaming ? (
            <Button size="sm" variant="secondary" onClick={() => abortRef.current?.abort()} aria-label="Stop generating" icon={<Square className="size-3.5 fill-current" />} />
          ) : (
            <Button
              type="submit"
              size="sm"
              disabled={!input.trim()}
              aria-label="Send"
              className={cn("size-8 px-0")}
              icon={<ArrowUp className="size-4" />}
            />
          )}
        </div>
        <p className="mt-1.5 hidden text-center text-[11px] text-faint sm:block">
          Enter to send · Shift+Enter for a new line · Click a timestamp to watch that moment
        </p>
      </form>
    </div>
  );
}
