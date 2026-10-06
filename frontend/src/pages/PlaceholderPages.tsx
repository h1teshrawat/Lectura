import { Compass } from "lucide-react";
import { useNavigate } from "react-router";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";

export function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <div className="mx-auto max-w-lg px-4 py-20">
      <EmptyState
        icon={<Compass className="size-6" />}
        title="Page not found"
        description="The page you're looking for doesn't exist."
        action={<Button variant="secondary" onClick={() => navigate("/")}>Back to home</Button>}
      />
    </div>
  );
}
