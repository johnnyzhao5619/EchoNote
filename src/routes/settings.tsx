import { createFileRoute } from "@tanstack/react-router";
import { SettingsMain } from "@/components/settings/SettingsMain";

export const Route = createFileRoute("/settings")({
  component: SettingsPage,
});

function SettingsPage() {
  return <SettingsMain />;
}
