import { create } from "zustand";

import { commands } from "@/lib/bindings";
import type {
  DocumentDetail,
  DocumentSummary,
  FolderNode,
  SearchResult,
} from "@/lib/bindings";

interface WorkspaceState {
  folders: FolderNode[];
  currentFolderId: string | null;
  documents: DocumentSummary[];
  currentDoc: DocumentDetail | null;
  searchQuery: string;
  searchResults: SearchResult[];
  isSearching: boolean;

  loadFolderTree: () => Promise<void>;
  selectFolder: (id: string | null) => Promise<void>;
  createFolder: (name: string, parentId?: string) => Promise<void>;
  renameFolder: (id: string, name: string) => Promise<void>;
  deleteFolder: (id: string) => Promise<void>;

  openDocument: (id: string) => Promise<void>;
  createDocument: (title: string, folderId?: string, content?: string) => Promise<string>;
  updateDocument: (id: string, opts: { title?: string; role?: string; content?: string }) => Promise<void>;
  deleteDocument: (id: string) => Promise<void>;

  setSearchQuery: (query: string) => void;
  search: (query: string) => Promise<void>;
  clearSearch: () => void;

  importFile: (filePath: string, folderId?: string) => Promise<DocumentSummary>;
  exportDocument: (id: string, format: "md" | "txt" | "srt" | "vtt", targetPath: string) => Promise<void>;
}

function unwrapResult<T>(result: { status: "ok"; data: T } | { status: "error"; error: unknown }): T {
  if (result.status === "error") {
    throw result.error;
  }
  return result.data;
}

let latestSearchRequestId = 0;

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  folders: [],
  currentFolderId: null,
  documents: [],
  currentDoc: null,
  searchQuery: "",
  searchResults: [],
  isSearching: false,

  loadFolderTree: async () => {
    const folders = unwrapResult(await commands.listFolderTree());
    set({ folders });
  },

  selectFolder: async (id) => {
    set({ currentFolderId: id, currentDoc: null });
    const documents = unwrapResult(await commands.listDocumentsInFolder(id));
    set({ documents });
  },

  createFolder: async (name, parentId) => {
    unwrapResult(await commands.createFolder(name, parentId ?? null));
    await get().loadFolderTree();
  },

  renameFolder: async (id, name) => {
    unwrapResult(await commands.renameFolder(id, name));
    await get().loadFolderTree();
  },

  deleteFolder: async (id) => {
    unwrapResult(await commands.deleteFolder(id));
    await get().loadFolderTree();
    if (get().currentFolderId === id) {
      set({ currentFolderId: null, documents: [], currentDoc: null });
    }
  },

  openDocument: async (id) => {
    const currentDoc = unwrapResult(await commands.getDocument(id));
    set({ currentDoc });
  },

  createDocument: async (title, folderId, content = "") => {
    const summary = unwrapResult(await commands.createDocument(title, folderId ?? null, content));
    set((state) => ({ documents: [summary, ...state.documents] }));
    return summary.id;
  },

  updateDocument: async (id, { title, role, content }) => {
    unwrapResult(await commands.updateDocument(id, title ?? null, role ?? null, content ?? null));
    if (get().currentDoc?.id === id) {
      await get().openDocument(id);
    }
  },

  deleteDocument: async (id) => {
    unwrapResult(await commands.deleteDocument(id));
    set((state) => ({
      documents: state.documents.filter((doc) => doc.id !== id),
      currentDoc: state.currentDoc?.id === id ? null : state.currentDoc,
    }));
  },

  setSearchQuery: (searchQuery) => set({ searchQuery }),

  search: async (query) => {
    const normalizedQuery = query.trim();
    if (!normalizedQuery) {
      latestSearchRequestId += 1;
      set({ searchResults: [], isSearching: false });
      return;
    }

    const requestId = ++latestSearchRequestId;
    set({ isSearching: true });
    try {
      const searchResults = unwrapResult(await commands.searchWorkspace(normalizedQuery));
      if (requestId !== latestSearchRequestId) {
        return;
      }
      set({ searchResults });
    } finally {
      if (requestId === latestSearchRequestId) {
        set({ isSearching: false });
      }
    }
  },

  clearSearch: () => {
    latestSearchRequestId += 1;
    set({ searchQuery: "", searchResults: [], isSearching: false });
  },

  importFile: async (filePath, folderId) => {
    const summary = unwrapResult(await commands.importFileToWorkspace(filePath, folderId ?? null));
    set((state) => ({
      documents: [summary, ...state.documents.filter((doc) => doc.id !== summary.id)],
    }));
    return summary;
  },

  exportDocument: async (id, format, targetPath) => {
    unwrapResult(await commands.exportDocument(id, format, targetPath));
  },
}));
