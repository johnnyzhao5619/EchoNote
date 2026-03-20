import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const RESOURCES_DIR = path.resolve(__dirname, "../../resources/themes");

describe("convert-themes output", () => {
  const themeFiles = ["tokyo-night.json", "tokyo-night-storm.json", "tokyo-night-light.json"];

  for (const file of themeFiles) {
    describe(file, () => {
      const filePath = path.join(RESOURCES_DIR, file);

      it("file exists", () => {
        expect(fs.existsSync(filePath)).toBe(true);
      });

      it("has required semanticTokens fields", () => {
        const theme = JSON.parse(fs.readFileSync(filePath, "utf-8"));
        expect(theme.semanticTokens).toBeDefined();
        expect(theme.semanticTokens["bg.primary"]).toBeDefined();
        expect(theme.semanticTokens["text.primary"]).toBeDefined();
        expect(theme.semanticTokens["accent.primary"]).toBeDefined();
        expect(theme.semanticTokens["border.default"]).toBeDefined();
        expect(theme.semanticTokens["status.error"]).toBeDefined();
      });

      it("has valid type field (dark|light)", () => {
        const theme = JSON.parse(fs.readFileSync(filePath, "utf-8"));
        expect(["dark", "light"]).toContain(theme.type);
      });

      it("tokyo-night-light has type light", () => {
        if (file !== "tokyo-night-light.json") return;
        const theme = JSON.parse(fs.readFileSync(filePath, "utf-8"));
        expect(theme.type).toBe("light");
      });
    });
  }
});
