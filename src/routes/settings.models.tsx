import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/settings/models")({
  component: SettingsModelsPage,
});

function SettingsModelsPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-8 p-6">
      <h1 className="text-lg font-semibold text-text-primary">Models</h1>
      <p className="text-sm text-text-muted">Model management — Coming in M3</p>
    </div>
  );
}
