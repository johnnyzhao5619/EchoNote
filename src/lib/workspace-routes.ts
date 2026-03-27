export function buildWorkspaceFolderRoute(folderId: string) {
  return {
    to: "/workspace/$folderId" as const,
    params: { folderId },
  };
}

export function buildWorkspaceDocumentRoute(
  documentId: string,
  folderId?: string | null,
) {
  if (folderId) {
    return {
      to: "/workspace/$folderId/$docId" as const,
      params: { folderId, docId: documentId },
    };
  }

  return {
    to: "/workspace/document/$documentId" as const,
    params: { documentId },
  };
}
