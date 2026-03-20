import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/transcription")({
  component: TranscriptionPage,
});

function TranscriptionPage() {
  return (
    <div className="flex h-full items-center justify-center text-text-muted">
      <p>Transcription — Coming in M2</p>
    </div>
  );
}
