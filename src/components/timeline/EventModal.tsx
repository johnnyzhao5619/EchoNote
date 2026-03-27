import { useEffect, useState } from "react";

import type {
  CreateEventRequest,
  TimelineEvent,
  UpdateEventRequest,
} from "@/lib/bindings";
import { datetimeLocalToMs, msToDatetimeLocal } from "@/lib/timeUtils";
import { useTimelineStore } from "@/store/timeline";

interface EventModalProps {
  event?: TimelineEvent;
  defaultStartMs?: number;
  onClose: () => void;
}

export function EventModal({ event, defaultStartMs, onClose }: EventModalProps) {
  const {
    createEvent,
    updateEvent,
    deleteEvent,
    loadLinkables,
    linkableRecordings,
    linkableDocuments,
  } = useTimelineStore();
  const isEdit = Boolean(event);
  const startMs = event?.start_at ?? defaultStartMs ?? Date.now();
  const endMs = event?.end_at ?? startMs + 3_600_000;

  const [title, setTitle] = useState(event?.title ?? "");
  const [description, setDescription] = useState(event?.description ?? "");
  const [startLocal, setStartLocal] = useState(msToDatetimeLocal(startMs));
  const [endLocal, setEndLocal] = useState(msToDatetimeLocal(endMs));
  const [tags, setTags] = useState<string[]>(event?.tags ?? []);
  const [tagInput, setTagInput] = useState("");
  const [recordingId, setRecordingId] = useState(event?.recording_id ?? "");
  const [documentId, setDocumentId] = useState(event?.document_id ?? "");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadLinkables();
  }, [loadLinkables]);

  function addTag() {
    const nextTag = tagInput.trim();
    if (!nextTag || tags.includes(nextTag)) {
      return;
    }

    setTags((current) => [...current, nextTag]);
    setTagInput("");
  }

  function removeTag(tag: string) {
    setTags((current) => current.filter((item) => item !== tag));
  }

  async function handleSave() {
    const trimmedTitle = title.trim();
    const start_at = datetimeLocalToMs(startLocal);
    const end_at = datetimeLocalToMs(endLocal);

    if (!trimmedTitle) {
      setError("Title is required.");
      return;
    }
    if (!Number.isFinite(start_at) || !Number.isFinite(end_at) || end_at <= start_at) {
      setError("End time must be after start time.");
      return;
    }

    setError(null);

    if (isEdit && event) {
      const req: UpdateEventRequest = {
        title: trimmedTitle,
        start_at,
        end_at,
        description: description.trim()
          ? { kind: "set", value: description.trim() }
          : { kind: "clear" },
        tags,
        recording_id: recordingId
          ? { kind: "set", value: recordingId }
          : { kind: "clear" },
        document_id: documentId
          ? { kind: "set", value: documentId }
          : { kind: "clear" },
      };

      await updateEvent(event.id, req);
    } else {
      const req: CreateEventRequest = {
        title: trimmedTitle,
        start_at,
        end_at,
        description: description.trim() || null,
        tags,
        recording_id: recordingId || null,
        document_id: documentId || null,
      };

      await createEvent(req);
    }

    onClose();
  }

  async function handleDelete() {
    if (!event) {
      return;
    }

    await deleteEvent(event.id);
    onClose();
  }

  return (
    <div className="rounded-lg border border-border bg-bg-panel p-4 shadow-sm">
      <div className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium" htmlFor="timeline-title">
            Title
          </label>
          <input
            id="timeline-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            className="w-full rounded-md border border-border bg-bg-muted px-3 py-2"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium" htmlFor="timeline-description">
            Description
          </label>
          <textarea
            id="timeline-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className="min-h-24 w-full rounded-md border border-border bg-bg-muted px-3 py-2"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium" htmlFor="timeline-start">
              Start
            </label>
            <input
              id="timeline-start"
              type="datetime-local"
              value={startLocal}
              onChange={(event) => setStartLocal(event.target.value)}
              className="w-full rounded-md border border-border bg-bg-muted px-3 py-2"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium" htmlFor="timeline-end">
              End
            </label>
            <input
              id="timeline-end"
              type="datetime-local"
              value={endLocal}
              onChange={(event) => setEndLocal(event.target.value)}
              className="w-full rounded-md border border-border bg-bg-muted px-3 py-2"
            />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium" htmlFor="timeline-tag-input">
            Tags
          </label>
          <div className="flex gap-2">
            <input
              id="timeline-tag-input"
              placeholder="Add tag"
              value={tagInput}
              onChange={(event) => setTagInput(event.target.value)}
              className="flex-1 rounded-md border border-border bg-bg-muted px-3 py-2"
            />
            <button
              type="button"
              onClick={addTag}
              className="rounded-md border border-border px-3 py-2"
            >
              Add tag
            </button>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {tags.map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => removeTag(tag)}
                className="rounded-full border border-border px-2 py-1 text-sm"
              >
                {tag}
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium" htmlFor="timeline-recording">
              Recording
            </label>
            <select
              id="timeline-recording"
              value={recordingId}
              onChange={(event) => setRecordingId(event.target.value)}
              className="w-full rounded-md border border-border bg-bg-muted px-3 py-2"
            >
              <option value="">None</option>
              {linkableRecordings.map((recording) => (
                <option key={recording.id} value={recording.id}>
                  {recording.title}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium" htmlFor="timeline-document">
              Document
            </label>
            <select
              id="timeline-document"
              value={documentId}
              onChange={(event) => setDocumentId(event.target.value)}
              className="w-full rounded-md border border-border bg-bg-muted px-3 py-2"
            >
              <option value="">None</option>
              {linkableDocuments.map((document) => (
                <option key={document.id} value={document.id}>
                  {document.title}
                </option>
              ))}
            </select>
          </div>
        </div>

        {error ? <p className="text-sm text-red-500">{error}</p> : null}

        <div className="flex justify-between gap-2">
          {isEdit ? (
            <button
              type="button"
              onClick={() => void handleDelete()}
              className="rounded-md border border-red-300 px-3 py-2 text-red-600"
            >
              Delete
            </button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-border px-3 py-2"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void handleSave()}
              className="rounded-md bg-blue-600 px-3 py-2 text-white"
            >
              {isEdit ? "Save" : "Create"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
