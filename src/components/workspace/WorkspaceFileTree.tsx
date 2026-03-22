// src/components/workspace/WorkspaceFileTree.tsx
// Obsidian-style folder tree sidebar.
// Folders are expandable/collapsible; documents shown inside their folder.
// System folders (inbox, batch_task) appear first; user folders after a divider.
// Right-click context menus provide folder/document CRUD.

import { useEffect, useState, useCallback } from "react";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import {
  ChevronDown,
  ChevronRight,
  FolderOpen,
  Folder,
  FileText,
  Inbox,
  LayoutList,
  Plus,
  Pencil,
  Trash2,
  FolderInput,
} from "lucide-react";
import * as ContextMenu from "@radix-ui/react-context-menu";
import { useWorkspaceStore } from "@/store/workspace";
import type { FolderNode, DocumentSummary } from "@/lib/bindings";

// ── helpers ─────────────────────────────────────────────────────────────────

function FolderIcon({
  kind,
  open,
  className,
}: {
  kind: string;
  open: boolean;
  className?: string;
}) {
  if (kind === "inbox") return <Inbox className={className ?? "w-3.5 h-3.5"} />;
  if (kind === "batch_task")
    return <LayoutList className={className ?? "w-3.5 h-3.5"} />;
  return open ? (
    <FolderOpen className={className ?? "w-3.5 h-3.5"} />
  ) : (
    <Folder className={className ?? "w-3.5 h-3.5"} />
  );
}

// ── DocumentRow ─────────────────────────────────────────────────────────────

function DocumentRow({
  doc,
  isActive,
  onSelect,
  folderId,
  allFolders,
}: {
  doc: DocumentSummary;
  isActive: boolean;
  onSelect: () => void;
  folderId: string;
  allFolders: FolderNode[];
}) {
  const { renameDocument, deleteDocument, moveDocument } = useWorkspaceStore();
  const [renaming, setRenaming] = useState(false);
  const [renameVal, setRenameVal] = useState(doc.title);
  const submitRename = async () => {
    const trimmed = renameVal.trim();
    if (trimmed && trimmed !== doc.title) await renameDocument(doc.id, trimmed);
    setRenaming(false);
  };

  // flatten folder list for "move to" menu (excluding current)
  const targets = flattenFolders(allFolders).filter((f) => f.id !== folderId);

  return (
    <ContextMenu.Root>
      <ContextMenu.Trigger asChild>
        <div
          role="button"
          tabIndex={0}
          onClick={onSelect}
          onKeyDown={(e) => e.key === "Enter" && onSelect()}
          className={[
            "flex items-center gap-1.5 px-2 py-1 rounded cursor-pointer select-none text-xs min-w-0 ml-4",
            isActive
              ? "bg-accent-primary/15 text-accent-primary"
              : "text-text-secondary hover:bg-bg-tertiary hover:text-text-primary",
          ].join(" ")}
        >
          {renaming ? (
            <input
              autoFocus
              value={renameVal}
              onChange={(e) => setRenameVal(e.target.value)}
              onBlur={submitRename}
              onKeyDown={(e) => {
                if (e.key === "Enter") submitRename();
                if (e.key === "Escape") setRenaming(false);
                e.stopPropagation();
              }}
              onClick={(e) => e.stopPropagation()}
              className="flex-1 bg-bg-secondary border border-accent-primary rounded px-1 outline-none text-xs text-text-primary"
            />
          ) : (
            <>
              <FileText className="w-3 h-3 shrink-0" />
              <span className="truncate flex-1">{doc.title}</span>
            </>
          )}
        </div>
      </ContextMenu.Trigger>

      <ContextMenu.Portal>
        <ContextMenu.Content className="z-50 min-w-[160px] bg-bg-secondary border border-border-default rounded-md shadow-lg py-1 text-xs text-text-primary">
          <ContextMenu.Item
            onSelect={() => {
              setRenameVal(doc.title);
              setRenaming(true);
            }}
            className="flex items-center gap-2 px-3 py-1.5 hover:bg-bg-tertiary cursor-pointer outline-none"
          >
            <Pencil className="w-3 h-3" /> 重命名
          </ContextMenu.Item>

          {targets.length > 0 && (
            <ContextMenu.Sub>
              <ContextMenu.SubTrigger className="flex items-center gap-2 px-3 py-1.5 hover:bg-bg-tertiary cursor-pointer outline-none">
                <FolderInput className="w-3 h-3" /> 移动到
                <ChevronRight className="w-3 h-3 ml-auto" />
              </ContextMenu.SubTrigger>
              <ContextMenu.Portal>
                <ContextMenu.SubContent className="z-50 min-w-[140px] bg-bg-secondary border border-border-default rounded-md shadow-lg py-1 text-xs text-text-primary">
                  {targets.map((t) => (
                    <ContextMenu.Item
                      key={t.id}
                      onSelect={() => moveDocument(doc.id, t.id)}
                      className="flex items-center gap-2 px-3 py-1.5 hover:bg-bg-tertiary cursor-pointer outline-none truncate"
                    >
                      <Folder className="w-3 h-3 shrink-0" />
                      <span className="truncate">{t.name}</span>
                    </ContextMenu.Item>
                  ))}
                </ContextMenu.SubContent>
              </ContextMenu.Portal>
            </ContextMenu.Sub>
          )}

          <ContextMenu.Separator className="my-1 border-t border-border-default" />
          <ContextMenu.Item
            onSelect={() => deleteDocument(doc.id)}
            className="flex items-center gap-2 px-3 py-1.5 hover:bg-bg-tertiary cursor-pointer outline-none text-red-400"
          >
            <Trash2 className="w-3 h-3" /> 删除
          </ContextMenu.Item>
        </ContextMenu.Content>
      </ContextMenu.Portal>
    </ContextMenu.Root>
  );
}

// ── FolderItem ───────────────────────────────────────────────────────────────

function FolderItem({
  node,
  currentDocumentId,
  onSelectDoc,
  allFolders,
}: {
  node: FolderNode;
  currentDocumentId: string | null;
  onSelectDoc: (docId: string) => void;
  allFolders: FolderNode[];
}) {
  const { expandedFolderIds, toggleFolder, createFolder, renameFolder, deleteFolder } =
    useWorkspaceStore();

  const isOpen = expandedFolderIds.has(node.id);

  const [renaming, setRenaming] = useState(false);
  const [renameVal, setRenameVal] = useState(node.name);
  const [creating, setCreating] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");

  const submitRename = async () => {
    const trimmed = renameVal.trim();
    if (trimmed && trimmed !== node.name) await renameFolder(node.id, trimmed);
    setRenaming(false);
  };

  const submitCreate = async () => {
    const trimmed = newFolderName.trim();
    if (trimmed) await createFolder(node.id, trimmed);
    setCreating(false);
    setNewFolderName("");
  };

  return (
    <div>
      {/* Folder header row */}
      <ContextMenu.Root>
        <ContextMenu.Trigger asChild>
          <div
            role="button"
            tabIndex={0}
            onClick={() => toggleFolder(node.id)}
            onKeyDown={(e) => e.key === "Enter" && toggleFolder(node.id)}
            className="flex items-center gap-1 px-2 py-1 rounded cursor-pointer select-none hover:bg-bg-tertiary group"
          >
            <span className="text-text-muted w-3 shrink-0">
              {isOpen ? (
                <ChevronDown className="w-3 h-3" />
              ) : (
                <ChevronRight className="w-3 h-3" />
              )}
            </span>
            <FolderIcon
              kind={node.folder_kind}
              open={isOpen}
              className="w-3.5 h-3.5 shrink-0 text-text-secondary"
            />
            {renaming ? (
              <input
                autoFocus
                value={renameVal}
                onChange={(e) => setRenameVal(e.target.value)}
                onBlur={submitRename}
                onKeyDown={(e) => {
                  if (e.key === "Enter") submitRename();
                  if (e.key === "Escape") setRenaming(false);
                  e.stopPropagation();
                }}
                onClick={(e) => e.stopPropagation()}
                className="flex-1 bg-bg-secondary border border-accent-primary rounded px-1 outline-none text-xs text-text-primary"
              />
            ) : (
              <span className="truncate flex-1 text-xs font-medium text-text-primary">
                {node.name}
              </span>
            )}
            {/* Quick-add child folder button */}
            {!node.is_system && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setCreating(true);
                  if (!isOpen) toggleFolder(node.id);
                }}
                className="hidden group-hover:flex items-center justify-center w-4 h-4 rounded hover:bg-bg-primary text-text-muted shrink-0"
                title="新建子文件夹"
              >
                <Plus className="w-3 h-3" />
              </button>
            )}
          </div>
        </ContextMenu.Trigger>

        <ContextMenu.Portal>
          <ContextMenu.Content className="z-50 min-w-[160px] bg-bg-secondary border border-border-default rounded-md shadow-lg py-1 text-xs text-text-primary">
            <ContextMenu.Item
              onSelect={() => {
                setCreating(true);
                if (!isOpen) toggleFolder(node.id);
              }}
              className="flex items-center gap-2 px-3 py-1.5 hover:bg-bg-tertiary cursor-pointer outline-none"
            >
              <Plus className="w-3 h-3" /> 新建子文件夹
            </ContextMenu.Item>

            {!node.is_system && (
              <>
                <ContextMenu.Item
                  onSelect={() => {
                    setRenameVal(node.name);
                    setRenaming(true);
                  }}
                  className="flex items-center gap-2 px-3 py-1.5 hover:bg-bg-tertiary cursor-pointer outline-none"
                >
                  <Pencil className="w-3 h-3" /> 重命名
                </ContextMenu.Item>
                <ContextMenu.Separator className="my-1 border-t border-border-default" />
                <ContextMenu.Item
                  onSelect={() => deleteFolder(node.id)}
                  className="flex items-center gap-2 px-3 py-1.5 hover:bg-bg-tertiary cursor-pointer outline-none text-red-400"
                >
                  <Trash2 className="w-3 h-3" /> 删除文件夹
                </ContextMenu.Item>
              </>
            )}
          </ContextMenu.Content>
        </ContextMenu.Portal>
      </ContextMenu.Root>

      {/* Expanded contents */}
      {isOpen && (
        <div className="ml-3">
          {/* New folder inline input */}
          {creating && (
            <div className="flex items-center gap-1.5 px-2 py-1 ml-4">
              <Folder className="w-3 h-3 shrink-0 text-text-muted" />
              <input
                autoFocus
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                onBlur={submitCreate}
                onKeyDown={(e) => {
                  if (e.key === "Enter") submitCreate();
                  if (e.key === "Escape") {
                    setCreating(false);
                    setNewFolderName("");
                  }
                }}
                placeholder="文件夹名称"
                className="flex-1 bg-bg-secondary border border-accent-primary rounded px-1 outline-none text-xs text-text-primary placeholder:text-text-muted"
              />
            </div>
          )}

          {/* Subfolders */}
          {node.children.map((child) => (
            <FolderItem
              key={child.id}
              node={child}
              currentDocumentId={currentDocumentId}
              onSelectDoc={onSelectDoc}
              allFolders={allFolders}
            />
          ))}

          {/* Documents */}
          {node.documents.map((doc) => (
            <DocumentRow
              key={doc.id}
              doc={doc}
              isActive={doc.id === currentDocumentId}
              onSelect={() => onSelectDoc(doc.id)}
              folderId={node.id}
              allFolders={allFolders}
            />
          ))}

          {node.children.length === 0 && node.documents.length === 0 && !creating && (
            <p className="ml-4 py-1 text-xs text-text-muted italic">空文件夹</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── flat folder list helper ───────────────────────────────────────────────────

function flattenFolders(nodes: FolderNode[]): { id: string; name: string }[] {
  const result: { id: string; name: string }[] = [];
  function walk(ns: FolderNode[]) {
    for (const n of ns) {
      result.push({ id: n.id, name: n.name });
      walk(n.children);
    }
  }
  walk(nodes);
  return result;
}

// ── WorkspaceFileTree (main export) ─────────────────────────────────────────

export function WorkspaceFileTree() {
  const navigate = useNavigate();
  const routerState = useRouterState();
  const { folderTree, loadFolderTree, createFolder } = useWorkspaceStore();

  const [creatingRoot, setCreatingRoot] = useState(false);
  const [rootFolderName, setRootFolderName] = useState("");

  const currentDocumentId: string | null =
    routerState.matches
      .map((m) => (m.params as Record<string, string>).documentId)
      .find(Boolean) ?? null;

  const handleSelectDoc = useCallback(
    (docId: string) => {
      navigate({ to: "/workspace/$documentId", params: { documentId: docId } });
    },
    [navigate]
  );

  // Initial load + poll (tauri events unreliable on macOS dev)
  useEffect(() => {
    loadFolderTree();
    const timer = setInterval(loadFolderTree, 5000);
    return () => clearInterval(timer);
  }, [loadFolderTree]);

  const systemFolders = folderTree.filter((n) => n.is_system);
  const userFolders = folderTree.filter((n) => !n.is_system);

  const submitRootCreate = async () => {
    const trimmed = rootFolderName.trim();
    if (trimmed) await createFolder(null, trimmed);
    setCreatingRoot(false);
    setRootFolderName("");
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="shrink-0 px-3 py-2 flex items-center justify-between border-b border-border-default">
        <span className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
          工作区
        </span>
        <button
          onClick={() => setCreatingRoot(true)}
          className="flex items-center justify-center w-5 h-5 rounded hover:bg-bg-tertiary text-text-muted"
          title="新建文件夹"
        >
          <Plus className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-y-auto py-1 px-1">
        {/* System folders */}
        {systemFolders.map((node) => (
          <FolderItem
            key={node.id}
            node={node}
            currentDocumentId={currentDocumentId}
            onSelectDoc={handleSelectDoc}
            allFolders={folderTree}
          />
        ))}

        {/* Divider between system and user folders */}
        {systemFolders.length > 0 && userFolders.length > 0 && (
          <div className="my-1 mx-2 border-t border-border-default opacity-40" />
        )}

        {/* User folders */}
        {userFolders.map((node) => (
          <FolderItem
            key={node.id}
            node={node}
            currentDocumentId={currentDocumentId}
            onSelectDoc={handleSelectDoc}
            allFolders={folderTree}
          />
        ))}

        {/* Root-level new folder inline input */}
        {creatingRoot && (
          <div className="flex items-center gap-1.5 px-2 py-1">
            <Folder className="w-3 h-3 shrink-0 text-text-muted" />
            <input
              autoFocus
              value={rootFolderName}
              onChange={(e) => setRootFolderName(e.target.value)}
              onBlur={submitRootCreate}
              onKeyDown={(e) => {
                if (e.key === "Enter") submitRootCreate();
                if (e.key === "Escape") {
                  setCreatingRoot(false);
                  setRootFolderName("");
                }
              }}
              placeholder="文件夹名称"
              className="flex-1 bg-bg-secondary border border-accent-primary rounded px-1 outline-none text-xs text-text-primary placeholder:text-text-muted"
            />
          </div>
        )}

        {folderTree.length === 0 && (
          <div className="flex flex-col items-center justify-center h-24 gap-1 text-text-muted">
            <p className="text-xs">暂无文件夹</p>
          </div>
        )}
      </div>
    </div>
  );
}
