import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/timeline")({
  component: TimelinePage,
});

function TimelinePage() {
  return (
    <div className="flex h-full items-center justify-center text-text-muted">
      <p>Timeline — Coming in M4</p>
    </div>
  );
}
