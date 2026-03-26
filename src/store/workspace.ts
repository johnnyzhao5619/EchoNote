// src/store/workspace.ts
import { create } from "zustand";
import { commands } from "@/lib/bindings";
import type { FolderNode, SystemFolderIds } from "@/lib/bindings";

interface WorkspaceStore {
  folderTree: FolderNode[];
  expandedFolderIds: Set<string>;
  systemFolderIds: SystemFolderIds | null;

  loadFolderTree: () => Promise<void>;
  toggleFolder: (folderId: string) => void;
  createFolder: (parentId: string | null, name: string) => Promise<void>;
  renameFolder: (folderId: string, name: string) => Promise<void>;
  deleteFolder: (folderId: string) => Promise<void>;
  moveDocument: (documentId: string, folderId: string) => Promise<void>;
  renameDocument: (documentId: string, title: string) => Promise<void>;
  deleteDocument: (documentId: string) => Promise<void>;
}

export const useWorkspaceStore = create<WorkspaceStore>((set, get) => ({
  folderTree: [],
  expandedFolderIds: new Set(),
  systemFolderIds: null,

  loadFolderTree: async () => {
    const [treeResult, sysResult] = await Promise.all([
      commands.listFoldersWithDocuments(),
      commands.ensureSystemFolders(),
    ]);
    if (treeResult.status === "ok") {
      set((s) => {
        // Auto-expand system folders on first load
        let expandedFolderIds = s.expandedFolderIds;
        if (expandedFolderIds.size === 0) {
          expandedFolderIds = new Set(
            treeResult.data.filter((n) => n.is_system).map((n) => n.id)
          );
        }
        return { folderTree: treeResult.data, expandedFolderIds };
      });
    }
    if (sysResult.status === "ok") {
      set({ systemFolderIds: sysResult.data });
    }
  },

  toggleFolder: (folderId) => {
    set((s) => {
      const next = new Set(s.expandedFolderIds);
      if (next.has(folderId)) next.delete(folderId);
      else next.add(folderId);
      return { expandedFolderIds: next };
    });
  },

  createFolder: async (parentId, name) => {
    const result = await commands.createFolder(parentId, name);
    if (result.status === "ok") {
      await get().loadFolderTree();
      if (parentId) {
        set((s) => {
          const next = new Set(s.expandedFolderIds);
          next.add(parentId);
          return { expandedFolderIds: next };
        });
      }
    }
  },

  renameFolder: async (folderId, name) => {
    const result = await commands.renameFolder(folderId, name);
    if (result.status === "ok") await get().loadFolderTree();
  },

  deleteFolder: async (folderId) => {
    const result = await commands.deleteFolder(folderId);
    if (result.status === "ok") await get().loadFolderTree();
  },

  moveDocument: async (documentId, folderId) => {
    const result = await commands.moveDocumentToFolder(documentId, folderId);
    if (result.status === "ok") await get().loadFolderTree();
  },

  renameDocument: async (documentId, title) => {
    const result = await commands.renameDocument(documentId, title);
    if (result.status === "ok") await get().loadFolderTree();
  },

  deleteDocument: async (documentId) => {
    const result = await commands.deleteDocument(documentId);
    if (result.status === "ok") await get().loadFolderTree();
  },
}));
