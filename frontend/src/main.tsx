import "./index.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "framer-motion";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { Toaster } from "sonner";

import { App } from "@/App";
import { ThemeProvider, useTheme } from "@/hooks/useTheme";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 30_000 },
  },
});

function ThemedToaster() {
  const { theme } = useTheme();
  return <Toaster theme={theme} position="top-center" richColors closeButton />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        {/* Respect the operating system's "reduce motion" setting. */}
        <MotionConfig reducedMotion="user">
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </MotionConfig>
        <ThemedToaster />
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
);
