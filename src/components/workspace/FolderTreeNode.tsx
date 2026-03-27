import { useState } from "react";
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
  onSelect: (id: string) => void;
  onCreateChild: (parentId: string) => void;
  onRename: (id: string, currentName: string) => void;
  onDelete: (id: string) => void;
}

export function FolderTreeNode({
  node,
  depth,
  selectedId,
  onSelect,
  onCreateChild,
  onRename,
  onDelete,
}: Props) {
  const [expanded, setExpanded] = useState(depth === 0);
  const isSelected = node.id === selectedId;
  const hasChildren = node.children.length > 0;

  return (
    <div>
      <ContextMenu>
        <ContextMenuTrigger>
          <div
            className={cn(
              "flex cursor-pointer select-none items-center gap-1 rounded px-2 py-1 text-sm hover:bg-bg-hover",
              isSelected && "bg-accent-muted text-accent",
            )}
            style={{ paddingLeft: `${depth * 12 + 8}px` }}
            onClick={() => {
              onSelect(node.id);
              if (hasChildren) {
                setExpanded((value) => !value);
              }
            }}
          >
            {hasChildren ? (
              <ChevronRight
                size={14}
                className={cn("shrink-0 transition-transform", expanded && "rotate-90")}
              />
            ) : (
              <span className="w-3.5 shrink-0" />
            )}
            {expanded && hasChildren ? (
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

      {expanded &&
        node.children.map((child) => (
          <FolderTreeNode
            key={child.id}
            node={child}
            depth={depth + 1}
            selectedId={selectedId}
            onSelect={onSelect}
            onCreateChild={onCreateChild}
            onRename={onRename}
            onDelete={onDelete}
          />
        ))}
    </div>
  );
}
