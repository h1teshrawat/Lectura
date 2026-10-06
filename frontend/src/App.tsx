import { Route, Routes } from "react-router";

import { AppLayout } from "@/components/layout/AppLayout";
import { HomePage } from "@/pages/HomePage";
import { LibraryPage, NotFoundPage, StatsPage } from "@/pages/PlaceholderPages";
import { ProcessingPage } from "@/pages/ProcessingPage";
import { WorkspacePage } from "@/pages/WorkspacePage";

export function App() {
  return (
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
  );
}
