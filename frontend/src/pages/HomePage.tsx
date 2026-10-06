import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";

import { HowItWorks } from "@/features/home/HowItWorks";
import { LectureInput, type LectureInputState } from "@/features/home/LectureInput";
import { RecentLectures } from "@/features/home/RecentLectures";
import { SampleLectures } from "@/features/home/SampleLectures";
import { useCreateLecture } from "@/hooks/queries";
import { ApiError } from "@/lib/api";

export function HomePage() {
  const navigate = useNavigate();
  const createLecture = useCreateLecture();
  const [input, setInput] = useState<LectureInputState>({
    url: "",
    file: null,
    language: "auto",
    notesLanguage: "english",
  });

  /** Start processing. `sampleUrl` (from a sample card) replaces whatever is in the input. */
  function start(sampleUrl?: string) {
    const file = sampleUrl ? undefined : (input.file ?? undefined);
    createLecture.mutate(
      {
        url: file ? undefined : (sampleUrl ?? input.url).trim(),
        file,
        language: input.language,
        notesLanguage: input.notesLanguage,
      },
      {
        onSuccess: (created) => {
          if (created.cached) {
            toast.success("Loaded from your library", { description: "This lecture was already processed." });
            navigate(`/lectures/${created.id}`);
          } else {
            navigate(`/lectures/${created.id}/processing`);
          }
        },
        onError: (error) => {
          toast.error(error.message, { description: error instanceof ApiError ? error.hint : undefined });
        },
      },
    );
  }

  return (
    <>
      <section className="hero-glow relative">
        <div className="mx-auto flex max-w-3xl flex-col items-center px-4 pt-16 pb-12 text-center sm:px-6 sm:pt-24">
          <motion.span
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-5 inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-muted shadow-sm"
          >
            <Sparkles className="size-3.5 text-accent" />
            Free and open-source · English, Hindi and Hinglish
          </motion.span>
          <motion.h1
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl"
          >
            Turn any lecture into notes, flashcards and quizzes
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="mt-4 max-w-xl text-base text-pretty text-muted sm:text-lg"
          >
            Paste a YouTube link or upload a recording. Lectura transcribes it and builds a study kit with
            timestamps that jump straight to the right moment.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="mt-9 w-full"
          >
            <LectureInput
              state={input}
              onChange={(patch) => setInput((current) => ({ ...current, ...patch }))}
              onSubmit={() => start()}
              loading={createLecture.isPending}
            />
          </motion.div>
        </div>
      </section>

      <SampleLectures
        disabled={createLecture.isPending}
        onPick={(url) => {
          setInput((current) => ({ ...current, url, file: null }));
          start(url);
        }}
      />
      <RecentLectures />
      <HowItWorks />
    </>
  );
}
