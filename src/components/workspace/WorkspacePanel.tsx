import { useEffect, useRef, useState } from "react";
import { Plus } from "lucide-react";
import { useNavigate } from "@tanstack/react-router";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { buildWorkspaceFolderRoute } from "@/lib/workspace-routes";
import { getFolderAncestorIds, getRootFolderIds } from "@/lib/workspace-tree";
import { useWorkspaceStore } from "@/store/workspace";

import { FolderTreeNode } from "./FolderTreeNode";
import { SearchBar } from "./SearchBar";

function mergeExpandedFolderIds(current: Set<string>, folderIds: string[]) {
  let changed = false;
  const next = new Set(current);
  for (const folderId of folderIds) {
    if (!next.has(folderId)) {
      next.add(folderId);
      changed = true;
    }
  }
  return changed ? next : current;
}

export function WorkspacePanel() {
  const navigate = useNavigate();
  const {
    folders,
    currentFolderId,
    loadFolderTree,
    createFolder,
    renameFolder,
    deleteFolder,
  } = useWorkspaceStore();

  const [dialog, setDialog] = useState<
    | { mode: "create"; parentId?: string }
    | { mode: "rename"; id: string; currentName: string }
    | null
  >(null);
  const [inputValue, setInputValue] = useState("");
  const [expandedFolderIds, setExpandedFolderIds] = useState<Set<string>>(() => new Set());
  const initializedRootsRef = useRef(false);

  useEffect(() => {
    void loadFolderTree();
  }, [loadFolderTree]);

  useEffect(() => {
    if (initializedRootsRef.current || folders.length === 0) {
      return;
    }

    initializedRootsRef.current = true;
    setExpandedFolderIds((current) => {
      return mergeExpandedFolderIds(current, getRootFolderIds(folders));
    });
  }, [folders]);

  useEffect(() => {
    if (!currentFolderId) {
      return;
    }

    setExpandedFolderIds((current) => {
      return mergeExpandedFolderIds(current, getFolderAncestorIds(folders, currentFolderId));
    });
  }, [folders, currentFolderId]);

  const handleConfirm = async () => {
    if (!dialog || !inputValue.trim()) {
      return;
    }

    if (dialog.mode === "create") {
      await createFolder(inputValue.trim(), dialog.parentId);
    } else {
      await renameFolder(dialog.id, inputValue.trim());
    }

    setDialog(null);
    setInputValue("");
  };

  return (
    <div className="flex h-full flex-col text-text-primary">
      <div className="border-b border-border p-2">
        <SearchBar />
      </div>

      <ul className="flex-1 overflow-y-auto py-1" role="tree" aria-label="Workspace folders">
        {folders.map((node) => (
          <FolderTreeNode
            key={node.id}
            node={node}
            depth={0}
            selectedId={currentFolderId}
            expandedFolderIds={expandedFolderIds}
            onSelect={(id) => {
              void navigate(buildWorkspaceFolderRoute(id));
            }}
            onToggleExpand={(id) => {
              setExpandedFolderIds((current) => {
                const next = new Set(current);
                if (next.has(id)) {
                  next.delete(id);
                } else {
                  next.add(id);
                }
                return next;
              });
            }}
            onCreateChild={(parentId) => {
              setDialog({ mode: "create", parentId });
              setInputValue("");
            }}
            onRename={(id, currentName) => {
              setDialog({ mode: "rename", id, currentName });
              setInputValue(currentName);
            }}
            onDelete={(id) => void deleteFolder(id)}
          />
        ))}
      </ul>

      <div className="border-t border-border p-2">
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-2 text-text-secondary hover:text-text-primary"
          onClick={() => {
            setDialog({ mode: "create" });
            setInputValue("");
          }}
        >
          <Plus size={14} /> 新建文件夹
        </Button>
      </div>

      <Dialog open={!!dialog} onOpenChange={(open) => !open && setDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {dialog?.mode === "create" ? "新建文件夹" : "重命名文件夹"}
            </DialogTitle>
          </DialogHeader>
          <Input
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                void handleConfirm();
              }
            }}
            placeholder="文件夹名称"
            autoFocus
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDialog(null)}>
              取消
            </Button>
            <Button onClick={() => void handleConfirm()}>确认</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
