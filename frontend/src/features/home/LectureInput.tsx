import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, AudioLines, FileText, Languages, Link as LinkIcon, Upload, X } from "lucide-react";
import { useRef, useState, type DragEvent, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { SelectField } from "@/components/ui/SelectField";
import { cn } from "@/lib/cn";
import { formatFileSize } from "@/lib/format";
import { ACCEPTED_FILE_TYPES, isAcceptedFile, looksLikeYouTubeUrl } from "@/lib/youtube";
import type { LectureLanguage, NotesLanguage } from "@/types/api";

const LECTURE_LANGUAGES: { value: LectureLanguage; label: string }[] = [
  { value: "auto", label: "Auto-detect" },
  { value: "en", label: "English" },
  { value: "hi", label: "Hindi" },
  { value: "hinglish", label: "Hinglish" },
];

const NOTES_LANGUAGES: { value: NotesLanguage; label: string }[] = [
  { value: "english", label: "English" },
  { value: "hindi", label: "Hindi" },
  { value: "hinglish", label: "Hinglish" },
];

export interface LectureInputState {
  url: string;
  file: File | null;
  language: LectureLanguage;
  notesLanguage: NotesLanguage;
}

interface LectureInputProps {
  state: LectureInputState;
  onChange: (patch: Partial<LectureInputState>) => void;
  onSubmit: () => void;
  loading: boolean;
}

export function LectureInput({ state, onChange, onSubmit, loading }: LectureInputProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragDepth = useRef(0);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function chooseFile(file: File | undefined) {
    if (!file) return;
    if (!isAcceptedFile(file)) {
      setError("That file type isn't supported. Use MP3, MP4, WAV, M4A, WEBM, OGG or FLAC.");
      return;
    }
    setError(null);
    onChange({ file, url: "" });
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!state.file) {
      if (!state.url.trim()) {
        setError("Paste a YouTube link or choose a file first.");
        return;
      }
      if (!looksLikeYouTubeUrl(state.url)) {
        setError("That doesn't look like a YouTube video link. Example: https://youtu.be/aircAruvnKk");
        return;
      }
    }
    setError(null);
    onSubmit();
  }

  // Drag events fire for every child element, so we count enter/leave pairs.
  const dragHandlers = {
    onDragEnter: (e: DragEvent) => {
      e.preventDefault();
      dragDepth.current += 1;
      setDragging(true);
    },
    onDragOver: (e: DragEvent) => e.preventDefault(),
    onDragLeave: (e: DragEvent) => {
      e.preventDefault();
      dragDepth.current -= 1;
      if (dragDepth.current <= 0) setDragging(false);
    },
    onDrop: (e: DragEvent) => {
      e.preventDefault();
      dragDepth.current = 0;
      setDragging(false);
      chooseFile(e.dataTransfer.files[0]);
    },
  };

  return (
    <form onSubmit={handleSubmit} className="w-full" {...dragHandlers}>
      <div
        className={cn(
          "relative rounded-2xl border bg-surface p-2 shadow-[0_1px_2px_rgba(0,0,0,0.04),0_8px_24px_-12px_rgba(0,0,0,0.12)] transition-all",
          dragging ? "border-accent ring-4 ring-accent/15" : "border-border focus-within:border-accent/60",
          error && !dragging && "border-danger/60",
        )}
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="flex min-w-0 flex-1 items-center gap-3 pl-3">
            <AnimatePresence mode="wait" initial={false}>
              {state.file ? (
                <motion.div
                  key="file"
                  initial={{ opacity: 0, scale: 0.97 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex h-12 min-w-0 flex-1 items-center gap-3"
                >
                  <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent">
                    <AudioLines className="size-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{state.file.name}</p>
                    <p className="text-xs text-muted">{formatFileSize(state.file.size)}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onChange({ file: null })}
                    className="grid size-8 place-items-center rounded-lg text-muted hover:bg-subtle hover:text-fg"
                    aria-label="Remove file"
                  >
                    <X className="size-4" />
                  </button>
                </motion.div>
              ) : (
                <motion.div
                  key="url"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex h-12 min-w-0 flex-1 items-center gap-3"
                >
                  <LinkIcon className="size-5 shrink-0 text-faint" aria-hidden />
                  <input
                    type="text"
                    inputMode="url"
                    value={state.url}
                    onChange={(e) => {
                      onChange({ url: e.target.value });
                      if (error) setError(null);
                    }}
                    placeholder="Paste a YouTube link or drop a file"
                    aria-label="YouTube link"
                    autoComplete="off"
                    spellCheck={false}
                    className="h-full min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-faint"
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <div className="flex gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_FILE_TYPES}
              className="hidden"
              onChange={(e) => {
                chooseFile(e.target.files?.[0]);
                e.target.value = ""; // allow choosing the same file again
              }}
            />
            <Button
              variant="secondary"
              size="lg"
              onClick={() => fileInputRef.current?.click()}
              icon={<Upload className="size-4" />}
              className="flex-1 sm:flex-none"
            >
              Upload
            </Button>
            <Button
              type="submit"
              size="lg"
              loading={loading}
              className="flex-1 sm:flex-none"
            >
              Generate
              {!loading && <ArrowRight className="size-4" />}
            </Button>
          </div>
        </div>

        {/* Drop overlay */}
        <AnimatePresence>
          {dragging && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="pointer-events-none absolute inset-0 grid place-items-center rounded-2xl bg-accent-soft/95 text-accent"
            >
              <span className="flex items-center gap-2 font-medium">
                <Upload className="size-5" /> Drop your lecture file
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {error && (
          <motion.p
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            role="alert"
            className="mt-2 px-1 text-left text-sm text-danger"
          >
            {error}
          </motion.p>
        )}
      </AnimatePresence>

      <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
        <SelectField
          label="Lecture"
          icon={<Languages className="size-3.5" />}
          value={state.language}
          options={LECTURE_LANGUAGES}
          onChange={(language) => onChange({ language })}
        />
        <SelectField
          label="Notes in"
          icon={<FileText className="size-3.5" />}
          value={state.notesLanguage}
          options={NOTES_LANGUAGES}
          onChange={(notesLanguage) => onChange({ notesLanguage })}
        />
        <span className="text-xs text-faint">MP3, MP4, WAV and more · up to 500 MB</span>
      </div>
    </form>
  );
}
