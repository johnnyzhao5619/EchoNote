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

export function getVisibleFolderIds(
  folders: FolderNode[],
  expandedFolderIds: ReadonlySet<string>,
): string[] {
  const visibleIds: string[] = [];

  const walk = (nodes: FolderNode[]) => {
    for (const node of nodes) {
      visibleIds.push(node.id);
      if (node.children.length > 0 && expandedFolderIds.has(node.id)) {
        walk(node.children);
      }
    }
  };

  walk(folders);
  return visibleIds;
}

export function getNearestVisibleFolderId(
  folders: FolderNode[],
  targetId: string,
  expandedFolderIds: ReadonlySet<string>,
): string | null {
  const path = findFolderPath(folders, targetId);
  if (!path) {
    return null;
  }

  let nearestVisibleId = path[0] ?? null;
  for (let index = 1; index < path.length; index += 1) {
    if (!expandedFolderIds.has(path[index - 1])) {
      break;
    }
    nearestVisibleId = path[index];
  }

  return nearestVisibleId;
}
