import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/recording")({
  component: RecordingPage,
});

function RecordingPage() {
  return (
    <div className="flex h-full items-center justify-center text-text-muted">
      <p>Recording — Coming in M2</p>
    </div>
  );
}
