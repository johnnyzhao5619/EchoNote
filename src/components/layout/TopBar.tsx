import { useRouterState } from "@tanstack/react-router";

const PAGE_TITLES: Record<string, string> = {
  "/recording":     "Recording",
  "/transcription": "Transcription",
  "/workspace":     "Workspace",
  "/timeline":      "Timeline",
  "/settings":      "Settings",
};

export function TopBar() {
  const { location } = useRouterState();
  const title =
    PAGE_TITLES[location.pathname] ??
    Object.entries(PAGE_TITLES).find(([key]) =>
      location.pathname.startsWith(key)
    )?.[1] ??
    "EchoNote";

  return (
    <div
      className="flex items-center px-4 border-b border-border-default bg-bg-secondary shrink-0"
      style={{ height: "var(--top-bar-height)" }}
    >
      <span className="text-sm font-medium text-text-primary">{title}</span>
    </div>
  );
}
