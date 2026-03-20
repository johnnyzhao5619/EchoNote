#!/usr/bin/env tsx
/**
 * convert-themes.ts — 将 docs/themes/*.json（VSCode 主题格式）
 * 转换为 resources/themes/*.json（EchoNote semanticTokens 格式）
 *
 * 用法：
 *   npx tsx scripts/convert-themes.ts
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const DOCS_THEMES_DIR    = path.resolve(__dirname, "../docs/themes");
const OUTPUT_THEMES_DIR  = path.resolve(__dirname, "../resources/themes");

/** VSCode 主题颜色到 EchoNote 语义 token 的映射表 */
const VSCODE_TO_ECHONOTE: Record<string, string> = {
  "editor.background":                      "bg.primary",
  "sideBar.background":                     "bg.sidebar",
  "input.background":                       "bg.input",
  "list.hoverBackground":                   "bg.hover",
  "editor.selectionBackground":             "bg.selection",
  "editorGroupHeader.tabsBackground":       "bg.secondary",
  "foreground":                             "text.secondary",
  "descriptionForeground":                  "text.muted",
  "disabledForeground":                     "text.disabled",
  "editor.foreground":                      "text.primary",
  "terminal.ansiBlue":                      "accent.primary",
  "button.background":                      "accent.primary",
  "button.hoverBackground":                 "accent.hover",
  "textLink.foreground":                    "accent.primary",
  "sash.hoverBorder":                       "border.default",
  "focusBorder":                            "border.focus",
  "editorError.foreground":                 "status.error",
  "editorWarning.foreground":               "status.warning",
  "gitDecoration.addedResourceForeground":  "status.success",
  "editorInfo.foreground":                  "status.info",
};

/** 确保输出目录存在 */
fs.mkdirSync(OUTPUT_THEMES_DIR, { recursive: true });

interface VscodeTheme {
  name: string;
  type: string;
  colors: Record<string, string>;
}

interface EchoNoteTheme {
  name: string;
  type: "dark" | "light";
  semanticTokens: Record<string, string>;
}

/** 去除 JSONC 文件中的行注释和尾随逗号（VSCode 主题文件为 JSONC 格式） */
function stripJsonComments(text: string): string {
  // 先去除行注释
  let result = text.replace(/\/\/[^\n]*/g, "");
  // 再去除尾随逗号（在 } 或 ] 之前的逗号）
  result = result.replace(/,(\s*[}\]])/g, "$1");
  return result;
}

function convertTheme(srcPath: string): EchoNoteTheme {
  const raw = JSON.parse(stripJsonComments(fs.readFileSync(srcPath, "utf-8"))) as VscodeTheme;
  const semanticTokens: Record<string, string> = {};

  for (const [vsKey, echoKey] of Object.entries(VSCODE_TO_ECHONOTE)) {
    const color = raw.colors?.[vsKey];
    if (color) {
      // 某些颜色带透明度（8位 hex）—— 保留透明度，仅为 accent.primary 去除
      if (echoKey === "accent.primary" && color.length === 9) {
        semanticTokens[echoKey] = color.slice(0, 7);
      } else {
        semanticTokens[echoKey] = color;
      }
    }
  }

  // 从 accent.primary 派生 accent.muted（添加 44 alpha）
  if (semanticTokens["accent.primary"] && !semanticTokens["accent.muted"]) {
    semanticTokens["accent.muted"] = semanticTokens["accent.primary"] + "44";
  }

  // 源文件中 tokyo-night-light 的 type 字段错误标记为 "dark"，
  // 按名称推断更可靠
  const inferredType: "dark" | "light" =
    raw.type === "light" || raw.name.toLowerCase().includes("light")
      ? "light"
      : "dark";

  return {
    name: raw.name,
    type: inferredType,
    semanticTokens,
  };
}

const themeFiles = fs
  .readdirSync(DOCS_THEMES_DIR)
  .filter((f) => f.endsWith(".json"));

for (const file of themeFiles) {
  const srcPath = path.join(DOCS_THEMES_DIR, file);

  // 输出文件名：去掉 "-color-theme" 后缀
  const outputName = file
    .replace(/-color-theme\.json$/, "")
    .replace(/\.json$/, "") + ".json";

  const outputPath = path.join(OUTPUT_THEMES_DIR, outputName);

  try {
    const converted = convertTheme(srcPath);
    fs.writeFileSync(outputPath, JSON.stringify(converted, null, 2) + "\n");
    console.log(`✓ ${file} → resources/themes/${outputName}`);
  } catch (err) {
    console.error(`✗ ${file}: ${err}`);
    process.exit(1);
  }
}

console.log(`\n${themeFiles.length} theme(s) converted successfully.`);
