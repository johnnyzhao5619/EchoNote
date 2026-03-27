import { useEffect } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Search, X } from "lucide-react";
import { useDebounce } from "use-debounce";

import { Input } from "@/components/ui/input";
import { buildWorkspaceDocumentRoute } from "@/lib/workspace-routes";
import { useWorkspaceStore } from "@/store/workspace";

export function SearchBar() {
  const navigate = useNavigate();
  const {
    searchQuery,
    searchResults,
    isSearching,
    setSearchQuery,
    search,
    clearSearch,
  } = useWorkspaceStore();
  const [debouncedQuery] = useDebounce(searchQuery, 300);

  useEffect(() => {
    if (debouncedQuery.trim()) {
      void search(debouncedQuery);
    } else {
      clearSearch();
    }
  }, [clearSearch, debouncedQuery, search]);

  const inSearch = !!searchQuery.trim();

  return (
    <div className="relative">
      <div className="relative flex items-center">
        <Search
          size={14}
          className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted"
        />
        <Input
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          placeholder="搜索文档…"
          className="h-8 border-border bg-bg-input pl-8 pr-8 text-sm"
        />
        {inSearch && (
          <button
            onClick={clearSearch}
            className="absolute right-2 text-text-muted hover:text-text-primary"
          >
            <X size={14} />
          </button>
        )}
      </div>

      {inSearch && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-72 overflow-y-auto rounded border border-border bg-bg-secondary shadow-lg">
          {isSearching && (
            <div className="p-2 text-xs text-text-muted">搜索中…</div>
          )}
          {!isSearching && searchResults.length === 0 && (
            <div className="p-2 text-xs text-text-muted">无匹配结果</div>
          )}
          {searchResults.map((result) => (
            <div
              key={result.document_id}
              className="cursor-pointer px-3 py-2 hover:bg-bg-hover"
              onClick={() => {
                void navigate(
                  buildWorkspaceDocumentRoute(result.document_id, result.folder_id),
                );
                clearSearch();
              }}
            >
              <div className="truncate text-sm font-medium">{result.title}</div>
              <div
                className="mt-0.5 line-clamp-2 text-xs text-text-muted [&_mark]:rounded-sm [&_mark]:bg-accent-muted [&_mark]:px-0.5 [&_mark]:text-accent"
                dangerouslySetInnerHTML={{ __html: result.snippet }}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
