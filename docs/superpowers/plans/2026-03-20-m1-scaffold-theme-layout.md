# EchoNote v3.0.0 M1: Scaffold + Theme System + App Layout Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 EchoNote v3.0.0 的 Tauri 2.x + React 18 项目骨架，包含主题系统和应用布局，使应用可运行并展示完整 UI 框架。

**Architecture:** 采用 Tauri 2.x 三层架构（React 前端 / IPC 层 / Rust 后端），前端使用 TanStack Router 管理 5 个功能页面路由，Zustand 管理应用状态；主题系统通过 CSS 变量三层 Token 架构（Primitive → Semantic → Tailwind）实现运行时切换，`ThemeProvider` 在应用启动时将当前主题 token 注入 `:root`；M1 不实现任何实际业务功能，只建立目录结构、类型骨架和 UI 框架。

**Tech Stack:** Tauri 2.x, Rust (thiserror, serde, specta), React 18, TypeScript, Tailwind CSS v3, shadcn/ui, TanStack Router v1, Zustand, tauri-specta v2, Vitest, @testing-library/react

---

### Task 1: Tauri 2.x + React 18 + TypeScript 项目初始化

**Files:**
- Create: `src-tauri/Cargo.toml`
- Create: `src-tauri/tauri.conf.json`
- Create: `src-tauri/build.rs`
- Create: `src-tauri/src/main.rs`
- Create: `src-tauri/src/lib.rs`
- Create: `src-tauri/src/state.rs`
- Create: `src-tauri/src/error.rs`
- Create: `src-tauri/src/commands/mod.rs`
- Create: `src-tauri/src/commands/theme.rs`
- Create: `src-tauri/src/commands/settings.rs`
- Create: `src/main.tsx`
- Create: `src/App.tsx`
- Create: `src/vite-env.d.ts`
- Create: `index.html`
- Create: `vite.config.ts`
- Create: `tsconfig.json`
- Create: `tsconfig.node.json`
- Create: `package.json`
- Modify: `.gitignore`

- [ ] **Step 1: 初始化 npm 项目并安装前端依赖**

  在项目根目录（假设新建于 `/Users/weijiazhao/Dev/EchoNote-v3`，下同）执行：

  ```bash
  # 初始化 Tauri 2.x 项目
  npm create tauri-app@latest echonote-v3 -- \
    --template react-ts \
    --manager npm \
    --tauri
  cd echonote-v3

  # 安装前端生产依赖
  npm install \
    @tanstack/react-router \
    zustand \
    class-variance-authority \
    clsx \
    tailwind-merge \
    lucide-react \
    @radix-ui/react-slot \
    @radix-ui/react-separator \
    @radix-ui/react-tooltip

  # 安装前端开发依赖
  npm install -D \
    tailwindcss \
    postcss \
    autoprefixer \
    @tailwindcss/typography \
    @testing-library/react \
    @testing-library/jest-dom \
    @testing-library/user-event \
    vitest \
    @vitejs/plugin-react \
    jsdom \
    tsx \
    typescript

  # 初始化 Tailwind
  npx tailwindcss init -p
  ```

- [ ] **Step 2: 配置 `tsconfig.json`**

  写入 `tsconfig.json`：

  ```json
  {
    "compilerOptions": {
      "target": "ES2020",
      "useDefineForClassFields": true,
      "lib": ["ES2020", "DOM", "DOM.Iterable"],
      "module": "ESNext",
      "skipLibCheck": true,
      "moduleResolution": "bundler",
      "allowImportingTsExtensions": true,
      "resolveJsonModule": true,
      "isolatedModules": true,
      "noEmit": true,
      "jsx": "react-jsx",
      "strict": true,
      "noUnusedLocals": true,
      "noUnusedParameters": true,
      "noFallthroughCasesInSwitch": true,
      "paths": {
        "@/*": ["./src/*"]
      }
    },
    "include": ["src", "scripts"],
    "references": [{ "path": "./tsconfig.node.json" }]
  }
  ```

  写入 `tsconfig.node.json`：

  ```json
  {
    "compilerOptions": {
      "composite": true,
      "skipLibCheck": true,
      "module": "ESNext",
      "moduleResolution": "bundler",
      "allowSyntheticDefaultImports": true
    },
    "include": ["vite.config.ts"]
  }
  ```

- [ ] **Step 3: 配置 `vite.config.ts`（含 Vitest 配置）**

  写入 `vite.config.ts`：

  ```typescript
  import { defineConfig } from "vite";
  import react from "@vitejs/plugin-react";
  import path from "path";

  export default defineConfig({
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    // Tauri 开发服务器配置
    server: {
      port: 1420,
      strictPort: true,
      host: "localhost",
      hmr: {
        protocol: "ws",
        host: "localhost",
        port: 1421,
      },
      watch: {
        ignored: ["**/src-tauri/**"],
      },
    },
    clearScreen: false,
    envPrefix: ["VITE_", "TAURI_"],
    // Vitest 配置
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: ["./src/test-setup.ts"],
      css: true,
    },
  });
  ```

- [ ] **Step 4: 配置 `src-tauri/Cargo.toml`**

  写入 `src-tauri/Cargo.toml`：

  ```toml
  [package]
  name = "echonote"
  version = "3.0.0"
  description = "EchoNote - AI-powered meeting recorder and transcriber"
  authors = ["EchoNote Team"]
  edition = "2021"

  [lib]
  name = "echonote_lib"
  crate-type = ["staticlib", "cdylib", "rlib"]

  [build-dependencies]
  tauri-build = { version = "2", features = [] }

  [dependencies]
  tauri         = { version = "2",   features = ["protocol-asset"] }
  tauri-specta  = { version = "2",   features = ["derive"] }
  specta        = { version = "2" }
  specta-typescript = "0.0.7"
  serde         = { version = "1",   features = ["derive"] }
  serde_json    = "1"
  thiserror     = "1"
  tokio         = { version = "1",   features = ["full"] }
  uuid          = { version = "1",   features = ["v4"] }
  log           = "0.4"
  env_logger    = "0.11"

  [features]
  default = ["custom-protocol"]
  custom-protocol = ["tauri/custom-protocol"]
  cuda = []

  [profile.release]
  opt-level = 3
  lto = true
  codegen-units = 1
  panic = "abort"
  strip = true
  ```

- [ ] **Step 5: 写入 `src-tauri/build.rs`**

  ```rust
  fn main() {
      tauri_build::build()
  }
  ```

- [ ] **Step 6: 配置 `src-tauri/tauri.conf.json`**

  写入 `src-tauri/tauri.conf.json`：

  ```json
  {
    "$schema": "https://schema.tauri.app/config/2",
    "productName": "EchoNote",
    "version": "3.0.0",
    "identifier": "app.echonote.desktop",
    "build": {
      "frontendDist": "../dist",
      "devUrl": "http://localhost:1420",
      "beforeDevCommand": "npm run dev",
      "beforeBuildCommand": "npm run build"
    },
    "app": {
      "windows": [
        {
          "label": "main",
          "title": "EchoNote",
          "width": 1280,
          "height": 800,
          "minWidth": 900,
          "minHeight": 600,
          "resizable": true,
          "fullscreen": false
        }
      ],
      "security": {
        "csp": null
      }
    },
    "bundle": {
      "active": true,
      "targets": "all",
      "icon": [
        "icons/32x32.png",
        "icons/128x128.png",
        "icons/128x128@2x.png",
        "icons/icon.icns",
        "icons/icon.ico"
      ]
    }
  }
  ```

- [ ] **Step 7: 创建 `src-tauri/src/main.rs`**

  ```rust
  // Prevents additional console window on Windows in release, DO NOT REMOVE!!
  #![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

  fn main() {
      echonote_lib::run();
  }
  ```

- [ ] **Step 8: 验证 Rust 编译和前端编译**

  ```bash
  # 验证 Rust 编译
  cd src-tauri && cargo check && cd ..

  # 验证前端类型检查
  npm run typecheck 2>/dev/null || npx tsc --noEmit
  ```

- [ ] **Commit**

  ```bash
  git add -A
  git commit -m "feat(m1): initialize Tauri 2.x + React 18 + TypeScript project scaffold"
  ```

---

### Task 2: Rust 错误类型 + AppState 骨架 + lib.rs 启动

**Files:**
- Create: `src-tauri/src/error.rs`
- Create: `src-tauri/src/state.rs`
- Modify: `src-tauri/src/lib.rs`
- Create: `src-tauri/src/commands/mod.rs`
- Create: `src-tauri/src/commands/theme.rs`
- Create: `src-tauri/src/commands/settings.rs`

- [ ] **Step 1: 先写测试文件（TDD）**

  创建 `src-tauri/src/error.rs` 底部测试模块（先写测试）：

  注意：先创建文件，只含测试部分：

  ```rust
  // src-tauri/src/error.rs — 先写测试骨架
  #[cfg(test)]
  mod tests {
      use super::*;

      #[test]
      fn test_app_error_display_audio() {
          let err = AppError::Audio("microphone not found".to_string());
          assert_eq!(err.to_string(), "audio error: microphone not found");
      }

      #[test]
      fn test_app_error_display_channel_closed() {
          let err = AppError::ChannelClosed;
          assert_eq!(err.to_string(), "channel closed");
      }

      #[test]
      fn test_app_error_serde_round_trip() {
          let err = AppError::NotFound("recording-123".to_string());
          let json = serde_json::to_string(&err).unwrap();
          assert!(json.contains("\"kind\":\"NotFound\""));
          assert!(json.contains("recording-123"));
      }
  }
  ```

- [ ] **Step 2: 实现 `src-tauri/src/error.rs`**

  ```rust
  use serde::Serialize;

  #[derive(Debug, thiserror::Error, Serialize, specta::Type)]
  #[serde(tag = "kind", content = "message")]
  pub enum AppError {
      #[error("audio error: {0}")]
      Audio(String),

      #[error("transcription error: {0}")]
      Transcription(String),

      #[error("llm error: {0}")]
      Llm(String),

      #[error("storage error: {0}")]
      Storage(String),

      #[error("io error: {0}")]
      Io(String),

      #[error("model error: {0}")]
      Model(String),

      #[error("workspace error: {0}")]
      Workspace(String),

      #[error("not found: {0}")]
      NotFound(String),

      #[error("validation: {0}")]
      Validation(String),

      #[error("channel closed")]
      ChannelClosed,
  }

  impl AppError {
      pub fn channel<E: std::fmt::Display>(_e: E) -> Self {
          AppError::ChannelClosed
      }

      pub fn io<E: std::fmt::Display>(e: E) -> Self {
          AppError::Io(e.to_string())
      }

      pub fn storage<E: std::fmt::Display>(e: E) -> Self {
          AppError::Storage(e.to_string())
      }
  }

  // 让 Tauri 能序列化错误返回给前端
  impl From<AppError> for tauri::ipc::InvokeError {
      fn from(e: AppError) -> Self {
          tauri::ipc::InvokeError::from_serde_json(
              serde_json::to_value(&e).unwrap_or_default()
          )
      }
  }

  #[cfg(test)]
  mod tests {
      use super::*;

      #[test]
      fn test_app_error_display_audio() {
          let err = AppError::Audio("microphone not found".to_string());
          assert_eq!(err.to_string(), "audio error: microphone not found");
      }

      #[test]
      fn test_app_error_display_channel_closed() {
          let err = AppError::ChannelClosed;
          assert_eq!(err.to_string(), "channel closed");
      }

      #[test]
      fn test_app_error_serde_round_trip() {
          let err = AppError::NotFound("recording-123".to_string());
          let json = serde_json::to_string(&err).unwrap();
          assert!(json.contains("\"kind\":\"NotFound\""));
          assert!(json.contains("recording-123"));
      }
  }
  ```

- [ ] **Step 3: 实现 `src-tauri/src/state.rs`（AppState 骨架）**

  ```rust
  use std::sync::Arc;
  use tokio::sync::Mutex;

  /// AppState 是注入所有 Tauri commands 的共享状态。
  /// M1 阶段只有结构骨架，无实际业务字段。
  /// 后续里程碑逐步添加 transcription_tx / llm_tx / model_tx 等 channel sender。
  #[derive(Clone)]
  pub struct AppState {
      pub inner: Arc<AppStateInner>,
  }

  pub struct AppStateInner {
      /// 当前选中主题名称（对应 resources/themes/*.json 的 name 字段）
      pub current_theme: Mutex<String>,
  }

  impl AppState {
      pub fn new() -> Self {
          Self {
              inner: Arc::new(AppStateInner {
                  current_theme: Mutex::new("Tokyo Night".to_string()),
              }),
          }
      }
  }

  impl Default for AppState {
      fn default() -> Self {
          Self::new()
      }
  }

  #[cfg(test)]
  mod tests {
      use super::*;

      #[tokio::test]
      async fn test_app_state_default_theme() {
          let state = AppState::new();
          let theme = state.inner.current_theme.lock().await;
          assert_eq!(*theme, "Tokyo Night");
      }
  }
  ```

- [ ] **Step 4: 实现 `src-tauri/src/commands/mod.rs`**

  ```rust
  pub mod settings;
  pub mod theme;
  ```

- [ ] **Step 5: 实现 `src-tauri/src/commands/theme.rs`（骨架）**

  ```rust
  use crate::{error::AppError, state::AppState};
  use serde::{Deserialize, Serialize};
  use specta::Type;

  /// 主题描述符，仅含元信息（不含完整 token 数据，token 由前端直接读取 JSON 文件）
  #[derive(Debug, Clone, Serialize, Deserialize, Type)]
  pub struct ThemeInfo {
      pub name: String,
      pub r#type: String, // "dark" | "light"
  }

  /// 获取当前激活主题名称
  #[tauri::command]
  #[specta::specta]
  pub async fn get_current_theme(
      state: tauri::State<'_, AppState>,
  ) -> Result<String, AppError> {
      let theme = state.inner.current_theme.lock().await;
      Ok(theme.clone())
  }

  /// 设置当前激活主题
  #[tauri::command]
  #[specta::specta]
  pub async fn set_current_theme(
      name: String,
      state: tauri::State<'_, AppState>,
  ) -> Result<(), AppError> {
      let mut theme = state.inner.current_theme.lock().await;
      *theme = name;
      Ok(())
  }

  /// 列举内置主题信息
  #[tauri::command]
  #[specta::specta]
  pub async fn list_builtin_themes() -> Result<Vec<ThemeInfo>, AppError> {
      Ok(vec![
          ThemeInfo { name: "Tokyo Night".to_string(),       r#type: "dark".to_string() },
          ThemeInfo { name: "Tokyo Night Storm".to_string(), r#type: "dark".to_string() },
          ThemeInfo { name: "Tokyo Night Light".to_string(), r#type: "light".to_string() },
      ])
  }

  #[cfg(test)]
  mod tests {
      use super::*;

      #[tokio::test]
      async fn test_list_builtin_themes_returns_three() {
          let themes = list_builtin_themes().await.unwrap();
          assert_eq!(themes.len(), 3);
          assert!(themes.iter().any(|t| t.name == "Tokyo Night"));
          assert!(themes.iter().any(|t| t.name == "Tokyo Night Storm"));
          assert!(themes.iter().any(|t| t.name == "Tokyo Night Light"));
      }
  }
  ```

- [ ] **Step 6: 实现 `src-tauri/src/commands/settings.rs`（骨架）**

  ```rust
  use crate::error::AppError;
  use serde::{Deserialize, Serialize};
  use specta::Type;

  /// 应用配置骨架（M1 只含主题相关字段，后续里程碑扩充）
  #[derive(Debug, Clone, Serialize, Deserialize, Type)]
  pub struct AppConfig {
      pub theme: String,
      pub language: String,
  }

  impl Default for AppConfig {
      fn default() -> Self {
          Self {
              theme: "Tokyo Night".to_string(),
              language: "en".to_string(),
          }
      }
  }

  /// 获取应用配置骨架（M1 返回默认值，M3+ 从磁盘读取）
  #[tauri::command]
  #[specta::specta]
  pub async fn get_app_config() -> Result<AppConfig, AppError> {
      Ok(AppConfig::default())
  }

  #[cfg(test)]
  mod tests {
      use super::*;

      #[tokio::test]
      async fn test_get_app_config_defaults() {
          let config = get_app_config().await.unwrap();
          assert_eq!(config.theme, "Tokyo Night");
          assert_eq!(config.language, "en");
      }
  }
  ```

- [ ] **Step 7: 实现 `src-tauri/src/lib.rs`（启动骨架）**

  ```rust
  mod commands;
  mod error;
  mod state;

  use commands::{settings, theme};
  use state::AppState;
  use tauri_specta::{collect_commands, Builder};

  /// tauri-specta builder（构建时自动导出 bindings.ts）
  fn specta_builder() -> Builder {
      Builder::<tauri::Wry>::new()
          .commands(collect_commands![
              theme::get_current_theme,
              theme::set_current_theme,
              theme::list_builtin_themes,
              settings::get_app_config,
          ])
  }

  /// 仅在开发构建时重新生成 bindings.ts
  #[cfg(debug_assertions)]
  fn export_bindings() {
      specta_builder()
          .export(
              specta_typescript::Typescript::default(),
              "../src/lib/bindings.ts",
          )
          .expect("Failed to export TypeScript bindings");
  }

  #[cfg_attr(mobile, tauri::mobile_entry_point)]
  pub fn run() {
      #[cfg(debug_assertions)]
      export_bindings();

      let app_state = AppState::new();

      tauri::Builder::default()
          .manage(app_state)
          .invoke_handler(
              specta_builder().invoke_handler()
          )
          .run(tauri::generate_context!())
          .expect("error while running tauri application");
  }
  ```

- [ ] **Step 8: 运行 Rust 测试**

  ```bash
  cd src-tauri && cargo test 2>&1 | tail -20
  ```

  预期输出：所有测试 `ok`，无编译错误。

- [ ] **Commit**

  ```bash
  git add src-tauri/
  git commit -m "feat(m1): add AppState skeleton, AppError, and IPC command stubs"
  ```

---

### Task 3: tauri-specta v2 IPC 脚手架（bindings.ts 自动生成）

**Files:**
- Create: `src/lib/bindings.ts`（由 Rust 自动生成，不手写业务逻辑）
- Create: `src/lib/utils.ts`
- Create: `src/test-setup.ts`

- [ ] **Step 1: 创建 `src/lib/utils.ts`**

  ```typescript
  import { type ClassValue, clsx } from "clsx";
  import { twMerge } from "tailwind-merge";

  /** shadcn/ui 标准 cn 工具函数 */
  export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
  }
  ```

- [ ] **Step 2: 创建测试设置文件 `src/test-setup.ts`**

  ```typescript
  import "@testing-library/jest-dom";

  // Mock Tauri IPC（防止测试环境调用原生 API）
  vi.mock("@tauri-apps/api/core", () => ({
    invoke: vi.fn(),
  }));

  vi.mock("@tauri-apps/api/event", () => ({
    listen: vi.fn(() => Promise.resolve(() => {})),
    emit: vi.fn(),
  }));
  ```

- [ ] **Step 3: 触发首次 `bindings.ts` 生成**

  ```bash
  # 以开发模式启动 Tauri（会触发 export_bindings()），
  # 生成 src/lib/bindings.ts 后立即 Ctrl+C 终止
  npm run tauri dev &
  sleep 15
  kill %1 2>/dev/null || true

  # 验证文件已生成
  ls -la src/lib/bindings.ts
  ```

  > 如果自动生成失败（CI 环境无 display），可手动运行：
  > ```bash
  > cd src-tauri && cargo test export_bindings -- --ignored
  > ```

- [ ] **Step 4: 提交 `bindings.ts`（生成结果纳入版本控制，供 CI 使用）**

  注意：`bindings.ts` 是自动生成文件，顶部应含 `// This file was generated by [tauri-specta](...)` 注释。将该文件加入 `.gitattributes` 标记为生成文件：

  在 `.gitattributes` 中添加：
  ```
  src/lib/bindings.ts linguist-generated=true
  ```

- [ ] **Step 5: 为 `bindings.ts` 写 smoke 测试**

  创建 `src/lib/__tests__/bindings.test.ts`：

  ```typescript
  import { describe, it, expect, vi } from "vitest";

  // 验证 bindings.ts 导出预期的命令函数
  describe("bindings smoke test", () => {
    it("exports get_current_theme command", async () => {
      const bindings = await import("../bindings");
      expect(typeof bindings.commands.getCurrentTheme).toBe("function");
    });

    it("exports set_current_theme command", async () => {
      const bindings = await import("../bindings");
      expect(typeof bindings.commands.setCurrentTheme).toBe("function");
    });

    it("exports list_builtin_themes command", async () => {
      const bindings = await import("../bindings");
      expect(typeof bindings.commands.listBuiltinThemes).toBe("function");
    });
  });
  ```

- [ ] **Commit**

  ```bash
  git add src/lib/ .gitattributes
  git commit -m "feat(m1): add tauri-specta bindings scaffold and IPC utils"
  ```

---

### Task 4: Tailwind CSS v3 + shadcn/ui 配置

**Files:**
- Create: `tailwind.config.ts`
- Create: `postcss.config.js`
- Create: `src/styles/globals.css`
- Create: `components.json`（shadcn/ui 配置）
- Create: `src/components/ui/button.tsx`（shadcn/ui CLI 生成示例）
- Create: `src/components/ui/separator.tsx`
- Create: `src/components/ui/tooltip.tsx`

- [ ] **Step 1: 写入 `tailwind.config.ts`（含主题 CSS 变量映射）**

  ```typescript
  import type { Config } from "tailwindcss";

  const config: Config = {
    darkMode: ["class", '[data-theme-type="dark"]'],
    content: [
      "./index.html",
      "./src/**/*.{ts,tsx}",
    ],
    theme: {
      extend: {
        colors: {
          bg: {
            primary:   "var(--color-bg-primary)",
            secondary: "var(--color-bg-secondary)",
            sidebar:   "var(--color-bg-sidebar)",
            input:     "var(--color-bg-input)",
            hover:     "var(--color-bg-hover)",
            selection: "var(--color-bg-selection)",
          },
          text: {
            primary:   "var(--color-text-primary)",
            secondary: "var(--color-text-secondary)",
            muted:     "var(--color-text-muted)",
            disabled:  "var(--color-text-disabled)",
          },
          accent: {
            DEFAULT: "var(--color-accent-primary)",
            hover:   "var(--color-accent-hover)",
            muted:   "var(--color-accent-muted)",
          },
          border: {
            DEFAULT: "var(--color-border-default)",
            focus:   "var(--color-border-focus)",
          },
          status: {
            error:   "var(--color-status-error)",
            warning: "var(--color-status-warning)",
            success: "var(--color-status-success)",
            info:    "var(--color-status-info)",
          },
        },
        fontFamily: {
          sans: [
            "-apple-system",
            "BlinkMacSystemFont",
            '"Segoe UI"',
            "Roboto",
            "sans-serif",
          ],
          mono: [
            '"JetBrains Mono"',
            '"Fira Code"',
            "Menlo",
            "Monaco",
            "Consolas",
            "monospace",
          ],
        },
        borderRadius: {
          sm: "4px",
          md: "6px",
          lg: "8px",
        },
      },
    },
    plugins: [],
  };

  export default config;
  ```

- [ ] **Step 2: 写入 `postcss.config.js`**

  ```javascript
  export default {
    plugins: {
      tailwindcss: {},
      autoprefixer: {},
    },
  };
  ```

- [ ] **Step 3: 写入 `src/styles/globals.css`（Tailwind base + CSS 变量定义）**

  ```css
  @tailwind base;
  @tailwind components;
  @tailwind utilities;

  /* ============================================================
     CSS 变量语义层定义（默认 = Tokyo Night，由 ThemeProvider 覆盖）
     规则：不在组件中直接写颜色值，只写 Tailwind 工具类
     ============================================================ */
  :root {
    /* 背景层 */
    --color-bg-primary:   #1a1b26;
    --color-bg-secondary: #16161e;
    --color-bg-sidebar:   #13131a;
    --color-bg-input:     #14141b;
    --color-bg-hover:     #202330;
    --color-bg-selection: #3d59a144;

    /* 文本层 */
    --color-text-primary:   #c0caf5;
    --color-text-secondary: #787c99;
    --color-text-muted:     #515670;
    --color-text-disabled:  #545c7e;

    /* 强调色 */
    --color-accent-primary: #7aa2f7;
    --color-accent-hover:   #3d59a1;
    --color-accent-muted:   #3d59a144;

    /* 边框 */
    --color-border-default: #29355a;
    --color-border-focus:   #545c7e33;

    /* 状态色 */
    --color-status-error:   #f7768e;
    --color-status-warning: #e0af68;
    --color-status-success: #9ece6a;
    --color-status-info:    #2ac3de;

    /* 布局尺寸变量（不随主题变化） */
    --activity-bar-width: 48px;
    --second-panel-width: 240px;
    --second-panel-min:   160px;
    --second-panel-max:   480px;
    --top-bar-height:     40px;
    --status-bar-height:  24px;
  }

  /* 基础重置 */
  *,
  *::before,
  *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  html,
  body,
  #root {
    height: 100%;
    overflow: hidden;
  }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 13px;
    line-height: 1.5;
    background-color: var(--color-bg-primary);
    color: var(--color-text-primary);
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    user-select: none;
  }

  /* 滚动条样式 */
  ::-webkit-scrollbar {
    width: 6px;
    height: 6px;
  }
  ::-webkit-scrollbar-track {
    background: transparent;
  }
  ::-webkit-scrollbar-thumb {
    background: var(--color-border-default);
    border-radius: 3px;
  }
  ::-webkit-scrollbar-thumb:hover {
    background: var(--color-text-muted);
  }
  ```

- [ ] **Step 4: 写入 `components.json`（shadcn/ui 配置）**

  ```json
  {
    "$schema": "https://ui.shadcn.com/schema.json",
    "style": "default",
    "rsc": false,
    "tsx": true,
    "tailwind": {
      "config": "tailwind.config.ts",
      "css": "src/styles/globals.css",
      "baseColor": "slate",
      "cssVariables": false,
      "prefix": ""
    },
    "aliases": {
      "components": "@/components",
      "utils": "@/lib/utils"
    }
  }
  ```

- [ ] **Step 5: 使用 shadcn/ui CLI 添加基础组件**

  ```bash
  # 添加 Button（ActivityBar icon button 会用到）
  npx shadcn@latest add button --yes

  # 添加 Separator（StatusBar / SecondPanel 分割线）
  npx shadcn@latest add separator --yes

  # 添加 Tooltip（ActivityBar 图标 hover 提示）
  npx shadcn@latest add tooltip --yes
  ```

- [ ] **Step 6: 为 `cn` 工具函数写测试**

  创建 `src/lib/__tests__/utils.test.ts`：

  ```typescript
  import { describe, it, expect } from "vitest";
  import { cn } from "../utils";

  describe("cn", () => {
    it("merges class names", () => {
      expect(cn("a", "b")).toBe("a b");
    });

    it("resolves tailwind conflicts (last wins)", () => {
      expect(cn("p-2", "p-4")).toBe("p-4");
    });

    it("handles conditional classes", () => {
      expect(cn("base", false && "hidden", "visible")).toBe("base visible");
    });

    it("handles undefined and null", () => {
      expect(cn("base", undefined, null)).toBe("base");
    });
  });
  ```

- [ ] **Step 7: 运行前端测试**

  ```bash
  npx vitest run src/lib/__tests__/utils.test.ts
  ```

- [ ] **Commit**

  ```bash
  git add tailwind.config.ts postcss.config.js src/styles/ components.json src/components/ui/
  git commit -m "feat(m1): configure Tailwind CSS v3 with theme CSS variables and add shadcn/ui base components"
  ```

---

### Task 5: 主题系统（CSS 变量 + Tokyo Night 主题 + ThemeProvider + useThemeStore）

**Files:**
- Create: `src/styles/themes/tokyo-night.css`
- Create: `src/styles/themes/tokyo-night-storm.css`
- Create: `src/styles/themes/tokyo-night-light.css`
- Create: `src/store/theme.ts`
- Create: `src/components/providers/ThemeProvider.tsx`
- Create: `src/store/__tests__/theme.test.ts`
- Create: `src/components/providers/__tests__/ThemeProvider.test.tsx`

- [ ] **Step 1: 写主题测试（TDD，先写）**

  创建 `src/store/__tests__/theme.test.ts`：

  ```typescript
  import { describe, it, expect, beforeEach } from "vitest";
  import { act, renderHook } from "@testing-library/react";
  import { useThemeStore } from "../theme";

  describe("useThemeStore", () => {
    beforeEach(() => {
      // 重置 store 到初始状态
      useThemeStore.setState({
        currentTheme: "Tokyo Night",
        themes: [],
      });
    });

    it("has default theme Tokyo Night", () => {
      const { result } = renderHook(() => useThemeStore());
      expect(result.current.currentTheme).toBe("Tokyo Night");
    });

    it("setTheme updates currentTheme", () => {
      const { result } = renderHook(() => useThemeStore());
      act(() => {
        result.current.setTheme("Tokyo Night Storm");
      });
      expect(result.current.currentTheme).toBe("Tokyo Night Storm");
    });
  });
  ```

- [ ] **Step 2: 创建 `src/store/theme.ts`**

  ```typescript
  import { create } from "zustand";
  import { persist } from "zustand/middleware";

  /** 主题元信息（不含完整 token 数据） */
  export interface ThemeInfo {
    name: string;
    type: "dark" | "light";
  }

  /** 主题 JSON 文件的 semanticTokens 定义（与 resources/themes/*.json 格式一致） */
  export interface ThemeTokens {
    name: string;
    type: "dark" | "light";
    semanticTokens: Record<string, string>;
  }

  interface ThemeState {
    /** 当前激活主题名称 */
    currentTheme: string;
    /** 已加载的主题元信息列表 */
    themes: ThemeInfo[];
    /** 设置当前主题（触发 ThemeProvider 更新 CSS 变量） */
    setTheme: (name: string) => void;
    /** 注册可用主题（由 ThemeProvider 初始化时调用） */
    registerThemes: (themes: ThemeInfo[]) => void;
  }

  export const useThemeStore = create<ThemeState>()(
    persist(
      (set) => ({
        currentTheme: "Tokyo Night",
        themes: [],
        setTheme: (name) => set({ currentTheme: name }),
        registerThemes: (themes) => set({ themes }),
      }),
      {
        name: "echonote-theme",
        // 只持久化 currentTheme，themes 列表在每次启动时重新加载
        partialize: (state) => ({ currentTheme: state.currentTheme }),
      }
    )
  );
  ```

- [ ] **Step 3: 创建内置主题 CSS 文件**

  创建 `src/styles/themes/tokyo-night.css`（与 `globals.css` 中 `:root` 默认值保持一致，作为显式声明）：

  ```css
  /* Tokyo Night — https://github.com/enkia/tokyo-night-vscode-theme */
  [data-theme="tokyo-night"] {
    --color-bg-primary:   #1a1b26;
    --color-bg-secondary: #16161e;
    --color-bg-sidebar:   #13131a;
    --color-bg-input:     #14141b;
    --color-bg-hover:     #202330;
    --color-bg-selection: #3d59a144;

    --color-text-primary:   #c0caf5;
    --color-text-secondary: #787c99;
    --color-text-muted:     #515670;
    --color-text-disabled:  #545c7e;

    --color-accent-primary: #7aa2f7;
    --color-accent-hover:   #3d59a1;
    --color-accent-muted:   #3d59a144;

    --color-border-default: #29355a;
    --color-border-focus:   #545c7e33;

    --color-status-error:   #f7768e;
    --color-status-warning: #e0af68;
    --color-status-success: #9ece6a;
    --color-status-info:    #2ac3de;
  }
  ```

  创建 `src/styles/themes/tokyo-night-storm.css`：

  ```css
  /* Tokyo Night Storm */
  [data-theme="tokyo-night-storm"] {
    --color-bg-primary:   #24283b;
    --color-bg-secondary: #1f2335;
    --color-bg-sidebar:   #1e2030;
    --color-bg-input:     #1b1e2e;
    --color-bg-hover:     #2d3149;
    --color-bg-selection: #3d59a144;

    --color-text-primary:   #c0caf5;
    --color-text-secondary: #737aa2;
    --color-text-muted:     #565f89;
    --color-text-disabled:  #545c7e;

    --color-accent-primary: #7aa2f7;
    --color-accent-hover:   #3d59a1;
    --color-accent-muted:   #3d59a144;

    --color-border-default: #29355a;
    --color-border-focus:   #545c7e33;

    --color-status-error:   #f7768e;
    --color-status-warning: #e0af68;
    --color-status-success: #9ece6a;
    --color-status-info:    #2ac3de;
  }
  ```

  创建 `src/styles/themes/tokyo-night-light.css`：

  ```css
  /* Tokyo Night Light */
  [data-theme="tokyo-night-light"] {
    --color-bg-primary:   #d5d6db;
    --color-bg-secondary: #cbccd1;
    --color-bg-sidebar:   #c4c5cc;
    --color-bg-input:     #d0d1d8;
    --color-bg-hover:     #bbbcc2;
    --color-bg-selection: #7890dd44;

    --color-text-primary:   #343b58;
    --color-text-secondary: #6172b0;
    --color-text-muted:     #8990b3;
    --color-text-disabled:  #9699b0;

    --color-accent-primary: #2959aa;
    --color-accent-hover:   #7890dd;
    --color-accent-muted:   #7890dd44;

    --color-border-default: #a8aecb;
    --color-border-focus:   #9699b033;

    --color-status-error:   #8c4351;
    --color-status-warning: #8f5e15;
    --color-status-success: #485e30;
    --color-status-info:    #0f4b6e;
  }
  ```

- [ ] **Step 4: 创建 `src/components/providers/ThemeProvider.tsx`**

  ```typescript
  import { useEffect } from "react";
  import { useThemeStore, type ThemeInfo } from "@/store/theme";

  /** 将主题名称转换为 data-theme 属性值（与 CSS 选择器一致） */
  function themeNameToSlug(name: string): string {
    return name.toLowerCase().replace(/\s+/g, "-");
  }

  const BUILTIN_THEMES: ThemeInfo[] = [
    { name: "Tokyo Night",       type: "dark" },
    { name: "Tokyo Night Storm", type: "dark" },
    { name: "Tokyo Night Light", type: "light" },
  ];

  interface ThemeProviderProps {
    children: React.ReactNode;
  }

  /**
   * ThemeProvider — 负责将 currentTheme 同步到 document.documentElement 的
   * data-theme 和 data-theme-type 属性，驱动 CSS 变量切换。
   *
   * 放在组件树最外层（App.tsx），只渲染一次。
   */
  export function ThemeProvider({ children }: ThemeProviderProps) {
    const { currentTheme, registerThemes } = useThemeStore();

    // 初始化：注册内置主题列表
    useEffect(() => {
      registerThemes(BUILTIN_THEMES);
    }, [registerThemes]);

    // 主题切换：更新 DOM 属性
    useEffect(() => {
      const root = document.documentElement;
      const slug = themeNameToSlug(currentTheme);
      const themeInfo = BUILTIN_THEMES.find((t) => t.name === currentTheme);

      root.setAttribute("data-theme", slug);
      root.setAttribute("data-theme-type", themeInfo?.type ?? "dark");
    }, [currentTheme]);

    return <>{children}</>;
  }
  ```

- [ ] **Step 5: 为 ThemeProvider 写测试**

  创建 `src/components/providers/__tests__/ThemeProvider.test.tsx`：

  ```typescript
  import { describe, it, expect, beforeEach } from "vitest";
  import { render } from "@testing-library/react";
  import { ThemeProvider } from "../ThemeProvider";
  import { useThemeStore } from "@/store/theme";
  import { act } from "react";

  describe("ThemeProvider", () => {
    beforeEach(() => {
      useThemeStore.setState({ currentTheme: "Tokyo Night", themes: [] });
      document.documentElement.removeAttribute("data-theme");
      document.documentElement.removeAttribute("data-theme-type");
    });

    it("sets data-theme on mount", () => {
      render(<ThemeProvider><div /></ThemeProvider>);
      expect(document.documentElement.getAttribute("data-theme"))
        .toBe("tokyo-night");
    });

    it("sets data-theme-type dark for Tokyo Night", () => {
      render(<ThemeProvider><div /></ThemeProvider>);
      expect(document.documentElement.getAttribute("data-theme-type"))
        .toBe("dark");
    });

    it("updates data-theme when store changes", () => {
      render(<ThemeProvider><div /></ThemeProvider>);
      act(() => {
        useThemeStore.getState().setTheme("Tokyo Night Light");
      });
      expect(document.documentElement.getAttribute("data-theme"))
        .toBe("tokyo-night-light");
      expect(document.documentElement.getAttribute("data-theme-type"))
        .toBe("light");
    });
  });
  ```

- [ ] **Step 6: 运行主题相关测试**

  ```bash
  npx vitest run src/store/__tests__/theme.test.ts \
                 src/components/providers/__tests__/ThemeProvider.test.tsx
  ```

- [ ] **Commit**

  ```bash
  git add src/styles/themes/ src/store/theme.ts src/components/providers/
  git commit -m "feat(m1): add theme system with ThemeProvider, useThemeStore, and Tokyo Night variants"
  ```

---

### Task 6: TanStack Router 路由骨架（5 个页面占位）

**Files:**
- Create: `src/router.tsx`
- Create: `src/routes/__root.tsx`
- Create: `src/routes/recording.tsx`
- Create: `src/routes/transcription.tsx`
- Create: `src/routes/workspace.tsx`
- Create: `src/routes/timeline.tsx`
- Create: `src/routes/settings.tsx`
- Create: `src/routes/index.tsx`（重定向到 /recording）
- Create: `src/App.tsx`
- Modify: `src/main.tsx`

- [ ] **Step 1: 安装 TanStack Router 所需的 Vite 插件**

  ```bash
  npm install -D @tanstack/router-vite-plugin
  ```

  修改 `vite.config.ts`，在 plugins 数组中添加：

  ```typescript
  import { TanStackRouterVite } from "@tanstack/router-vite-plugin";

  // plugins 数组改为：
  plugins: [react(), TanStackRouterVite()],
  ```

  > TanStack Router Vite 插件会自动扫描 `src/routes/` 目录生成 `src/routeTree.gen.ts`（不手写）。

- [ ] **Step 2: 创建 `src/routes/__root.tsx`（根路由，包含 Shell 布局）**

  ```typescript
  import { createRootRoute, Outlet } from "@tanstack/react-router";
  import { Shell } from "@/components/layout/Shell";

  export const Route = createRootRoute({
    component: () => (
      <Shell>
        <Outlet />
      </Shell>
    ),
  });
  ```

- [ ] **Step 3: 创建重定向路由 `src/routes/index.tsx`**

  ```typescript
  import { createFileRoute, redirect } from "@tanstack/react-router";

  export const Route = createFileRoute("/")({
    beforeLoad: () => {
      throw redirect({ to: "/recording" });
    },
  });
  ```

- [ ] **Step 4: 创建各页面占位路由**

  创建 `src/routes/recording.tsx`：

  ```typescript
  import { createFileRoute } from "@tanstack/react-router";

  export const Route = createFileRoute("/recording")({
    component: RecordingPage,
  });

  function RecordingPage() {
    return (
      <div className="flex h-full items-center justify-center text-text-muted">
        <p>Recording — Coming in M2</p>
      </div>
    );
  }
  ```

  创建 `src/routes/transcription.tsx`：

  ```typescript
  import { createFileRoute } from "@tanstack/react-router";

  export const Route = createFileRoute("/transcription")({
    component: TranscriptionPage,
  });

  function TranscriptionPage() {
    return (
      <div className="flex h-full items-center justify-center text-text-muted">
        <p>Transcription — Coming in M2</p>
      </div>
    );
  }
  ```

  创建 `src/routes/workspace.tsx`：

  ```typescript
  import { createFileRoute } from "@tanstack/react-router";

  export const Route = createFileRoute("/workspace")({
    component: WorkspacePage,
  });

  function WorkspacePage() {
    return (
      <div className="flex h-full items-center justify-center text-text-muted">
        <p>Workspace — Coming in M4</p>
      </div>
    );
  }
  ```

  创建 `src/routes/timeline.tsx`：

  ```typescript
  import { createFileRoute } from "@tanstack/react-router";

  export const Route = createFileRoute("/timeline")({
    component: TimelinePage,
  });

  function TimelinePage() {
    return (
      <div className="flex h-full items-center justify-center text-text-muted">
        <p>Timeline — Coming in M4</p>
      </div>
    );
  }
  ```

  创建 `src/routes/settings.tsx`：

  ```typescript
  import { createFileRoute } from "@tanstack/react-router";

  export const Route = createFileRoute("/settings")({
    component: SettingsPage,
  });

  function SettingsPage() {
    return (
      <div className="flex h-full items-center justify-center text-text-muted">
        <p>Settings — Coming in M5</p>
      </div>
    );
  }
  ```

- [ ] **Step 5: 创建 `src/router.tsx`**

  ```typescript
  import { createRouter } from "@tanstack/react-router";
  import { routeTree } from "./routeTree.gen";

  export const router = createRouter({
    routeTree,
    defaultPreload: "intent",
  });

  // 类型注册（TanStack Router 类型安全要求）
  declare module "@tanstack/react-router" {
    interface Register {
      router: typeof router;
    }
  }
  ```

- [ ] **Step 6: 创建 `src/App.tsx`**

  ```typescript
  import { RouterProvider } from "@tanstack/react-router";
  import { ThemeProvider } from "@/components/providers/ThemeProvider";
  import { router } from "./router";

  export function App() {
    return (
      <ThemeProvider>
        <RouterProvider router={router} />
      </ThemeProvider>
    );
  }
  ```

- [ ] **Step 7: 更新 `src/main.tsx`**

  ```typescript
  import React from "react";
  import ReactDOM from "react-dom/client";
  import { App } from "./App";
  import "./styles/globals.css";
  import "./styles/themes/tokyo-night.css";
  import "./styles/themes/tokyo-night-storm.css";
  import "./styles/themes/tokyo-night-light.css";

  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
  ```

- [ ] **Step 8: 为路由写集成测试**

  创建 `src/routes/__tests__/routing.test.tsx`：

  ```typescript
  import { describe, it, expect } from "vitest";
  import { render, screen } from "@testing-library/react";
  import {
    createMemoryHistory,
    createRouter,
    RouterProvider,
  } from "@tanstack/react-router";
  import { routeTree } from "../../routeTree.gen";

  function renderWithRouter(initialPath: string) {
    const memoryHistory = createMemoryHistory({ initialEntries: [initialPath] });
    const testRouter = createRouter({ routeTree, history: memoryHistory });
    return render(<RouterProvider router={testRouter} />);
  }

  describe("routing", () => {
    it("redirects / to /recording", async () => {
      renderWithRouter("/");
      // 等待路由 redirect 完成
      await screen.findByText(/recording/i);
    });

    it("renders transcription page at /transcription", async () => {
      renderWithRouter("/transcription");
      await screen.findByText(/transcription/i);
    });
  });
  ```

- [ ] **Step 9: 运行路由测试**

  ```bash
  npx vitest run src/routes/__tests__/routing.test.tsx
  ```

- [ ] **Commit**

  ```bash
  git add src/routes/ src/router.tsx src/App.tsx src/main.tsx src/routeTree.gen.ts
  git commit -m "feat(m1): add TanStack Router skeleton with 5 page route placeholders"
  ```

---

### Task 7: 应用布局（Shell + ActivityBar + SecondPanel + TopBar + StatusBar）

**Files:**
- Create: `src/components/layout/Shell.tsx`
- Create: `src/components/layout/ActivityBar.tsx`
- Create: `src/components/layout/SecondPanel.tsx`
- Create: `src/components/layout/TopBar.tsx`
- Create: `src/components/layout/StatusBar.tsx`
- Create: `src/components/layout/__tests__/Shell.test.tsx`
- Create: `src/components/layout/__tests__/SecondPanel.test.tsx`
- Create: `src/components/layout/__tests__/ActivityBar.test.tsx`

- [ ] **Step 1: 先写 Shell 测试（TDD）**

  创建 `src/components/layout/__tests__/Shell.test.tsx`：

  ```typescript
  import { describe, it, expect } from "vitest";
  import { render, screen } from "@testing-library/react";
  import { MemoryRouter } from "@tanstack/react-router";
  import { Shell } from "../Shell";

  describe("Shell", () => {
    it("renders activity bar", () => {
      render(
        <Shell>
          <div data-testid="content">content</div>
        </Shell>
      );
      expect(screen.getByRole("navigation", { name: /activity bar/i }))
        .toBeInTheDocument();
    });

    it("renders children in main content area", () => {
      render(
        <Shell>
          <div data-testid="content">hello</div>
        </Shell>
      );
      expect(screen.getByTestId("content")).toBeInTheDocument();
    });

    it("renders status bar", () => {
      render(
        <Shell>
          <div />
        </Shell>
      );
      expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    });
  });
  ```

- [ ] **Step 2: 创建 `src/components/layout/ActivityBar.tsx`**

  ```typescript
  import { Link, useRouterState } from "@tanstack/react-router";
  import { cn } from "@/lib/utils";
  import {
    Mic,
    FileText,
    FolderOpen,
    CalendarDays,
    Settings,
  } from "lucide-react";

  interface NavItem {
    to: string;
    icon: React.ComponentType<{ className?: string }>;
    label: string;
  }

  const NAV_ITEMS: NavItem[] = [
    { to: "/recording",      icon: Mic,          label: "Recording" },
    { to: "/transcription",  icon: FileText,      label: "Transcription" },
    { to: "/workspace",      icon: FolderOpen,    label: "Workspace" },
    { to: "/timeline",       icon: CalendarDays,  label: "Timeline" },
  ];

  export function ActivityBar() {
    const { location } = useRouterState();

    return (
      <nav
        aria-label="Activity bar"
        className="flex flex-col items-center justify-between h-full bg-bg-sidebar border-r border-border-default"
        style={{ width: "var(--activity-bar-width)", minWidth: "var(--activity-bar-width)" }}
      >
        {/* 主导航图标 */}
        <div className="flex flex-col items-center gap-1 pt-2">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => {
            const isActive = location.pathname.startsWith(to);
            return (
              <Link
                key={to}
                to={to}
                aria-label={label}
                title={label}
                className={cn(
                  "flex items-center justify-center w-10 h-10 rounded-md transition-colors",
                  "text-text-secondary hover:text-text-primary hover:bg-bg-hover",
                  isActive && "text-accent border-l-2 border-accent bg-bg-hover"
                )}
              >
                <Icon className="w-5 h-5" />
              </Link>
            );
          })}
        </div>

        {/* 底部设置图标 */}
        <div className="pb-2">
          <Link
            to="/settings"
            aria-label="Settings"
            title="Settings"
            className={cn(
              "flex items-center justify-center w-10 h-10 rounded-md transition-colors",
              "text-text-secondary hover:text-text-primary hover:bg-bg-hover",
              location.pathname.startsWith("/settings") && "text-accent"
            )}
          >
            <Settings className="w-5 h-5" />
          </Link>
        </div>
      </nav>
    );
  }
  ```

- [ ] **Step 3: 创建 `src/components/layout/TopBar.tsx`**

  ```typescript
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
        {/* TODO(M2): 录音状态指示灯 */}
        {/* TODO(M2): 面包屑导航 */}
      </div>
    );
  }
  ```

- [ ] **Step 4: 创建 `src/components/layout/StatusBar.tsx`**

  ```typescript
  export function StatusBar() {
    return (
      <footer
        role="contentinfo"
        aria-label="Status bar"
        className="flex items-center justify-between px-3 bg-bg-sidebar border-t border-border-default text-xs text-text-muted shrink-0"
        style={{ height: "var(--status-bar-height)" }}
      >
        <div className="flex items-center gap-3">
          {/* TODO(M2): 模型状态 */}
          <span>EchoNote v3.0.0</span>
        </div>
        <div className="flex items-center gap-3">
          {/* TODO(M2): 音频电平 */}
          {/* TODO(M5): 语言选择 */}
        </div>
      </footer>
    );
  }
  ```

- [ ] **Step 5: 创建 `src/components/layout/SecondPanel.tsx`（可拖拽宽度）**

  ```typescript
  import { useRef, useState, useCallback, useEffect } from "react";
  import { cn } from "@/lib/utils";

  interface SecondPanelProps {
    children: React.ReactNode;
    defaultWidth?: number;
    minWidth?: number;
    maxWidth?: number;
    /** 是否允许完全折叠（宽度 = 0） */
    collapsible?: boolean;
  }

  /**
   * SecondPanel — 可拖拽宽度的次级面板。
   * 用鼠标拖拽右侧分隔线调整宽度；双击分隔线恢复默认宽度。
   */
  export function SecondPanel({
    children,
    defaultWidth = 240,
    minWidth = 160,
    maxWidth = 480,
    collapsible = true,
  }: SecondPanelProps) {
    const [width, setWidth] = useState(defaultWidth);
    const [isCollapsed, setIsCollapsed] = useState(false);
    const isDragging = useRef(false);
    const startX = useRef(0);
    const startWidth = useRef(0);

    const onMouseDown = useCallback(
      (e: React.MouseEvent) => {
        e.preventDefault();
        isDragging.current = true;
        startX.current = e.clientX;
        startWidth.current = width;
        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";
      },
      [width]
    );

    const onDoubleClick = useCallback(() => {
      if (collapsible) {
        setIsCollapsed((prev) => !prev);
      } else {
        setWidth(defaultWidth);
      }
    }, [collapsible, defaultWidth]);

    useEffect(() => {
      const onMouseMove = (e: MouseEvent) => {
        if (!isDragging.current) return;
        const delta = e.clientX - startX.current;
        const newWidth = Math.max(minWidth, Math.min(maxWidth, startWidth.current + delta));
        setWidth(newWidth);
        if (newWidth <= minWidth && collapsible) {
          setIsCollapsed(true);
        } else {
          setIsCollapsed(false);
        }
      };

      const onMouseUp = () => {
        if (!isDragging.current) return;
        isDragging.current = false;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      };

      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
      return () => {
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
      };
    }, [minWidth, maxWidth, collapsible]);

    const panelWidth = isCollapsed ? 0 : width;

    return (
      <div className="relative flex h-full shrink-0">
        {/* 面板内容区 */}
        <div
          className={cn(
            "flex flex-col h-full overflow-hidden bg-bg-secondary border-r border-border-default transition-none",
            isCollapsed && "border-r-0"
          )}
          style={{ width: panelWidth, minWidth: panelWidth }}
          aria-hidden={isCollapsed}
        >
          {children}
        </div>

        {/* 拖拽分隔线 */}
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize panel"
          className={cn(
            "absolute right-0 top-0 h-full w-1 cursor-col-resize",
            "hover:bg-accent/30 active:bg-accent/50 transition-colors",
            "z-10"
          )}
          style={{ transform: "translateX(50%)" }}
          onMouseDown={onMouseDown}
          onDoubleClick={onDoubleClick}
        />
      </div>
    );
  }
  ```

- [ ] **Step 6: 创建 `src/components/layout/Shell.tsx`（顶层布局容器）**

  ```typescript
  import { ActivityBar } from "./ActivityBar";
  import { SecondPanel } from "./SecondPanel";
  import { TopBar } from "./TopBar";
  import { StatusBar } from "./StatusBar";

  interface ShellProps {
    children: React.ReactNode;
  }

  /**
   * Shell — 应用顶层布局骨架。
   *
   * 布局结构（对标 Obsidian/AnythingLLM）：
   * ┌──────┬────────────────────────────────────┐
   * │  AB  │  TopBar                            │
   * │      ├──────────┬─────────────────────────┤
   * │      │  Second  │  MainContent (children) │
   * │      │  Panel   │                         │
   * │      ├──────────┴─────────────────────────┤
   * │      │  StatusBar                         │
   * └──────┴────────────────────────────────────┘
   *
   * AB = ActivityBar（固定宽度 48px）
   * SecondPanel（可拖拽 160-480px）
   * MainContent = 路由出口（flex-1，占满剩余空间）
   */
  export function Shell({ children }: ShellProps) {
    return (
      <div className="flex h-screen overflow-hidden bg-bg-primary text-text-primary">
        {/* 左侧活动栏（固定宽度） */}
        <ActivityBar />

        {/* 右侧主区域（纵向分为 TopBar + 内容区 + StatusBar） */}
        <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
          {/* 顶部操作栏 */}
          <TopBar />

          {/* 中部内容区（SecondPanel + MainContent 并排） */}
          <div className="flex flex-1 min-h-0 overflow-hidden">
            {/* 可调宽二级面板（内容由各路由的 panel slot 填充，M1 为空） */}
            <SecondPanel>
              {/* TODO(M2+): 各功能页通过 route context 注入 panel 内容 */}
            </SecondPanel>

            {/* 主内容区：路由出口 */}
            <main className="flex-1 min-w-0 overflow-auto bg-bg-primary">
              {children}
            </main>
          </div>

          {/* 底部状态栏 */}
          <StatusBar />
        </div>
      </div>
    );
  }
  ```

- [ ] **Step 7: 为 SecondPanel 写可拖拽测试**

  创建 `src/components/layout/__tests__/SecondPanel.test.tsx`：

  ```typescript
  import { describe, it, expect } from "vitest";
  import { render, screen, fireEvent } from "@testing-library/react";
  import { SecondPanel } from "../SecondPanel";

  describe("SecondPanel", () => {
    it("renders children", () => {
      render(
        <SecondPanel>
          <div data-testid="panel-content">content</div>
        </SecondPanel>
      );
      expect(screen.getByTestId("panel-content")).toBeInTheDocument();
    });

    it("has a resize separator", () => {
      render(
        <SecondPanel>
          <div />
        </SecondPanel>
      );
      expect(screen.getByRole("separator")).toBeInTheDocument();
    });

    it("collapses on double-click when collapsible=true", () => {
      render(
        <SecondPanel collapsible defaultWidth={240}>
          <div data-testid="inner" />
        </SecondPanel>
      );
      const separator = screen.getByRole("separator");
      fireEvent.dblClick(separator);
      // 折叠后 panel 内容变为 aria-hidden
      expect(screen.getByTestId("inner").parentElement)
        .toHaveAttribute("aria-hidden", "true");
    });
  });
  ```

- [ ] **Step 8: 为 ActivityBar 写测试**

  创建 `src/components/layout/__tests__/ActivityBar.test.tsx`：

  ```typescript
  import { describe, it, expect } from "vitest";
  import { render, screen } from "@testing-library/react";
  import {
    createMemoryHistory,
    createRouter,
    RouterProvider,
  } from "@tanstack/react-router";
  import { routeTree } from "../../../routeTree.gen";

  function renderApp(initialPath = "/recording") {
    const history = createMemoryHistory({ initialEntries: [initialPath] });
    const router = createRouter({ routeTree, history });
    return render(<RouterProvider router={router} />);
  }

  describe("ActivityBar", () => {
    it("renders all 5 navigation links", async () => {
      renderApp();
      // 等待路由渲染完成
      await screen.findByRole("navigation", { name: /activity bar/i });
      expect(screen.getByRole("link", { name: /recording/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /transcription/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /workspace/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /timeline/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /settings/i })).toBeInTheDocument();
    });
  });
  ```

- [ ] **Step 9: 运行所有布局测试**

  ```bash
  npx vitest run src/components/layout/__tests__/
  ```

- [ ] **Commit**

  ```bash
  git add src/components/layout/
  git commit -m "feat(m1): implement Shell layout with ActivityBar, SecondPanel (draggable), TopBar, StatusBar"
  ```

---

### Task 8: 构建脚本 scripts/convert-themes.ts

**Files:**
- Create: `scripts/convert-themes.ts`
- Create: `resources/themes/tokyo-night.json`
- Create: `resources/themes/tokyo-night-storm.json`
- Create: `resources/themes/tokyo-night-light.json`

- [ ] **Step 1: 分析源主题 JSON 结构**

  `docs/themes/` 中的文件（VSCode 主题格式）含 `colors` 字段（UI 颜色）和 `semanticTokenColors` 字段（编辑器语法颜色）。

  转换脚本需要从 `colors` 字段提取对应的语义 token，映射到 EchoNote 的 `semanticTokens` 格式。

  关键映射规则（基于 Tokyo Night 分析）：
  ```
  editor.background           → bg.primary
  editor.foreground           → text.primary  (或 foreground)
  sideBar.background          → bg.sidebar
  input.background            → bg.input
  list.hoverBackground        → bg.hover
  editor.selectionBackground  → bg.selection
  foreground                  → text.secondary
  descriptionForeground       → text.muted
  disabledForeground          → text.disabled
  button.background           → accent.primary（去 alpha）
  button.hoverBackground      → accent.hover
  focusBorder                 → border.focus
  sash.hoverBorder            → border.default
  editorError.foreground      → status.error
  editorWarning.foreground    → status.warning
  gitDecoration.addedResourceForeground → status.success
  editorInfo.foreground       → status.info
  ```

- [ ] **Step 2: 写入 `scripts/convert-themes.ts`**

  ```typescript
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

  function convertTheme(srcPath: string): EchoNoteTheme {
    const raw = JSON.parse(fs.readFileSync(srcPath, "utf-8")) as VscodeTheme;
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

    return {
      name: raw.name,
      type: (raw.type === "light" ? "light" : "dark") as "dark" | "light",
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
  ```

- [ ] **Step 3: 在 `package.json` 中添加脚本**

  在 `package.json` 的 `scripts` 字段中添加：

  ```json
  "convert-themes": "tsx scripts/convert-themes.ts"
  ```

- [ ] **Step 4: 运行脚本生成主题 JSON 文件**

  ```bash
  npm run convert-themes
  ```

  预期输出：
  ```
  ✓ tokyo-night-color-theme.json → resources/themes/tokyo-night.json
  ✓ tokyo-night-light-color-theme.json → resources/themes/tokyo-night-light.json
  ✓ tokyo-night-storm-color-theme.json → resources/themes/tokyo-night-storm.json

  3 theme(s) converted successfully.
  ```

- [ ] **Step 5: 验证生成的 JSON 格式正确**

  ```bash
  # 检查每个文件是否含有必须字段
  node -e "
  const themes = ['resources/themes/tokyo-night.json',
                  'resources/themes/tokyo-night-storm.json',
                  'resources/themes/tokyo-night-light.json'];
  themes.forEach(f => {
    const t = JSON.parse(require('fs').readFileSync(f, 'utf-8'));
    const required = ['bg.primary','text.primary','accent.primary','border.default','status.error'];
    const missing = required.filter(k => !t.semanticTokens[k]);
    if (missing.length) console.error(f + ' missing: ' + missing.join(', '));
    else console.log('OK: ' + f);
  });
  "
  ```

- [ ] **Step 6: 为转换脚本写测试**

  创建 `scripts/__tests__/convert-themes.test.ts`：

  ```typescript
  import { describe, it, expect } from "vitest";
  import fs from "node:fs";
  import path from "node:path";

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
  ```

- [ ] **Step 7: 运行脚本测试**

  ```bash
  npx vitest run scripts/__tests__/convert-themes.test.ts
  ```

- [ ] **Commit**

  ```bash
  git add scripts/ resources/themes/
  git commit -m "feat(m1): add convert-themes script and generate Tokyo Night theme JSON files"
  ```

---

### Task 9: 端到端集成验证 + 收尾

**Files:**
- Create: `src/components/layout/__tests__/integration.test.tsx`（全布局集成测试）
- Modify: `package.json`（完善 scripts）

- [ ] **Step 1: 编写完整集成测试**

  创建 `src/components/layout/__tests__/integration.test.tsx`：

  ```typescript
  import { describe, it, expect } from "vitest";
  import { render, screen, waitFor } from "@testing-library/react";
  import {
    createMemoryHistory,
    createRouter,
    RouterProvider,
  } from "@tanstack/react-router";
  import { routeTree } from "../../../routeTree.gen";

  function renderApp(initialPath = "/recording") {
    const history = createMemoryHistory({ initialEntries: [initialPath] });
    const router = createRouter({ routeTree, history });
    return render(<RouterProvider router={router} />);
  }

  describe("M1 Integration: Shell + Router + Theme", () => {
    it("renders full app shell with all layout regions", async () => {
      renderApp();
      await waitFor(() => {
        expect(screen.getByRole("navigation", { name: /activity bar/i }))
          .toBeInTheDocument();
        expect(screen.getByRole("contentinfo"))
          .toBeInTheDocument(); // StatusBar
        expect(screen.getByRole("main"))
          .toBeInTheDocument();  // 主内容区
      });
    });

    it("default route redirects to /recording and shows placeholder", async () => {
      renderApp("/");
      await screen.findByText(/coming in m2/i);
    });

    it("navigating to /workspace shows workspace placeholder", async () => {
      renderApp("/workspace");
      await screen.findByText(/coming in m4/i);
    });

    it("navigating to /settings shows settings placeholder", async () => {
      renderApp("/settings");
      await screen.findByText(/coming in m5/i);
    });
  });
  ```

- [ ] **Step 2: 完善 `package.json` scripts**

  确保 `package.json` 的 `scripts` 字段包含：

  ```json
  {
    "scripts": {
      "dev":            "vite",
      "build":          "tsc && vite build",
      "preview":        "vite preview",
      "typecheck":      "tsc --noEmit",
      "test":           "vitest run",
      "test:watch":     "vitest",
      "test:ui":        "vitest --ui",
      "test:coverage":  "vitest run --coverage",
      "convert-themes": "tsx scripts/convert-themes.ts",
      "tauri":          "tauri"
    }
  }
  ```

- [ ] **Step 3: 运行所有前端测试**

  ```bash
  npm test 2>&1 | tail -30
  ```

  预期：所有测试通过，无失败（允许跳过涉及 Tauri 原生 API 的测试）。

- [ ] **Step 4: 运行所有 Rust 测试**

  ```bash
  cd src-tauri && cargo test -- --test-output immediate 2>&1 | tail -20
  ```

  预期：
  ```
  test error::tests::test_app_error_display_audio ... ok
  test error::tests::test_app_error_display_channel_closed ... ok
  test error::tests::test_app_error_serde_round_trip ... ok
  test state::tests::test_app_state_default_theme ... ok
  test commands::theme::tests::test_list_builtin_themes_returns_three ... ok
  test commands::settings::tests::test_get_app_config_defaults ... ok
  ```

- [ ] **Step 5: 启动 Tauri 开发模式，视觉验收**

  ```bash
  npm run tauri dev
  ```

  验收清单：
  - [ ] 应用窗口打开，背景为 Tokyo Night 深色（`#1a1b26`）
  - [ ] 左侧 ActivityBar 显示 5 个图标（Mic / FileText / FolderOpen / CalendarDays / Settings）
  - [ ] 点击各图标切换路由，TopBar 标题随之更新
  - [ ] SecondPanel 可通过拖拽分隔线调整宽度，双击可折叠
  - [ ] 底部 StatusBar 显示 "EchoNote v3.0.0"
  - [ ] 无 JavaScript 控制台错误

- [ ] **Step 6: 最终整体提交**

  ```bash
  git add -A
  git commit -m "feat(m1): complete M1 scaffold, theme system, and app layout

  - Tauri 2.x + React 18 + TypeScript initialized
  - Tailwind CSS v3 with CSS variable theme token architecture
  - shadcn/ui base components (Button, Separator, Tooltip)
  - TanStack Router with 5 page route placeholders
  - tauri-specta v2 bindings generation pipeline
  - Theme system: ThemeProvider, useThemeStore, Tokyo Night variants
  - App layout: Shell, ActivityBar, SecondPanel (draggable), TopBar, StatusBar
  - scripts/convert-themes.ts: docs/themes/ -> resources/themes/ conversion
  - AppState skeleton and lib.rs startup
  - AppError unified error type with tests
  - All Rust unit tests passing; all React/Vitest tests passing"
  ```

---

## 文件清单总览

| 类型 | 路径 |
|------|------|
| **Rust** | `src-tauri/Cargo.toml` |
| | `src-tauri/tauri.conf.json` |
| | `src-tauri/build.rs` |
| | `src-tauri/src/main.rs` |
| | `src-tauri/src/lib.rs` |
| | `src-tauri/src/state.rs` |
| | `src-tauri/src/error.rs` |
| | `src-tauri/src/commands/mod.rs` |
| | `src-tauri/src/commands/theme.rs` |
| | `src-tauri/src/commands/settings.rs` |
| **前端配置** | `package.json` |
| | `vite.config.ts` |
| | `tsconfig.json` |
| | `tsconfig.node.json` |
| | `tailwind.config.ts` |
| | `postcss.config.js` |
| | `components.json` |
| | `index.html` |
| **前端源码** | `src/main.tsx` |
| | `src/App.tsx` |
| | `src/router.tsx` |
| | `src/routeTree.gen.ts`（自动生成） |
| | `src/vite-env.d.ts` |
| | `src/test-setup.ts` |
| | `src/lib/bindings.ts`（自动生成） |
| | `src/lib/utils.ts` |
| | `src/store/theme.ts` |
| | `src/styles/globals.css` |
| | `src/styles/themes/tokyo-night.css` |
| | `src/styles/themes/tokyo-night-storm.css` |
| | `src/styles/themes/tokyo-night-light.css` |
| | `src/components/providers/ThemeProvider.tsx` |
| | `src/components/layout/Shell.tsx` |
| | `src/components/layout/ActivityBar.tsx` |
| | `src/components/layout/SecondPanel.tsx` |
| | `src/components/layout/TopBar.tsx` |
| | `src/components/layout/StatusBar.tsx` |
| | `src/routes/__root.tsx` |
| | `src/routes/index.tsx` |
| | `src/routes/recording.tsx` |
| | `src/routes/transcription.tsx` |
| | `src/routes/workspace.tsx` |
| | `src/routes/timeline.tsx` |
| | `src/routes/settings.tsx` |
| **测试** | `src/lib/__tests__/utils.test.ts` |
| | `src/lib/__tests__/bindings.test.ts` |
| | `src/store/__tests__/theme.test.ts` |
| | `src/components/providers/__tests__/ThemeProvider.test.tsx` |
| | `src/components/layout/__tests__/Shell.test.tsx` |
| | `src/components/layout/__tests__/SecondPanel.test.tsx` |
| | `src/components/layout/__tests__/ActivityBar.test.tsx` |
| | `src/components/layout/__tests__/integration.test.tsx` |
| | `src/routes/__tests__/routing.test.tsx` |
| | `scripts/__tests__/convert-themes.test.ts` |
| **资源** | `resources/themes/tokyo-night.json` |
| | `resources/themes/tokyo-night-storm.json` |
| | `resources/themes/tokyo-night-light.json` |
| **脚本** | `scripts/convert-themes.ts` |

---

## 任务依赖顺序

```
Task 1 (项目初始化)
  └── Task 2 (Rust 骨架)
        └── Task 3 (bindings.ts 生成)
  └── Task 4 (Tailwind + shadcn/ui)
        └── Task 5 (主题系统)
              └── Task 6 (路由骨架)
                    └── Task 7 (应用布局)
                          └── Task 9 (集成验收)
  └── Task 8 (convert-themes 脚本) ← 独立，可与 Task 4-7 并行
```

Task 1 必须最先完成；Task 8 可与 Task 4-7 并行执行；Task 9 必须最后执行。
