import { motion } from "framer-motion";
import { AudioLines, Link as LinkIcon, MessageSquare, WandSparkles } from "lucide-react";

const STEPS = [
  {
    icon: LinkIcon,
    title: "Paste or upload",
    text: "Drop in a YouTube link or an MP3/MP4 recording, in English, Hindi or Hinglish.",
  },
  {
    icon: AudioLines,
    title: "Transcribe",
    text: "We use YouTube captions when they exist, otherwise Whisper turns speech into timestamped text.",
  },
  {
    icon: WandSparkles,
    title: "Build your study kit",
    text: "An LLM writes structured notes, flashcards and a quiz, using only what the lecture says.",
  },
  {
    icon: MessageSquare,
    title: "Learn and ask",
    text: "Jump to any moment, revise with spaced repetition and chat with the lecture.",
  },
];

export function HowItWorks() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
      <div className="mb-10 text-center">
        <p className="text-sm font-medium text-accent">How it works</p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">From a long lecture to a revision kit</h2>
      </div>
      <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map(({ icon: Icon, title, text }, index) => (
          <motion.li
            key={title}
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{ delay: index * 0.08, duration: 0.35 }}
            className="relative rounded-2xl border border-border bg-surface p-5"
          >
            <div className="mb-4 flex items-center justify-between">
              <span className="grid size-10 place-items-center rounded-xl bg-accent-soft text-accent">
                <Icon className="size-5" />
              </span>
              <span className="font-mono text-xs text-faint">0{index + 1}</span>
            </div>
            <h3 className="font-semibold">{title}</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-muted">{text}</p>
          </motion.li>
        ))}
      </ol>
    </section>
  );
}
