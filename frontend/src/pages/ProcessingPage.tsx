import { useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { AudioLines, CircleAlert, CircleCheck, RotateCcw, TriangleAlert, Upload, WifiOff } from "lucide-react";
import { useEffect } from "react";
import { Navigate, useNavigate, useParams } from "react-router";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { ProcessingStepper } from "@/features/processing/ProcessingStepper";
import { queryKeys, useCreateLecture, useLecture } from "@/hooks/queries";
import { useLectureProgress } from "@/hooks/useLectureProgress";
import { ApiError } from "@/lib/api";
import { formatDuration, formatEta, formatTimestamp } from "@/lib/format";

export function ProcessingPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const lectureQuery = useLecture(id);
  const lecture = lectureQuery.data;
  const alreadyFinished = lecture?.status === "done";
  const { event, connectionLost } = useLectureProgress(id, Boolean(lecture) && !alreadyFinished);
  const retry = useCreateLecture();

  // Prefer the live event; fall back to what the database said when the page loaded.
  const status = event?.status ?? lecture?.status ?? "queued";
  const stage = event?.stage ?? lecture?.stage ?? "queued";
  const progress = event?.progress ?? lecture?.progress ?? 0;
  const message = event?.message ?? lecture?.message ?? "Waiting to start...";
  const warnings = event?.warnings ?? lecture?.warnings ?? [];
  const error = event?.error ?? lecture?.error;
  const hint = event?.hint ?? lecture?.error_hint;

  // The title and thumbnail arrive after transcription, so refresh the lecture when the stage changes.
  useEffect(() => {
    if (id && event?.stage) queryClient.invalidateQueries({ queryKey: queryKeys.lecture(id) });
  }, [id, event?.stage, queryClient]);

  // When finished, show the success state briefly, then open the workspace.
  useEffect(() => {
    if (event?.status !== "done" || !id) return;
    queryClient.invalidateQueries({ queryKey: ["lectures"] });
    const timer = setTimeout(() => navigate(`/lectures/${id}`, { replace: true }), 1100);
    return () => clearTimeout(timer);
  }, [event?.status, id, navigate, queryClient]);

  if (lectureQuery.isError) {
    return (
      <div className="mx-auto max-w-xl px-4 py-24 text-center">
        <p className="font-medium">{lectureQuery.error.message}</p>
        <Button className="mt-6" variant="secondary" onClick={() => navigate("/")}>Back to home</Button>
      </div>
    );
  }
  if (alreadyFinished) return <Navigate to={`/lectures/${id}`} replace />;

  function retryLecture() {
    if (!lecture?.url) return;
    retry.mutate(
      { url: lecture.url, language: lecture.language, notesLanguage: lecture.notes_language },
      {
        onSuccess: (created) => navigate(`/lectures/${created.id}/processing`, { replace: true }),
        onError: (e) => toast.error(e.message, { description: e instanceof ApiError ? e.hint : undefined }),
      },
    );
  }

  const failed = status === "failed";
  const done = status === "done";
  const percent = Math.round(progress * 100);

  return (
    <div className="mx-auto max-w-2xl px-4 py-10 sm:px-6 sm:py-16">
      {/* Lecture header */}
      <div className="mb-8 flex items-center gap-4">
        <div className="grid aspect-video w-28 shrink-0 place-items-center overflow-hidden rounded-xl bg-subtle sm:w-36">
          {lecture?.thumbnail_url ? (
            <img src={lecture.thumbnail_url} alt="" className="size-full object-cover" />
          ) : lecture ? (
            <AudioLines className="size-6 text-faint" />
          ) : (
            <Skeleton className="size-full" />
          )}
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium text-accent">
            {failed ? "Processing failed" : done ? "All done" : "Processing your lecture"}
          </p>
          {lecture ? (
            <h1 className="mt-0.5 line-clamp-2 text-lg font-semibold tracking-tight sm:text-xl">{lecture.title}</h1>
          ) : (
            <Skeleton className="mt-2 h-6 w-64" />
          )}
          {lecture?.duration_seconds ? (
            <p className="mt-1 text-sm text-muted">
              {formatDuration(lecture.duration_seconds)}
              {lecture.channel ? ` · ${lecture.channel}` : ""}
            </p>
          ) : null}
        </div>
      </div>

      {/* Progress bar */}
      <div className="rounded-2xl border border-border bg-surface p-5 sm:p-6">
        <div className="mb-2 flex items-baseline justify-between gap-3">
          <span className="text-3xl font-semibold tabular-nums tracking-tight">{percent}%</span>
          <span className="text-right text-sm text-muted">
            {failed
              ? "Stopped"
              : done
                ? "Opening your study kit..."
                : event?.eta_seconds != null && progress >= 0.1
                  ? formatEta(event.eta_seconds)
                  : "Estimating time..."}
            {event?.elapsed_seconds != null && !done && !failed && (
              <span className="ml-2 text-faint">· {formatTimestamp(event.elapsed_seconds)} elapsed</span>
            )}
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-subtle">
          <motion.div
            className={failed ? "h-full rounded-full bg-danger" : "h-full rounded-full bg-accent"}
            initial={false}
            animate={{ width: `${Math.max(percent, 2)}%` }}
            transition={{ type: "spring", stiffness: 60, damping: 20 }}
          />
        </div>

        {connectionLost && !failed && !done && (
          <p className="mt-3 flex items-center gap-1.5 text-sm text-warning">
            <WifiOff className="size-4" /> Connection to the server lost. Reconnecting...
          </p>
        )}

        <div className="mt-6">
          <ProcessingStepper stage={stage} status={status} message={message} />
        </div>
      </div>

      {/* Warnings (e.g. very long video) */}
      {warnings.length > 0 && (
        <div className="mt-4 space-y-2">
          {warnings.map((warning) => (
            <p key={warning} className="flex gap-2 rounded-xl bg-warning-soft px-4 py-3 text-sm text-warning">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" /> {warning}
            </p>
          ))}
        </div>
      )}

      {/* Success */}
      {done && (
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          className="mt-4 flex items-center gap-2 rounded-xl bg-success-soft px-4 py-3 text-sm font-medium text-success"
        >
          <CircleCheck className="size-5" /> Your notes, flashcards and quiz are ready!
        </motion.div>
      )}

      {/* Failure */}
      {failed && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-4 rounded-2xl border border-danger/30 bg-danger-soft p-5"
        >
          <div className="flex gap-3 text-danger">
            <CircleAlert className="mt-0.5 size-5 shrink-0" />
            <div>
              <p className="font-semibold">{error ?? "Something went wrong."}</p>
              {hint && <p className="mt-1 text-sm opacity-90">{hint}</p>}
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2 pl-8">
            {lecture?.source_type === "youtube" && (
              <Button onClick={retryLecture} loading={retry.isPending} icon={<RotateCcw className="size-4" />}>
                Try again
              </Button>
            )}
            <Button variant="secondary" onClick={() => navigate("/")} icon={<Upload className="size-4" />}>
              Upload a file instead
            </Button>
          </div>
        </motion.div>
      )}

      {!failed && !done && (
        <p className="mt-6 text-center text-sm text-faint">
          You can leave this page. Processing continues in the background and your lecture will appear in the library.
        </p>
      )}
    </div>
  );
}
