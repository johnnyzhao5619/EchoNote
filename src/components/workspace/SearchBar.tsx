import { Search } from "lucide-react";

import { Input } from "@/components/ui/input";

export function SearchBar() {
  return (
    <div className="relative">
      <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
      <Input
        readOnly
        value=""
        placeholder="搜索文档…"
        className="h-8 border-border bg-bg-input pl-8 text-sm"
      />
    </div>
  );
}
