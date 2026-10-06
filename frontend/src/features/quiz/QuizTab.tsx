import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ListChecks } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/ui/EmptyState";
import { QuizPlayer } from "@/features/quiz/QuizPlayer";
import { QuizResults } from "@/features/quiz/QuizResults";
import { QuizSetup, type QuizOptions } from "@/features/quiz/QuizSetup";
import { api } from "@/lib/api";
import type { QuizQuestion, QuizResult } from "@/types/api";

/** The quiz moves through three screens: setup -> playing -> results. */
type QuizScreen =
  | { kind: "setup" }
  | { kind: "playing"; questions: QuizQuestion[]; options: QuizOptions }
  | { kind: "results"; questions: QuizQuestion[]; options: QuizOptions; result: QuizResult; seconds: number };

export function QuizTab({ lectureId, bankSize }: { lectureId: string; bankSize: number }) {
  const queryClient = useQueryClient();
  const [screen, setScreen] = useState<QuizScreen>({ kind: "setup" });

  const start = useMutation({
    mutationFn: ({ options, ids }: { options: QuizOptions; ids?: string[] }) =>
      api.getQuiz(lectureId, { count: ids?.length ?? options.count, difficulty: options.difficulty, ids }),
    onSuccess: (quiz, { options }) => {
      if (!quiz.questions.length) {
        toast.error("No questions available for these settings.");
        return;
      }
      setScreen({ kind: "playing", questions: quiz.questions, options });
    },
    onError: (error) => toast.error("Couldn't start the quiz", { description: error.message }),
  });

  const submit = useMutation({
    mutationFn: ({ answers, seconds, options, questions }: {
      answers: (number | null)[];
      seconds: number;
      options: QuizOptions;
      questions: QuizQuestion[];
    }) =>
      api.submitQuiz(lectureId, {
        answers: questions.map((q, i) => ({ question_id: q.id, selected_index: answers[i] })),
        difficulty: options.difficulty,
        time_taken_seconds: seconds,
      }),
    onSuccess: (result, { seconds, options, questions }) => {
      setScreen({ kind: "results", result, seconds, options, questions });
      queryClient.invalidateQueries({ queryKey: ["stats"] }); // for the stats dashboard (Phase h)
    },
    onError: (error) => toast.error("Couldn't save your quiz", { description: error.message }),
  });

  if (bankSize === 0) {
    return (
      <EmptyState icon={<ListChecks className="size-6" />} title="No quiz questions" description="This lecture has no quiz questions." />
    );
  }

  switch (screen.kind) {
    case "setup":
      return <QuizSetup bankSize={bankSize} loading={start.isPending} onStart={(options) => start.mutate({ options })} />;
    case "playing":
      return (
        <QuizPlayer
          key={screen.questions.map((q) => q.id).join()}
          questions={screen.questions}
          secondsPerQuestion={screen.options.secondsPerQuestion}
          submitting={submit.isPending}
          onFinish={(answers, seconds) =>
            submit.mutate({ answers, seconds, options: screen.options, questions: screen.questions })
          }
        />
      );
    case "results":
      return (
        <QuizResults
          result={screen.result}
          questions={screen.questions}
          seconds={screen.seconds}
          retrying={start.isPending}
          onRetryWrong={() => start.mutate({ options: screen.options, ids: screen.result.wrong_question_ids })}
          onNewQuiz={() => setScreen({ kind: "setup" })}
        />
      );
  }
}
