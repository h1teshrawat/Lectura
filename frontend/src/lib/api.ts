/** Small typed client for the LectureLens backend. */

import type {
  CardProgress,
  ChatEntry,
  FlashcardProgress,
  Health,
  LectureCreated,
  LectureDetail,
  LectureLanguage,
  LectureSummary,
  NotesLanguage,
  QuizAnswer,
  QuizDifficulty,
  QuizOut,
  QuizResult,
  ReviewResult,
} from "@/types/api";

export const API_BASE = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

/** An error with a user-friendly message and an optional "what to do" hint. */
export class ApiError extends Error {
  readonly status: number;
  readonly hint?: string;

  constructor(status: number, message: string, hint?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.hint = hint;
  }
}

type ErrorDetail = string | { message?: string; hint?: string | null } | Array<{ msg?: string }> | undefined;

function readError(detail: ErrorDetail, status: number): { message: string; hint?: string } {
  if (typeof detail === "string") return { message: detail };
  if (Array.isArray(detail)) return { message: detail[0]?.msg ?? `Invalid request (${status})` };
  if (detail?.message) return { message: detail.message, hint: detail.hint ?? undefined };
  return { message: `Request failed (${status})` };
}

/** fetch() that turns network failures and error responses into ApiError. */
export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(
      0,
      "Can't reach the LectureLens server.",
      "Start the backend: in backend/ run  uvicorn app.main:app --reload",
    );
  }

  if (!response.ok) {
    let body: { detail?: ErrorDetail } | undefined;
    try {
      body = await response.json();
    } catch {
      body = undefined;
    }
    const { message, hint } = readError(body?.detail, response.status);
    throw new ApiError(response.status, message, hint);
  }
  return response;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(path, init);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export interface CreateLectureInput {
  url?: string;
  file?: File;
  language: LectureLanguage;
  notesLanguage: NotesLanguage;
  force?: boolean;
}

export const api = {
  health: () => request<Health>("/api/health"),

  listLectures: (search?: string) =>
    request<LectureSummary[]>(`/api/lectures${search ? `?q=${encodeURIComponent(search)}` : ""}`),

  getLecture: (id: string) => request<LectureDetail>(`/api/lectures/${id}`),

  createLecture: ({ url, file, language, notesLanguage, force }: CreateLectureInput) => {
    // Sent as a form (not JSON) because it may contain a file.
    const form = new FormData();
    if (url) form.append("url", url);
    if (file) form.append("file", file);
    form.append("language", language);
    form.append("notes_language", notesLanguage);
    if (force) form.append("force", "true");
    return request<LectureCreated>("/api/lectures", { method: "POST", body: form });
  },

  progressUrl: (id: string) => `${API_BASE}/api/lectures/${id}/progress`,

  // ---- quiz
  getQuiz: (id: string, options: { count: number; difficulty: QuizDifficulty; ids?: string[] }) => {
    const params = new URLSearchParams({ count: String(options.count), difficulty: options.difficulty });
    if (options.ids?.length) params.set("ids", options.ids.join(","));
    return request<QuizOut>(`/api/lectures/${id}/quiz?${params}`);
  },

  submitQuiz: (id: string, body: { answers: QuizAnswer[]; difficulty: QuizDifficulty; time_taken_seconds: number }) =>
    request<QuizResult>(`/api/lectures/${id}/quiz/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  // ---- flashcards
  getFlashcardProgress: (id: string) => request<FlashcardProgress>(`/api/lectures/${id}/flashcards/progress`),

  reviewCard: (id: string, cardId: string, result: ReviewResult) =>
    request<CardProgress>(`/api/lectures/${id}/flashcards/${cardId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ result }),
    }),

  resetFlashcardProgress: (id: string) =>
    request<void>(`/api/lectures/${id}/flashcards/progress`, { method: "DELETE" }),

  // ---- chat (sending a message streams: see features/chat/streamChat.ts)
  getChat: (id: string) => request<ChatEntry[]>(`/api/lectures/${id}/chat`),
  clearChat: (id: string) => request<void>(`/api/lectures/${id}/chat`, { method: "DELETE" }),
};
