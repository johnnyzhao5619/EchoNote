import { createFileRoute } from "@tanstack/react-router";

import { WorkspaceMain } from "@/components/workspace/WorkspaceMain";

export const Route = createFileRoute("/workspace/$folderId/$docId")({
  component: FolderDocumentPage,
});

function FolderDocumentPage() {
  return <WorkspaceMain />;
}
