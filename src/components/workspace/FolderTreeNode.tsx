import { type KeyboardEvent, useEffect, useRef } from "react";
import {
  ChevronRight,
  Folder,
  FolderOpen,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";

import { cn } from "@/lib/utils";
import type { FolderNode as FolderNodeType } from "@/lib/bindings";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";

interface Props {
  node: FolderNodeType;
  depth: number;
  selectedId: string | null;
  activeTreeItemId: string | null;
  visibleTreeItemIds: string[];
  expandedFolderIds: Set<string>;
  onSelect: (id: string) => void;
  onActivateTreeItem: (id: string) => void;
  onToggleExpand: (id: string) => void;
  onCreateChild: (parentId: string) => void;
  onRename: (id: string, currentName: string) => void;
  onDelete: (id: string) => void;
}

export function FolderTreeNode({
  node,
  depth,
  selectedId,
  activeTreeItemId,
  visibleTreeItemIds,
  expandedFolderIds,
  onSelect,
  onActivateTreeItem,
  onToggleExpand,
  onCreateChild,
  onRename,
  onDelete,
}: Props) {
  const isSelected = node.id === selectedId;
  const hasChildren = node.children.length > 0;
  const isExpanded = expandedFolderIds.has(node.id);
  const isActiveTreeItem = node.id === activeTreeItemId;
  const treeItemRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isActiveTreeItem) {
      treeItemRef.current?.focus();
    }
  }, [isActiveTreeItem]);

  const selectNode = () => {
    onActivateTreeItem(node.id);
    onSelect(node.id);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      selectNode();
      return;
    }

    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const currentIndex = visibleTreeItemIds.indexOf(node.id);
      if (currentIndex === -1) {
        return;
      }

      const nextIndex = event.key === "ArrowDown" ? currentIndex + 1 : currentIndex - 1;
      const nextId = visibleTreeItemIds[nextIndex];
      if (nextId) {
        onActivateTreeItem(nextId);
      }
      return;
    }

    if (event.key === "ArrowRight" && hasChildren && !isExpanded) {
      event.preventDefault();
      onActivateTreeItem(node.id);
      onToggleExpand(node.id);
      return;
    }

    if (event.key === "ArrowLeft" && hasChildren && isExpanded) {
      event.preventDefault();
      onActivateTreeItem(node.id);
      onToggleExpand(node.id);
    }
  };

  return (
    <li role="none">
      <ContextMenu>
        <ContextMenuTrigger asChild>
          <div className="space-y-0.5">
            <div
              className={cn(
                "flex items-center gap-1 rounded px-2 py-1 text-sm hover:bg-bg-hover",
                isSelected && "bg-accent-muted text-accent",
              )}
              style={{ paddingLeft: `${depth * 12 + 8}px` }}
            >
              {hasChildren ? (
                <button
                  type="button"
                  tabIndex={-1}
                  className="flex shrink-0 items-center justify-center"
                  aria-label={`${isExpanded ? "折叠" : "展开"} ${node.name}`}
                  aria-expanded={isExpanded}
                  onClick={(event) => {
                    event.stopPropagation();
                    onActivateTreeItem(node.id);
                    onToggleExpand(node.id);
                  }}
                >
                  <ChevronRight
                    size={14}
                    className={cn("shrink-0 transition-transform", isExpanded && "rotate-90")}
                  />
                </button>
              ) : (
                <span className="w-3.5 shrink-0" />
              )}
              {isExpanded && hasChildren ? (
                <FolderOpen size={14} className="shrink-0 text-accent" />
              ) : (
                <Folder size={14} className="shrink-0 text-text-secondary" />
              )}
              <div
                role="treeitem"
                ref={treeItemRef}
                tabIndex={isActiveTreeItem ? 0 : -1}
                aria-label={node.name}
                aria-level={depth + 1}
                aria-selected={isSelected}
                aria-expanded={hasChildren ? isExpanded : undefined}
                className="flex min-w-0 flex-1 items-center rounded outline-none focus-visible:ring-1 focus-visible:ring-accent/60"
                onClick={selectNode}
                onKeyDown={handleKeyDown}
                onFocus={() => onActivateTreeItem(node.id)}
              >
                <span className="truncate">{node.name}</span>
              </div>
              {node.document_count > 0 && (
                <span aria-hidden="true" className="ml-auto text-xs text-text-muted">
                  {node.document_count}
                </span>
              )}
            </div>
          </div>
        </ContextMenuTrigger>
        <ContextMenuContent>
          {!node.is_system ? (
            <>
              <ContextMenuItem onClick={() => onCreateChild(node.id)}>
                <Plus size={14} className="mr-2" /> 新建子文件夹
              </ContextMenuItem>
              <ContextMenuItem onClick={() => onRename(node.id, node.name)}>
                <Pencil size={14} className="mr-2" /> 重命名
              </ContextMenuItem>
              <ContextMenuItem
                onClick={() => onDelete(node.id)}
                className="text-status-error focus:text-status-error"
              >
                <Trash2 size={14} className="mr-2" /> 删除
              </ContextMenuItem>
            </>
          ) : (
            <ContextMenuItem disabled>系统文件夹（不可修改）</ContextMenuItem>
          )}
        </ContextMenuContent>
      </ContextMenu>

      {isExpanded && node.children.length > 0 && (
        <ul role="group">
          {node.children.map((child) => (
            <FolderTreeNode
              key={child.id}
            node={child}
            depth={depth + 1}
            selectedId={selectedId}
            activeTreeItemId={activeTreeItemId}
            visibleTreeItemIds={visibleTreeItemIds}
            expandedFolderIds={expandedFolderIds}
            onSelect={onSelect}
            onActivateTreeItem={onActivateTreeItem}
            onToggleExpand={onToggleExpand}
            onCreateChild={onCreateChild}
            onRename={onRename}
              onDelete={onDelete}
            />
          ))}
        </ul>
      )}
    </li>
  );
}
