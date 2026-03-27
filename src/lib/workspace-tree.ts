import type { FolderNode } from "@/lib/bindings";

function findFolderPath(folders: FolderNode[], targetId: string, trail: string[] = []): string[] | null {
  for (const folder of folders) {
    const nextTrail = [...trail, folder.id];
    if (folder.id === targetId) {
      return nextTrail;
    }

    const childPath = findFolderPath(folder.children, targetId, nextTrail);
    if (childPath) {
      return childPath;
    }
  }

  return null;
}

export function getFolderAncestorIds(folders: FolderNode[], targetId: string): string[] {
  const path = findFolderPath(folders, targetId);
  return path ? path.slice(0, -1) : [];
}

export function getRootFolderIds(folders: FolderNode[]): string[] {
  return folders.map((folder) => folder.id);
}
