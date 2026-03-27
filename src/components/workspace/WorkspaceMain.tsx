import { useEffect } from "react";
import { useNavigate, useParams } from "@tanstack/react-router";
import { FileText, FolderPlus, Import } from "lucide-react";
import { open } from "@tauri-apps/plugin-dialog";

import { Button } from "@/components/ui/button";
import { buildWorkspaceDocumentRoute } from "@/lib/workspace-routes";
import { useWorkspaceStore } from "@/store/workspace";

import { DocumentView } from "./DocumentView";

export function WorkspaceMain() {
  const navigate = useNavigate();
  const params = useParams({ strict: false }) as {
    folderId?: string;
    docId?: string;
    documentId?: string;
  };
  const {
    documents,
    currentDoc,
    currentFolderId,
    selectFolder,
    openDocument,
    createDocument,
    importFile,
  } = useWorkspaceStore();

  const folderId = params.folderId;
  const docId = params.docId ?? params.documentId;

  useEffect(() => {
    const targetFolderId = folderId ?? null;
    if (targetFolderId !== currentFolderId || (!docId && currentDoc)) {
      void selectFolder(targetFolderId);
    }
  }, [currentDoc, currentFolderId, docId, folderId, selectFolder]);

  useEffect(() => {
    if (docId) {
      void openDocument(docId);
    }
  }, [docId, openDocument]);

  if (currentDoc) {
    return <DocumentView doc={currentDoc} />;
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-border px-4 py-2">
        <Button
          size="sm"
          variant="ghost"
          className="gap-1"
          onClick={async () => {
            const documentId = await createDocument("新建文档", currentFolderId ?? undefined);
            void navigate(buildWorkspaceDocumentRoute(documentId, currentFolderId ?? undefined));
          }}
        >
          <FolderPlus size={14} /> 新建文档
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="gap-1"
          onClick={async () => {
            const selected = await open({
              multiple: false,
              filters: [
                { name: "Documents", extensions: ["pdf", "docx", "txt", "md"] },
              ],
            });
            if (typeof selected === "string") {
              const importedDocument = await importFile(selected, currentFolderId ?? undefined);
              void navigate(buildWorkspaceDocumentRoute(importedDocument.id, importedDocument.folder_id));
            }
          }}
        >
          <Import size={14} /> 导入文件
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {documents.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-text-muted">
            <FileText size={40} />
            <p className="text-sm">此文件夹为空</p>
          </div>
        ) : (
          <div className="grid gap-2">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="cursor-pointer rounded border border-border p-3 hover:bg-bg-hover"
                onClick={() => void navigate(buildWorkspaceDocumentRoute(doc.id, currentFolderId))}
              >
                <div className="truncate text-sm font-medium">{doc.title}</div>
                <div className="mt-1 flex gap-2 text-xs text-text-muted">
                  {doc.has_transcript && (
                    <span className="rounded bg-bg-secondary px-1">转写</span>
                  )}
                  {doc.has_summary && (
                    <span className="rounded bg-bg-secondary px-1">摘要</span>
                  )}
                  {doc.has_meeting_brief && (
                    <span className="rounded bg-bg-secondary px-1">会议纪要</span>
                  )}
                  <span className="ml-auto">
                    {new Date(doc.updated_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
