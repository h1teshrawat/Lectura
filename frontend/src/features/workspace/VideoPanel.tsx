import { AudioLines, Bot, Captions, Clock, ExternalLink, Languages, TriangleAlert } from "lucide-react";
import YouTube, { type YouTubePlayer } from "react-youtube";

import { Badge } from "@/components/ui/Badge";
import { ExportMenu } from "@/features/export/ExportMenu";
import { formatDuration, formatRelativeDate } from "@/lib/format";
import type { LectureDetail } from "@/types/api";

const TRANSCRIPT_SOURCE: Record<string, string> = {
  youtube_captions: "YouTube captions",
  groq_whisper: "Whisper (Groq)",
  local_whisper: "Whisper (local)",
  mixed_whisper: "Whisper",
};

/** The video (or an audio placeholder for uploads) plus the lecture's details. */
export function VideoPanel({ lecture, onPlayerReady }: {
  lecture: LectureDetail;
  onPlayerReady: (player: YouTubePlayer) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-2xl border border-border bg-black shadow-sm">
        {lecture.video_id ? (
          <YouTube
            videoId={lecture.video_id}
            onReady={(e) => onPlayerReady(e.target)}
            className="aspect-video w-full"
            iframeClassName="size-full"
            opts={{ playerVars: { rel: 0, modestbranding: 1 } }}
          />
        ) : (
          <div className="flex aspect-video flex-col items-center justify-center gap-2 bg-subtle text-center text-muted">
            <AudioLines className="size-8 text-faint" />
            <p className="text-sm font-medium text-fg">Uploaded recording</p>
            <p className="max-w-xs px-4 text-xs">Timestamps show where each topic starts in your file.</p>
          </div>
        )}
      </div>

      <div className="px-1">
        <h1 className="text-lg font-semibold leading-snug tracking-tight text-balance">{lecture.title}</h1>
        <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
          {lecture.channel && <span className="font-medium text-fg/80">{lecture.channel}</span>}
          {lecture.duration_seconds ? (
            <span className="flex items-center gap-1">
              <Clock className="size-3.5" /> {formatDuration(lecture.duration_seconds)}
            </span>
          ) : null}
          <span>Added {formatRelativeDate(lecture.created_at)}</span>
          {lecture.url && (
            <a href={lecture.url} target="_blank" rel="noreferrer" className="flex items-center gap-1 hover:text-fg">
              Open on YouTube <ExternalLink className="size-3" />
            </a>
          )}
        </p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {lecture.transcript_source && (
            <Badge icon={<Captions className="size-3" />}>
              {TRANSCRIPT_SOURCE[lecture.transcript_source] ?? lecture.transcript_source}
            </Badge>
          )}
          <Badge icon={<Languages className="size-3" />}>Notes: {lecture.notes_language}</Badge>
          {lecture.llm_model && (
            <Badge icon={<Bot className="size-3" />}>{lecture.llm_model.split(":").pop()}</Badge>
          )}
        </div>
        <div className="mt-4">
          <ExportMenu lectureId={lecture.id} />
        </div>
        {lecture.warnings.map((warning) => (
          <p key={warning} className="mt-3 flex gap-2 rounded-xl bg-warning-soft px-3 py-2.5 text-xs text-warning">
            <TriangleAlert className="size-4 shrink-0" /> {warning}
          </p>
        ))}
      </div>
    </div>
  );
}
