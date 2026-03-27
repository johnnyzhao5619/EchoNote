import type { TimelineEvent } from "@/lib/bindings";
import { formatEventTime } from "@/lib/timeUtils";

const TAG_COLORS = ["bg-blue-500", "bg-emerald-500", "bg-amber-500", "bg-rose-500"] as const;

function tagColor(tags: string[]) {
  if (tags.length === 0) {
    return TAG_COLORS[0];
  }

  const hash = tags[0].split("").reduce((sum, ch) => sum + ch.charCodeAt(0), 0);
  return TAG_COLORS[hash % TAG_COLORS.length];
}

interface EventCardProps {
  event: TimelineEvent;
  compact?: boolean;
  onClick?: (event: TimelineEvent) => void;
}

export function EventCard({ event, compact = false, onClick }: EventCardProps) {
  return (
    <button
      type="button"
      onClick={() => onClick?.(event)}
      aria-label={event.title}
      className={`w-full rounded-md px-3 py-2 text-left text-white ${tagColor(event.tags)}`}
    >
      <span className="block truncate font-medium">{event.title}</span>
      {!compact ? (
        <span className="block text-xs opacity-80">
          {formatEventTime(event.start_at)} - {formatEventTime(event.end_at)}
        </span>
      ) : null}
      {!compact ? (
        <div className="mt-1 flex flex-wrap gap-1">
          {event.tags.map((tag) => (
            <span key={tag} className="rounded bg-white/20 px-1.5 py-0.5 text-[10px]">
              {tag}
            </span>
          ))}
        </div>
      ) : null}
      {!compact && (event.recording_id || event.document_id) ? (
        <div className="mt-1 flex gap-2 text-[10px] opacity-80">
          {event.recording_id ? <span aria-label="Linked recording">REC</span> : null}
          {event.document_id ? <span aria-label="Linked document">DOC</span> : null}
        </div>
      ) : null}
    </button>
  );
}
