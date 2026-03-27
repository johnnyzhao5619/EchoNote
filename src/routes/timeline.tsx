import { useEffect } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { TimelineMain } from "@/components/timeline/TimelineMain";
import { TimelinePanel } from "@/components/timeline/TimelinePanel";
import { useShellStore } from "@/store/shell";

export const Route = createFileRoute("/timeline")({
  component: TimelinePage,
});

function TimelinePage() {
  const setSecondPanelContent = useShellStore((state) => state.setSecondPanelContent);

  useEffect(() => {
    setSecondPanelContent(<TimelinePanel />);
    return () => setSecondPanelContent(null);
  }, [setSecondPanelContent]);

  return (
    <div className="flex h-full flex-col p-4">
      <TimelineMain />
    </div>
  );
}
