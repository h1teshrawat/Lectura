import { motion } from "framer-motion";
import { useEffect } from "react";
import { Outlet, useLocation } from "react-router";

import { Navbar } from "@/components/layout/Navbar";
import { ServerStatusBanner } from "@/components/ServerStatusBanner";

export function AppLayout() {
  const location = useLocation();

  // Start every new page at the top (single-page apps keep the old scroll position otherwise).
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);

  return (
    <div className="flex min-h-dvh flex-col">
      <Navbar />
      <ServerStatusBanner />
      {/* Each page fades in gently when the route changes. */}
      <motion.main
        key={location.pathname}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25, ease: "easeOut" }}
        className="flex-1"
      >
        <Outlet />
      </motion.main>
      <footer className="border-t border-border py-6 text-center text-xs text-faint">
        LectureLens · Built with Whisper, open LLMs and RAG · B.Tech AI/ML minor project
      </footer>
    </div>
  );
}
