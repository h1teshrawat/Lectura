import { Clock, Play } from "lucide-react";

import { SAMPLE_LECTURES } from "@/lib/samples";

export function SampleLectures({ onPick, disabled }: { onPick: (url: string) => void; disabled?: boolean }) {
  return (
    <section className="mx-auto max-w-6xl px-4 sm:px-6">
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Try a sample lecture</h2>
          <p className="text-sm text-muted">One click: we'll process it (or load it instantly if you already have).</p>
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        {SAMPLE_LECTURES.map((sample) => (
          <button
            key={sample.videoId}
            type="button"
            disabled={disabled}
            onClick={() => onPick(sample.url)}
            className="group overflow-hidden rounded-2xl border border-border bg-surface text-left transition-all hover:-translate-y-0.5 hover:border-border-strong hover:shadow-lg hover:shadow-black/5 disabled:opacity-60"
          >
            <div className="relative aspect-video overflow-hidden bg-subtle">
              <img
                src={`https://i.ytimg.com/vi/${sample.videoId}/mqdefault.jpg`}
                alt=""
                loading="lazy"
                className="size-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
              />
              <span className="absolute inset-0 grid place-items-center bg-black/0 transition-colors group-hover:bg-black/25">
                <span className="grid size-11 scale-90 place-items-center rounded-full bg-white/95 text-black opacity-0 shadow-lg transition-all group-hover:scale-100 group-hover:opacity-100">
                  <Play className="ml-0.5 size-5 fill-current" />
                </span>
              </span>
              <span className="absolute right-2 bottom-2 flex items-center gap-1 rounded-md bg-black/75 px-1.5 py-0.5 text-xs font-medium text-white">
                <Clock className="size-3" /> {sample.duration}
              </span>
            </div>
            <div className="p-4">
              <span className="text-xs font-medium text-accent">{sample.tag}</span>
              <p className="mt-1 line-clamp-2 font-medium leading-snug">{sample.title}</p>
              <p className="mt-1 text-sm text-muted">{sample.channel}</p>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
