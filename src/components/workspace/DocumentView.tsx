import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { save } from "@tauri-apps/plugin-dialog";
import { ChevronDown, Download } from "lucide-react";

import { useWorkspaceStore } from "@/store/workspace";
import type { DocumentDetail } from "@/lib/bindings";

interface Props {
  doc: DocumentDetail;
}

export function DocumentView({ doc }: Props) {
  const { exportDocument } = useWorkspaceStore();
  const assetMap = Object.fromEntries(doc.assets.map((asset) => [asset.role, asset]));
  const assetTabs = [
    { role: "transcript", label: "转写原文" },
    { role: "summary", label: "AI 摘要" },
    { role: "meeting_brief", label: "会议纪要" },
    { role: "translation", label: "翻译" },
  ] as const;
  const availableTabs = assetTabs.filter((tab) => assetMap[tab.role]);
  const defaultTab = availableTabs[0]?.role ?? "transcript";

  const handleExport = async (format: "md" | "txt" | "srt" | "vtt") => {
    const path = await save({
      defaultPath: `${doc.title}.${format}`,
      filters: [{ name: format.toUpperCase(), extensions: [format] }],
    });
    if (path) {
      await exportDocument(doc.id, format, path);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
        <h2 className="flex-1 truncate text-sm font-semibold text-text-primary">
          {doc.title}
        </h2>
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

      {availableTabs.length === 0 ? (
        <div className="flex flex-1 items-center justify-center text-sm text-text-muted">
          此文档暂无内容
        </div>
      ) : (
        <Tabs defaultValue={defaultTab} className="flex min-h-0 flex-1 flex-col">
          <TabsList className="h-auto justify-start gap-1 border-b border-border bg-transparent px-4 pt-2">
            {availableTabs.map(({ role, label }) => (
              <TabsTrigger
                key={role}
                value={role}
                className="text-xs data-[state=active]:bg-accent-muted data-[state=active]:text-accent"
              >
                {label}
              </TabsTrigger>
            ))}
          </TabsList>
          {availableTabs.map(({ role }) => (
            <TabsContent
              key={role}
              value={role}
              className="mt-0 flex-1 overflow-y-auto p-4"
            >
              <pre className="whitespace-pre-wrap text-sm leading-relaxed font-sans text-text-primary">
                {assetMap[role]?.content ?? ""}
              </pre>
            </TabsContent>
          ))}
        </Tabs>
      )}
    </div>
  );
}
