import type { DocumentDetail } from "@/lib/bindings";

interface Props {
  doc: DocumentDetail;
}

export function DocumentView({ doc }: Props) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-4 py-3">
        <h2 className="truncate text-sm font-semibold text-text-primary">
          {doc.title}
        </h2>
      </div>
      <div className="flex flex-1 items-center justify-center text-sm text-text-muted">
        文档视图将在下一步补全
      </div>
    </div>
  );
}
