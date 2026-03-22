import { useEffect } from "react";
import { createFileRoute, Outlet } from "@tanstack/react-router";
import { SettingsPanel } from "@/components/settings/SettingsPanel";
import { useShellStore } from "@/store/shell";

export const Route = createFileRoute("/settings")({
  component: SettingsLayout,
});

function SettingsLayout() {
  const setSecondPanelContent = useShellStore((s) => s.setSecondPanelContent);

  useEffect(() => {
    setSecondPanelContent(<SettingsPanel />);
    return () => setSecondPanelContent(null);
  }, [setSecondPanelContent]);

  return <Outlet />;
}
