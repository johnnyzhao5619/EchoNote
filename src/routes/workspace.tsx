import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState, useCallback, useRef } from "react";
import { commands } from "@/lib/bindings";
import type { RecordingItem } from "@/lib/bindings";
import { formatDuration, formatDate } from "@/lib/format";
import { FileText, Mic, Clock } from "lucide-react";

export const Route = createFileRoute("/workspace")({
  component: WorkspacePage,
});

function RecordingCard({ item, onClick }: { item: RecordingItem; onClick: () => void }) {
  return (
    <div
      className="flex flex-col gap-2 p-4 rounded-lg border border-border-default bg-bg-secondary hover:bg-bg-tertiary transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Mic className="w-4 h-4 shrink-0 text-accent-primary" />
          <span className="text-sm font-medium text-text-primary truncate">
            {item.title}
          </span>
        </div>
        <div className="flex items-center gap-1 shrink-0 text-xs text-text-muted">
          <Clock className="w-3 h-3" />
          {formatDuration(item.duration_ms)}
        </div>
      </div>

      {item.transcript && (
        <div className="flex items-start gap-2">
          <FileText className="w-3.5 h-3.5 shrink-0 mt-0.5 text-text-muted" />
          <p className="text-xs text-text-secondary leading-relaxed line-clamp-2">
            {item.transcript}
          </p>
        </div>
      )}

      <div className="text-xs text-text-muted">{formatDate(item.created_at)}</div>
    </div>
  );
}

function WorkspacePage() {
  const navigate = useNavigate();
  const [recordings, setRecordings] = useState<RecordingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const prevCountRef = useRef(0);

  const load = useCallback(async () => {
    const result = await commands.listRecordings();
    if (result.status === "ok") {
      setRecordings(result.data);
      prevCountRef.current = result.data.length;
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Poll for new recordings (replaces unreliable Tauri event listener)
  useEffect(() => {
    const timer = setInterval(async () => {
      const result = await commands.listRecordings();
      if (result.status === "ok" && result.data.length !== prevCountRef.current) {
        setRecordings(result.data);
        prevCountRef.current = result.data.length;
      }
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  const handleCardClick = (item: RecordingItem) => {
    if (item.document_id) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (navigate as any)({ to: "/workspace/$documentId", params: { documentId: item.document_id } });
    }
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-text-muted text-sm">
        Loading...
      </div>
    );
  }

  if (recordings.length === 0) {
    return (
      <div className="flex flex-col h-full items-center justify-center gap-3 text-text-muted">
        <Mic className="w-10 h-10 opacity-30" />
        <p className="text-sm">No recordings yet. Start recording to see them here.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto p-4 gap-3">
      <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wide shrink-0">
        Recordings ({recordings.length})
      </h2>
      {recordings.map((item) => (
        <RecordingCard
          key={item.id}
          item={item}
          onClick={() => handleCardClick(item)}
        />
      ))}
    </div>
  );
}
