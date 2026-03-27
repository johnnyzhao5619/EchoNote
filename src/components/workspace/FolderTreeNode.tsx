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
  expandedFolderIds: Set<string>;
  onSelect: (id: string) => void;
  onToggleExpand: (id: string) => void;
  onCreateChild: (parentId: string) => void;
  onRename: (id: string, currentName: string) => void;
  onDelete: (id: string) => void;
}

export function FolderTreeNode({
  node,
  depth,
  selectedId,
  expandedFolderIds,
  onSelect,
  onToggleExpand,
  onCreateChild,
  onRename,
  onDelete,
}: Props) {
  const isSelected = node.id === selectedId;
  const hasChildren = node.children.length > 0;
  const isExpanded = expandedFolderIds.has(node.id);

  return (
    <div>
      <ContextMenu>
        <ContextMenuTrigger asChild>
          <div
            className={cn(
              "flex cursor-pointer select-none items-center gap-1 rounded px-2 py-1 text-sm hover:bg-bg-hover",
              isSelected && "bg-accent-muted text-accent",
            )}
            role="treeitem"
            aria-label={node.name}
            aria-level={depth + 1}
            aria-selected={isSelected}
            aria-expanded={hasChildren ? isExpanded : undefined}
            style={{ paddingLeft: `${depth * 12 + 8}px` }}
            onClick={() => {
              onSelect(node.id);
            }}
          >
            {hasChildren ? (
              <button
                type="button"
                className="flex shrink-0 items-center justify-center"
                aria-label={`${isExpanded ? "折叠" : "展开"} ${node.name}`}
                aria-expanded={isExpanded}
                onClick={(event) => {
                  event.stopPropagation();
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
            <span className="flex-1 truncate">{node.name}</span>
            {node.document_count > 0 && (
              <span className="ml-auto text-xs text-text-muted">{node.document_count}</span>
            )}
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

      {isExpanded &&
        node.children.map((child) => (
          <FolderTreeNode
            key={child.id}
            node={child}
            depth={depth + 1}
            selectedId={selectedId}
            expandedFolderIds={expandedFolderIds}
            onSelect={onSelect}
            onToggleExpand={onToggleExpand}
            onCreateChild={onCreateChild}
            onRename={onRename}
            onDelete={onDelete}
          />
        ))}
    </div>
  );
}
