import { createFileRoute } from "@tanstack/react-router";
import { ModelsPage } from "@/components/settings/ModelsPage";

export const Route = createFileRoute("/settings/models")({
  component: ModelsPage,
});
