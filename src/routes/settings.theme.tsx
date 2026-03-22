import { createFileRoute } from "@tanstack/react-router";
import { useThemeStore } from "@/store/theme";
import { commands } from "@/lib/bindings";

export const Route = createFileRoute("/settings/theme")({
  component: SettingsThemePage,
});

function SettingsThemePage() {
  const { currentTheme, themes, setTheme } = useThemeStore();

  const handleSelect = (name: string) => {
    setTheme(name);
    commands.setCurrentTheme(name).catch((e) => {
      console.error("[theme] setCurrentTheme failed:", e);
    });
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <h1 className="text-lg font-semibold text-text-primary">Theme</h1>

      {themes.length === 0 ? (
        <p className="text-sm text-text-muted">Loading themes…</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {themes.map((theme) => {
            const isActive = theme.name === currentTheme;
            return (
              <button
                key={theme.name}
                onClick={() => handleSelect(theme.name)}
                className={[
                  "flex flex-col items-start gap-2 rounded-lg border p-4 text-left transition-colors",
                  isActive
                    ? "border-accent bg-bg-secondary"
                    : "border-border-default bg-bg-secondary hover:border-accent/50",
                ].join(" ")}
              >
                {/* 主题色块预览 */}
                <ThemePreview type={theme.type} />

                <div className="space-y-0.5">
                  <p className="text-sm font-medium text-text-primary">{theme.name}</p>
                  <p className="text-xs capitalize text-text-muted">{theme.type}</p>
                </div>

                {isActive && (
                  <span className="text-xs font-medium text-accent-primary">Active</span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** 简单的主题色块预览（三色条）*/
function ThemePreview({ type }: { type: "dark" | "light" }) {
  const palettes: Record<"dark" | "light", string[]> = {
    dark:  ["#1a1b26", "#7aa2f7", "#c0caf5"],
    light: ["#d5d6db", "#2e7de9", "#3760bf"],
  };
  const colors = palettes[type];
  return (
    <div className="flex w-full gap-1 rounded overflow-hidden h-8">
      {colors.map((c) => (
        <div key={c} className="flex-1" style={{ backgroundColor: c }} />
      ))}
    </div>
  );
}
