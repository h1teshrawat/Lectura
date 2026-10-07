import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router";

import { AppLayout } from "@/components/layout/AppLayout";
import { Skeleton } from "@/components/ui/Skeleton";
import { HomePage } from "@/pages/HomePage";
import { NotFoundPage } from "@/pages/PlaceholderPages";

// Code-splitting: these pages (and heavy libraries they use, like Recharts,
// the YouTube player and Markdown) are only downloaded when first visited,
// so the home page loads much faster.
const WorkspacePage = lazy(() => import("@/pages/WorkspacePage").then((m) => ({ default: m.WorkspacePage })));
const ProcessingPage = lazy(() => import("@/pages/ProcessingPage").then((m) => ({ default: m.ProcessingPage })));
const LibraryPage = lazy(() => import("@/pages/LibraryPage").then((m) => ({ default: m.LibraryPage })));
const StatsPage = lazy(() => import("@/pages/StatsPage").then((m) => ({ default: m.StatsPage })));

function PageFallback() {
  return (
    <div className="mx-auto max-w-7xl space-y-4 px-4 py-10 sm:px-6">
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-64 w-full rounded-2xl" />
    </div>
  );
}

export function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<HomePage />} />
          <Route path="lectures/:id" element={<WorkspacePage />} />
          <Route path="lectures/:id/processing" element={<ProcessingPage />} />
          <Route path="library" element={<LibraryPage />} />
          <Route path="stats" element={<StatsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
