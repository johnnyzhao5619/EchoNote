// src/routes/workspace.tsx
// Layout route for /workspace — injects WorkspaceFileTree into SecondPanel.
// Content is rendered via <Outlet /> (workspace.index.tsx or workspace.$documentId.tsx).

import { createFileRoute, Outlet } from "@tanstack/react-router";
import { useEffect } from "react";
import { useShellStore } from "@/store/shell";
import { WorkspaceFileTree } from "@/components/workspace/WorkspaceFileTree";

export const Route = createFileRoute("/workspace")({
  component: WorkspaceLayout,
});

function WorkspaceLayout() {
  const setSecondPanelContent = useShellStore((s) => s.setSecondPanelContent);

  useEffect(() => {
    setSecondPanelContent(<WorkspaceFileTree />);
    return () => setSecondPanelContent(null);
  }, [setSecondPanelContent]);

  return <Outlet />;
}
