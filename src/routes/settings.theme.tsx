import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/settings/theme")({
  component: SettingsThemePage,
});

function SettingsThemePage() {
  return (
    <div className="mx-auto max-w-2xl space-y-8 p-6">
      <h1 className="text-lg font-semibold text-text-primary">Theme</h1>
      <p className="text-sm text-text-muted">Theme settings — Coming in M3</p>
    </div>
  );
}
