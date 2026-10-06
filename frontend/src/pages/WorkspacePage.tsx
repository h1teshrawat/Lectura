import { AnimatePresence, motion } from "framer-motion";
import { FileText, Layers, ListChecks, MessageSquare } from "lucide-react";
import { useCallback, useMemo, useRef, type ReactNode } from "react";
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router";
import type { YouTubePlayer } from "react-youtube";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { FlashcardsTab } from "@/features/flashcards/FlashcardsTab";
import { NotesTab } from "@/features/notes/NotesTab";
import { QuizTab } from "@/features/quiz/QuizTab";
import { PlayerContext, type PlayerControls } from "@/features/workspace/PlayerContext";
import { VideoPanel } from "@/features/workspace/VideoPanel";
import { WorkspaceTabs, type TabItem } from "@/features/workspace/WorkspaceTabs";
import { useLecture } from "@/hooks/queries";

type TabId = "notes" | "flashcards" | "quiz" | "chat";
const TAB_IDS: TabId[] = ["notes", "flashcards", "quiz", "chat"];

export function WorkspacePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: lecture, isLoading, isError, error } = useLecture(id);
  const [searchParams, setSearchParams] = useSearchParams();
  const playerRef = useRef<YouTubePlayer | null>(null);
  const playerBoxRef = useRef<HTMLDivElement>(null);

  // The active tab lives in the URL (?tab=quiz), so refreshing keeps your place.
  const tabParam = searchParams.get("tab") as TabId | null;
  const activeTab: TabId = tabParam && TAB_IDS.includes(tabParam) ? tabParam : "notes";

  const seekTo = useCallback((seconds: number) => {
    const player = playerRef.current;
    if (!player) return;
    player.seekTo(seconds, true);
    player.playVideo();
    // On phones the player is above the tabs: scroll up so you can see it.
    if (window.innerWidth < 1024) playerBoxRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const playerControls = useMemo<PlayerControls>(
    () => ({ canSeek: Boolean(lecture?.video_id), seekTo }),
    [lecture?.video_id, seekTo],
  );

  if (isLoading) return <WorkspaceSkeleton />;
  if (isError || !lecture) {
    return (
      <div className="mx-auto max-w-md px-4 py-24">
        <EmptyState
          icon={<FileText className="size-6" />}
          title="Lecture not found"
          description={error?.message ?? "It may have been deleted."}
          action={<Button onClick={() => navigate("/")}>Back to home</Button>}
        />
      </div>
    );
  }
  if (lecture.status !== "done") return <Navigate to={`/lectures/${lecture.id}/processing`} replace />;

  const tabs: TabItem<TabId>[] = [
    { id: "notes", label: "Notes", icon: FileText, count: lecture.notes?.sections.length },
    { id: "flashcards", label: "Flashcards", icon: Layers, count: lecture.flashcard_count },
    { id: "quiz", label: "Quiz", icon: ListChecks, count: lecture.quiz_count },
    { id: "chat", label: "Chat", icon: MessageSquare },
  ];

  return (
    <PlayerContext.Provider value={playerControls}>
      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-10 lg:py-8">
        {/* Left: sticky video */}
        <div ref={playerBoxRef} className="scroll-mt-16 lg:sticky lg:top-20 lg:self-start">
          <VideoPanel lecture={lecture} onPlayerReady={(player) => (playerRef.current = player)} />
        </div>

        {/* Right: tabs */}
        <div className="min-w-0">
          <div className="sticky top-14 z-20 -mx-4 bg-bg/90 px-4 backdrop-blur-md sm:-mx-6 sm:px-6 lg:mx-0 lg:px-0">
            <WorkspaceTabs
              tabs={tabs}
              active={activeTab}
              onChange={(tab) => setSearchParams(tab === "notes" ? {} : { tab }, { replace: true })}
            />
          </div>
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.18 }}
              className="pt-6"
            >
              {activeTab === "notes" && <NotesTab notes={lecture.notes} />}
              {activeTab === "flashcards" && <FlashcardsTab lectureId={lecture.id} cards={lecture.flashcards} />}
              {activeTab === "quiz" && <QuizTab lectureId={lecture.id} bankSize={lecture.quiz_count} />}
              {activeTab === "chat" && (
                <ComingSoon
                  icon={<MessageSquare className="size-6" />}
                  title="Chat with this lecture"
                  phase="g"
                  description="Ask questions and get answers grounded in the transcript, with timestamp citations."
                />
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </PlayerContext.Provider>
  );
}

function ComingSoon({ icon, title, description, phase }: {
  icon: ReactNode;
  title: string;
  description: string;
  phase: string;
}) {
  return (
    <EmptyState
      icon={icon}
      title={title}
      description={
        <>
          {description} <span className="mt-2 block text-xs text-faint">Coming in Phase ({phase})</span>
        </>
      }
    />
  );
}

function WorkspaceSkeleton() {
  return (
    <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-10 lg:py-8">
      <div className="space-y-4">
        <Skeleton className="aspect-video w-full rounded-2xl" />
        <Skeleton className="h-6 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
      </div>
      <div className="space-y-4">
        <Skeleton className="h-11 w-full" />
        <Skeleton className="h-48 w-full rounded-2xl" />
        <Skeleton className="h-16 w-full rounded-2xl" />
        <Skeleton className="h-16 w-full rounded-2xl" />
        <Skeleton className="h-16 w-full rounded-2xl" />
      </div>
    </div>
  );
}
