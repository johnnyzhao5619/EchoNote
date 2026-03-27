import { create } from "zustand";

import { commands } from "@/lib/bindings";
import type {
  CreateEventRequest,
  DocumentSummary,
  RecordingItem,
  TimelineEvent,
  UpdateEventRequest,
} from "@/lib/bindings";
import { rangeForView, shiftAnchor, type TimelineViewMode } from "@/lib/timeUtils";

function unwrapResult<T>(result: { status: "ok"; data: T } | { status: "error"; error: unknown }): T {
  if (result.status === "error") {
    throw result.error;
  }
  return result.data;
}

interface TimelineState {
  events: TimelineEvent[];
  anchorDate: Date;
  viewMode: TimelineViewMode;
  viewRange: { start: Date; end: Date };
  selectedEventId: string | null;
  linkableRecordings: RecordingItem[];
  linkableDocuments: DocumentSummary[];
  searchQuery: string;
  isLoading: boolean;
  error: string | null;
  fetchRange: (start: Date, end: Date) => Promise<void>;
  search: (query: string) => Promise<void>;
  loadLinkables: () => Promise<void>;
  createEvent: (req: CreateEventRequest) => Promise<TimelineEvent>;
  updateEvent: (id: string, req: UpdateEventRequest) => Promise<TimelineEvent>;
  deleteEvent: (id: string) => Promise<void>;
  setViewMode: (mode: TimelineViewMode) => Promise<void>;
  navigatePrev: () => Promise<void>;
  navigateNext: () => Promise<void>;
  navigateToday: () => Promise<void>;
  selectEvent: (id: string | null) => void;
}

const initialAnchor = new Date();
const initialRange = rangeForView(initialAnchor, "month");

export const useTimelineStore = create<TimelineState>((set, get) => ({
  events: [],
  anchorDate: initialAnchor,
  viewMode: "month",
  viewRange: {
    start: new Date(initialRange.start),
    end: new Date(initialRange.end),
  },
  selectedEventId: null,
  linkableRecordings: [],
  linkableDocuments: [],
  searchQuery: "",
  isLoading: false,
  error: null,

  fetchRange: async (start, end) => {
    set({ isLoading: true, error: null });
    try {
      const events = unwrapResult(await commands.listTimelineEvents(start.getTime(), end.getTime()))
        .slice()
        .sort((a, b) => a.start_at - b.start_at || a.end_at - b.end_at);
      set({
        events,
        viewRange: { start, end },
        isLoading: false,
      });
    } catch (error) {
      set({ isLoading: false, error: String(error) });
    }
  },

  search: async (query) => {
    const trimmed = query.trim();
    set({ searchQuery: query, error: null });
    if (!trimmed) {
      const { viewRange } = get();
      await get().fetchRange(viewRange.start, viewRange.end);
      return;
    }

    set({ isLoading: true });
    try {
      const events = unwrapResult(await commands.searchTimelineEvents(trimmed))
        .slice()
        .sort((a, b) => a.start_at - b.start_at || a.end_at - b.end_at);
      set({ events, isLoading: false });
    } catch (error) {
      set({ isLoading: false, error: String(error) });
    }
  },

  loadLinkables: async () => {
    const [recordings, documents] = await Promise.all([
      commands.listRecordings(),
      commands.listAllDocuments(),
    ]);
    set({
      linkableRecordings: unwrapResult(recordings),
      linkableDocuments: unwrapResult(documents),
    });
  },

  createEvent: async (req) => {
    const event = unwrapResult(await commands.createTimelineEvent(req));
    set((state) => ({
      events: [...state.events, event].sort(
        (a, b) => a.start_at - b.start_at || a.end_at - b.end_at,
      ),
    }));
    return event;
  },

  updateEvent: async (id, req) => {
    const updated = unwrapResult(await commands.updateTimelineEvent(id, req));
    set((state) => ({
      events: state.events
        .map((event) => (event.id === id ? updated : event))
        .sort((a, b) => a.start_at - b.start_at || a.end_at - b.end_at),
    }));
    return updated;
  },

  deleteEvent: async (id) => {
    unwrapResult(await commands.deleteTimelineEvent(id));
    set((state) => ({
      events: state.events.filter((event) => event.id !== id),
      selectedEventId: state.selectedEventId === id ? null : state.selectedEventId,
    }));
  },

  setViewMode: async (mode) => {
    const { anchorDate } = get();
    const nextRange = rangeForView(anchorDate, mode);
    set({
      viewMode: mode,
      viewRange: {
        start: new Date(nextRange.start),
        end: new Date(nextRange.end),
      },
    });
    await get().fetchRange(new Date(nextRange.start), new Date(nextRange.end));
  },

  navigatePrev: async () => {
    const { anchorDate, viewMode } = get();
    const nextAnchor = shiftAnchor(anchorDate, viewMode, -1);
    const nextRange = rangeForView(nextAnchor, viewMode);
    set({ anchorDate: nextAnchor });
    await get().fetchRange(new Date(nextRange.start), new Date(nextRange.end));
  },

  navigateNext: async () => {
    const { anchorDate, viewMode } = get();
    const nextAnchor = shiftAnchor(anchorDate, viewMode, 1);
    const nextRange = rangeForView(nextAnchor, viewMode);
    set({ anchorDate: nextAnchor });
    await get().fetchRange(new Date(nextRange.start), new Date(nextRange.end));
  },

  navigateToday: async () => {
    const nextAnchor = new Date();
    const { viewMode } = get();
    const nextRange = rangeForView(nextAnchor, viewMode);
    set({ anchorDate: nextAnchor });
    await get().fetchRange(new Date(nextRange.start), new Date(nextRange.end));
  },

  selectEvent: (id) => set({ selectedEventId: id }),
}));
