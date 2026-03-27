import { createFileRoute } from "@tanstack/react-router";

import { WorkspaceMain } from "@/components/workspace/WorkspaceMain";

export const Route = createFileRoute("/workspace/$documentId")({
  component: DocumentPage,
});

function DocumentPage() {
  return <WorkspaceMain />;
}
