import { useEffect, useMemo, useState } from "react";

import { ChevronDown, Download } from "lucide-react";
import { save } from "@tauri-apps/plugin-dialog";

import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { AiTaskBar } from "./AiTaskBar";
import { EditableAsset } from "./EditableAsset";
import { useWorkspaceStore } from "@/store/workspace";
import type { DocumentDetail } from "@/lib/bindings";

interface Props {
  doc: DocumentDetail;
}

const ASSET_META: Record<string, { label: string; actionLabel: string }> = {
  document_text: { label: "正文", actionLabel: "编辑正文" },
  transcript: { label: "转写原文", actionLabel: "编辑转写" },
  summary: { label: "AI 摘要", actionLabel: "编辑摘要" },
  meeting_brief: { label: "会议纪要", actionLabel: "编辑纪要" },
  translation: { label: "翻译", actionLabel: "编辑翻译" },
};

const ASSET_ORDER = ["document_text", "transcript", "summary", "meeting_brief", "translation"] as const;

function getPrimaryAssetRole(sourceType: string) {
  return sourceType === "recording" ? "transcript" : "document_text";
}

export function DocumentView({ doc }: Props) {
  const { exportDocument, updateDocument } = useWorkspaceStore();
  const [titleDraft, setTitleDraft] = useState(doc.title);

  useEffect(() => {
    setTitleDraft(doc.title);
  }, [doc.id, doc.title]);

  const handleExport = async (format: "md" | "txt" | "srt" | "vtt") => {
    const path = await save({
      defaultPath: `${doc.title}.${format}`,
      filters: [{ name: format.toUpperCase(), extensions: [format] }],
    });
    if (path) {
      await exportDocument(doc.id, format, path);
    }
  };

  const { editableSections, primaryRole, canRunAiTasks } = useMemo(() => {
    const assetMap = new Map(doc.assets.map((asset) => [asset.role, asset]));
    const primaryRole = getPrimaryAssetRole(doc.source_type);
    const orderedRoles = [primaryRole, ...ASSET_ORDER.filter((role) => role !== primaryRole)];

    const sections: Array<{ role: string; label: string; actionLabel: string; content: string }> = [];

    for (const role of orderedRoles) {
      const asset = assetMap.get(role);
      if (!asset && role !== primaryRole) {
        continue;
      }

      const meta = ASSET_META[role];
      sections.push({
        role,
        label: meta.label,
        actionLabel: meta.actionLabel,
        content: asset?.content ?? "",
      });
    }

    return {
      editableSections: sections,
      primaryRole,
      canRunAiTasks: assetMap.has("document_text") || assetMap.has("transcript"),
    };
  }, [doc.assets, doc.source_type]);

  const commitTitle = async () => {
    const nextTitle = titleDraft.trim();
    if (!nextTitle || nextTitle === doc.title) {
      setTitleDraft(doc.title);
      return;
    }

    try {
      await updateDocument(doc.id, { title: nextTitle });
    } catch (error) {
      console.error("[DocumentView] title update failed:", error);
      setTitleDraft(doc.title);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
        <input
          aria-label="标题"
          value={titleDraft}
          onChange={(event) => setTitleDraft(event.target.value)}
          onBlur={() => void commitTitle()}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              event.currentTarget.blur();
            }
          }}
          className="flex-1 truncate border-none bg-transparent text-sm font-semibold text-text-primary outline-none"
        />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="sm" variant="outline" className="gap-1">
              <Download size={14} /> 导出 <ChevronDown size={12} />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => void handleExport("md")}>
              Markdown (.md)
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => void handleExport("txt")}>
              纯文本 (.txt)
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => void handleExport("srt")}>
              字幕 SRT (.srt)
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => void handleExport("vtt")}>
              字幕 VTT (.vtt)
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="grid gap-4">
          {editableSections.map((section) => (
            <EditableAsset
              key={section.role}
              documentId={doc.id}
              role={section.role}
              label={section.label}
              actionLabel={section.actionLabel}
              initialContent={section.content}
              emptyStateText={section.role === primaryRole ? "点击开始编写" : undefined}
            />
          ))}

          {canRunAiTasks && (
            <AiTaskBar documentId={doc.id} className="border-t border-border/60 pt-4" />
          )}
        </div>
      </div>
    </div>
  );
}
