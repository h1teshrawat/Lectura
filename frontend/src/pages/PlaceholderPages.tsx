import { ChartColumn, Compass, Library } from "lucide-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";

function Placeholder({ icon, title, description }: { icon: ReactNode; title: string; description: string }) {
  const navigate = useNavigate();
  return (
    <div className="mx-auto max-w-lg px-4 py-20">
      <EmptyState
        icon={icon}
        title={title}
        description={description}
        action={<Button variant="secondary" onClick={() => navigate("/")}>Back to home</Button>}
      />
    </div>
  );
}

export function LibraryPage() {
  return (
    <Placeholder
      icon={<Library className="size-6" />}
      title="Library"
      description="A searchable grid of all your lectures is coming in Phase (h). For now, your recent lectures are on the home page."
    />
  );
}

export function StatsPage() {
  return (
    <Placeholder
      icon={<ChartColumn className="size-6" />}
      title="Stats"
      description="Quiz scores and flashcard progress charts are coming in Phase (h)."
    />
  );
}

export function NotFoundPage() {
  return (
    <Placeholder
      icon={<Compass className="size-6" />}
      title="Page not found"
      description="The page you're looking for doesn't exist."
    />
  );
}
