import { useEffect } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { TranscriptionMain } from "@/components/transcription/TranscriptionMain";
import { TranscriptionPanel } from "@/components/transcription/TranscriptionPanel";
import { useShellStore } from "@/store/shell";

export const Route = createFileRoute("/transcription")({
  component: TranscriptionPage,
});

function TranscriptionPage() {
  const setSecondPanelContent = useShellStore((state) => state.setSecondPanelContent);

  useEffect(() => {
    setSecondPanelContent(<TranscriptionPanel />);
    return () => setSecondPanelContent(null);
  }, [setSecondPanelContent]);

  return (
    <div className="flex h-full flex-col">
      <TranscriptionMain />
    </div>
  );
}
