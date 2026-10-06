import { ChartColumn, Library, Plus } from "lucide-react";
import { NavLink } from "react-router";

import { Logo } from "@/components/layout/Logo";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { cn } from "@/lib/cn";

const LINKS = [
  { to: "/", label: "New lecture", icon: Plus, end: true },
  { to: "/library", label: "Library", icon: Library, end: false },
  { to: "/stats", label: "Stats", icon: ChartColumn, end: false },
];

export function Navbar() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-bg/80 backdrop-blur-md">
      <nav className="mx-auto flex h-14 max-w-7xl items-center gap-2 px-4 sm:px-6">
        <Logo />
        <div className="ml-auto flex items-center gap-1">
          {LINKS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium transition-colors",
                  isActive ? "bg-subtle text-fg" : "text-muted hover:bg-subtle hover:text-fg",
                )
              }
            >
              <Icon className="size-4" aria-hidden />
              <span className="hidden sm:inline">{label}</span>
            </NavLink>
          ))}
          <div className="mx-1 h-5 w-px bg-border" aria-hidden />
          <ThemeToggle />
        </div>
      </nav>
    </header>
  );
}
