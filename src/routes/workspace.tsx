import { createFileRoute, Outlet } from "@tanstack/react-router";
import { useEffect } from "react";

import { WorkspacePanel } from "@/components/workspace/WorkspacePanel";
import { useShellStore } from "@/store/shell";

export const Route = createFileRoute("/workspace")({
  component: WorkspaceLayout,
});

function WorkspaceLayout() {
  const setSecondPanelContent = useShellStore((state) => state.setSecondPanelContent);

  useEffect(() => {
    setSecondPanelContent(<WorkspacePanel />);
    return () => setSecondPanelContent(null);
  }, [setSecondPanelContent]);

  return <Outlet />;
}
