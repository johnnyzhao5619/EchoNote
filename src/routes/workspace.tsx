import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/workspace")({
  component: WorkspacePage,
});

function WorkspacePage() {
  return (
    <div className="flex h-full items-center justify-center text-text-muted">
      <p>Workspace — Coming in M4</p>
    </div>
  );
}
