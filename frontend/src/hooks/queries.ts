/** React Query hooks: fetching, caching and refreshing data from the API. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type CreateLectureInput } from "@/lib/api";

export const queryKeys = {
  health: ["health"] as const,
  lectures: (search?: string) => ["lectures", search ?? ""] as const,
  lecture: (id: string) => ["lecture", id] as const,
  flashcardProgress: (id: string) => ["flashcard-progress", id] as const,
};

export function useFlashcardProgress(lectureId: string) {
  return useQuery({
    queryKey: queryKeys.flashcardProgress(lectureId),
    queryFn: () => api.getFlashcardProgress(lectureId),
  });
}

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: api.health,
    retry: false,
    // While the server is down, check again every 5 s so the banner disappears by itself.
    refetchInterval: (query) => (query.state.status === "error" ? 5000 : false),
  });
}

export function useLectures(search?: string) {
  return useQuery({ queryKey: queryKeys.lectures(search), queryFn: () => api.listLectures(search) });
}

export function useLecture(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.lecture(id ?? ""),
    queryFn: () => api.getLecture(id!),
    enabled: Boolean(id),
  });
}

export function useCreateLecture() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateLectureInput) => api.createLecture(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["lectures"] }),
  });
}
