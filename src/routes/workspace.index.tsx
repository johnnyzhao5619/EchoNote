import { createFileRoute } from "@tanstack/react-router";

import { WorkspaceMain } from "@/components/workspace/WorkspaceMain";

export const Route = createFileRoute("/workspace/")({
  component: WorkspaceIndex,
});

function WorkspaceIndex() {
  return <WorkspaceMain />;
}
