import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/settings")({
  component: SettingsPage,
});

function SettingsPage() {
  return (
    <div className="flex h-full items-center justify-center text-text-muted">
      <p>Settings — Coming in M5</p>
    </div>
  );
}
