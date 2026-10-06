/**
 * TypeScript versions of the backend's API models (backend/app/api/schemas.py).
 * Keeping these in sync gives us autocomplete and catches typos at compile time.
 */

export type LectureStatus = "queued" | "processing" | "done" | "failed";
export type Stage =
  | "queued"
  | "fetching"
  | "transcribing"
  | "notes"
  | "flashcards"
  | "quiz"
  | "indexing"
  | "done"
  | "failed";
export type LectureLanguage = "auto" | "en" | "hi" | "hinglish";
export type NotesLanguage = "english" | "hindi" | "hinglish";
export type Difficulty = "easy" | "medium" | "hard";

export interface Definition {
  term: string;
  definition: string;
}

export interface NoteSection {
  title: string;
  start_seconds: number;
  summary: string;
  key_points: string[];
  key_terms: string[];
  definitions: Definition[];
}

export interface LectureNotes {
  title: string;
  overview: string;
  key_takeaways: string[];
  sections: NoteSection[];
  glossary: Definition[];
  language: string;
}

export interface Flashcard {
  id: string;
  question: string;
  answer: string;
  start_seconds: number;
}

export interface QuizQuestion {
  id: string;
  question: string;
  options: string[];
  correct_index: number;
  explanation: string;
  difficulty: Difficulty;
  start_seconds: number;
}

export interface LectureSummary {
  id: string;
  title: string;
  source_type: "youtube" | "upload";
  video_id: string | null;
  url: string | null;
  thumbnail_url: string | null;
  channel: string | null;
  duration_seconds: number | null;
  status: LectureStatus;
  notes_language: NotesLanguage;
  flashcard_count: number;
  quiz_count: number;
  created_at: string;
}

export interface LectureDetail extends LectureSummary {
  language: LectureLanguage;
  stage: Stage;
  progress: number;
  message: string;
  error: string | null;
  error_hint: string | null;
  warnings: string[];
  transcript_source: string | null;
  detected_language: string | null;
  llm_model: string | null;
  processing_seconds: number | null;
  notes: LectureNotes | null;
  flashcards: Flashcard[];
}

export interface LectureCreated {
  id: string;
  status: LectureStatus;
  cached: boolean;
}

export interface ProgressEvent {
  status: LectureStatus;
  stage: Stage;
  progress: number;
  message: string;
  warnings: string[];
  error: string | null;
  hint: string | null;
  elapsed_seconds: number | null;
  eta_seconds: number | null;
}

export interface Health {
  status: string;
  version: string;
  llm_provider: string;
  llm_model: string;
  groq_configured: boolean;
  gemini_configured: boolean;
}

// ----------------------------------------------------------------- quiz

export type QuizDifficulty = "mixed" | Difficulty;

export interface QuizOut {
  difficulty: QuizDifficulty;
  questions: QuizQuestion[];
}

export interface QuizAnswer {
  question_id: string;
  /** null = skipped / time ran out */
  selected_index: number | null;
}

export interface QuestionResult {
  question_id: string;
  selected_index: number | null;
  correct_index: number;
  is_correct: boolean;
  explanation: string;
  start_seconds: number;
}

export interface QuizResult {
  attempt_id: number;
  score: number;
  total: number;
  percent: number;
  results: QuestionResult[];
  wrong_question_ids: string[];
}

// ----------------------------------------------------------- flashcards

export type ReviewResult = "got_it" | "again";

export interface CardProgress {
  card_id: string;
  /** Leitner box 1-5, or 0 if never reviewed */
  box: number;
  due_at: string | null;
  is_due: boolean;
  is_mastered: boolean;
  reviews: number;
  correct_count: number;
  last_result: ReviewResult | null;
}

export interface FlashcardProgress {
  total: number;
  new: number;
  learning: number;
  mastered: number;
  due_now: number;
  cards: CardProgress[];
}

// ----------------------------------------------------------------- chat

/** A transcript excerpt the answer was based on. */
export interface ChatSource {
  start: number;
  end: number;
  text: string;
  /** Cosine similarity to the question, 0..1 */
  similarity: number;
}

export interface ChatEntry {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources: ChatSource[];
  created_at: string;
}

// ---------------------------------------------------------------- stats

export interface Stats {
  totals: {
    lectures: number;
    quizzes_taken: number;
    questions_answered: number;
    average_percent: number | null;
    best_percent: number | null;
    flashcards_total: number;
    flashcards_mastered: number;
    cards_reviewed: number;
  };
  score_history: {
    attempt_id: number;
    taken_at: string;
    percent: number;
    score: number;
    total: number;
    difficulty: string;
    lecture_id: string;
    lecture_title: string;
  }[];
  activity: { date: string; questions_answered: number; cards_reviewed: number }[];
  box_distribution: { label: string; box: number; count: number }[];
  lectures: {
    lecture_id: string;
    title: string;
    thumbnail_url: string | null;
    quizzes: number;
    average_percent: number | null;
    last_percent: number | null;
    flashcards_total: number;
    flashcards_mastered: number;
  }[];
}

export type ExportFormat = "pdf" | "md" | "csv";

/** Events streamed back while an answer is generated. */
export type ChatStreamEvent =
  | { type: "status"; data: { message: string } }
  | { type: "sources"; data: { sources: ChatSource[] } }
  | { type: "token"; data: { text: string } }
  | { type: "done"; data: { answer: string; message_id?: number } }
  | { type: "error"; data: { message: string; hint?: string | null } };
