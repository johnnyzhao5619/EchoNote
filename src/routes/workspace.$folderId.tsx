import { createFileRoute } from "@tanstack/react-router";

import { WorkspaceMain } from "@/components/workspace/WorkspaceMain";

export const Route = createFileRoute("/workspace/$folderId")({
  component: FolderPage,
});

function FolderPage() {
  return <WorkspaceMain />;
}
