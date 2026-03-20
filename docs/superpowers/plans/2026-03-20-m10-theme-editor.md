# EchoNote v3.0.0 M10: VSCode-Style Theme Editor Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 M1 已有的 3 内置主题 + CSS 变量基础上，新增用户自定义主题的完整闭环——创建、编辑（实时预览）、导入、导出、删除。

**Architecture:** Rust 后端通过 `app_settings` KV 表持久化自定义主题列表（`custom_themes` key）和当前激活主题（`active_theme` key），`commands/theme.rs` 暴露 8 个 IPC 命令；前端 `store/theme.ts` 扩展 Zustand store 管理编辑临时状态，`useThemePreview` hook 将编辑中的 token 实时写入 `:root` CSS 变量实现全局预览；主题编辑器拆为 `ThemeSelector`（列表）/ `ThemeEditor`（token 编辑）/ `ThemePreview`（小预览面板）三个独立组件。

**Tech Stack:** Rust (serde_json, uuid, thiserror), tauri-specta v2, React 18, TypeScript, Zustand, Tailwind CSS, shadcn/ui (`<input type="color">`), Vitest + @testing-library/react

---

### Task 1: Rust — `ThemeManifest` 类型 + `commands/theme.rs` 骨架

**Files:**
- Modify: `src-tauri/src/commands/theme.rs`
- Modify: `src-tauri/src/commands/mod.rs`
- Modify: `src-tauri/src/error.rs`（确认 `Validation` variant 存在）
- Modify: `src-tauri/src/lib.rs`（注册新命令）

- [ ] **Step 1: 定义 `ThemeManifest` 及相关类型**

  在 `src-tauri/src/commands/theme.rs` 顶部写入：

  ```rust
  use std::collections::HashMap;
  use serde::{Deserialize, Serialize};
  use specta::Type;
  use uuid::Uuid;

  use crate::error::AppError;
  use crate::state::AppState;

  /// 主题类型：深色 / 浅色
  #[derive(Debug, Clone, Serialize, Deserialize, Type, PartialEq)]
  #[serde(rename_all = "lowercase")]
  pub enum ThemeType {
      Dark,
      Light,
  }

  /// 主题清单——内置主题与自定义主题共用此结构
  #[derive(Debug, Clone, Serialize, Deserialize, Type)]
  #[serde(rename_all = "camelCase")]
  pub struct ThemeManifest {
      pub id: String,
      pub name: String,
      pub theme_type: ThemeType,
      pub is_builtin: bool,
      /// semantic token 映射，例如 "bg.primary" → "#1a1b26"
      pub semantic_tokens: HashMap<String, String>,
  }
  ```

  **注意**：`ThemeManifest` 必须标注 `#[specta::specta]`（通过模块级 `use specta::Type` 派生），tauri-specta 构建时会自动将其映射为 TypeScript 接口。

- [ ] **Step 2: 定义 22 个必须的 semantic token key 列表（常量）**

  在 `theme.rs` 中写入常量（供 schema 校验复用）：

  ```rust
  /// M1 规格定义的全量 semantic token key 集合（22 个）
  pub const REQUIRED_TOKENS: &[&str] = &[
      "bg.primary",
      "bg.secondary",
      "bg.sidebar",
      "bg.input",
      "bg.hover",
      "bg.selection",
      "text.primary",
      "text.secondary",
      "text.muted",
      "text.disabled",
      "accent.primary",
      "accent.hover",
      "accent.muted",
      "border.default",
      "border.focus",
      "status.error",
      "status.warning",
      "status.success",
      "status.info",
      // 以下 3 个来自规格补充（共 22 个）
      "bg.overlay",
      "text.inverse",
      "accent.foreground",
  ];
  ```

  > **说明**：规格正文列出 19 个，此处补全至 22 个。若 M1 实际实施时 token 数量与此不同，以 M1 已落地的 `resources/themes/tokyo-night.json` 为准，保持一致，并同步更新此常量。

- [ ] **Step 3: 实现 CSS 颜色校验辅助函数**

  ```rust
  /// 校验 CSS 颜色值是否合法（支持 #RGB #RRGGBB #RRGGBBAA rgb() rgba()）
  fn is_valid_css_color(value: &str) -> bool {
      let v = value.trim();
      // #RGB / #RRGGBB / #RRGGBBAA
      if let Some(hex) = v.strip_prefix('#') {
          return matches!(hex.len(), 3 | 6 | 8)
              && hex.chars().all(|c| c.is_ascii_hexdigit());
      }
      // rgb(R, G, B) 或 rgba(R, G, B, A)
      let lower = v.to_lowercase();
      if lower.starts_with("rgb(") || lower.starts_with("rgba(") {
          return v.ends_with(')')
              && v.contains(',');
      }
      false
  }

  /// 完整 schema 校验：缺少 token、颜色非法、名称非法时返回 Validation 错误
  fn validate_theme_manifest(theme: &ThemeManifest) -> Result<(), AppError> {
      // 名称校验
      let name = theme.name.trim();
      if name.is_empty() {
          return Err(AppError::Validation("theme name must not be empty".into()));
      }
      if name.len() > 50 {
          return Err(AppError::Validation(
              "theme name must not exceed 50 characters".into(),
          ));
      }

      // 必须包含所有 required token
      for key in REQUIRED_TOKENS {
          if !theme.semantic_tokens.contains_key(*key) {
              return Err(AppError::Validation(format!(
                  "missing required token: {key}"
              )));
          }
      }

      // 每个值必须是合法 CSS 颜色
      for (key, value) in &theme.semantic_tokens {
          if !is_valid_css_color(value) {
              return Err(AppError::Validation(format!(
                  "invalid CSS color for token '{key}': {value}"
              )));
          }
      }

      Ok(())
  }
  ```

- [ ] **Step 4: 实现内置主题加载（从 `resources/themes/` 读取 JSON）**

  ```rust
  /// 从 Tauri 资源目录加载内置主题
  fn load_builtin_themes(app_handle: &tauri::AppHandle) -> Vec<ThemeManifest> {
      let builtin_ids = [
          ("tokyo-night",       "Tokyo Night",       ThemeType::Dark),
          ("tokyo-night-storm", "Tokyo Night Storm", ThemeType::Dark),
          ("tokyo-night-light", "Tokyo Night Light", ThemeType::Light),
      ];

      builtin_ids
          .iter()
          .filter_map(|(id, name, theme_type)| {
              // 使用 tauri::Manager::path 获取资源路径
              let resource_path = app_handle
                  .path()
                  .resource_dir()
                  .ok()?
                  .join("themes")
                  .join(format!("{id}.json"));

              let content = std::fs::read_to_string(&resource_path).ok()?;
              // resources/themes/*.json 格式：{ "semanticTokens": {...} }
              let raw: serde_json::Value = serde_json::from_str(&content).ok()?;
              let tokens_map = raw.get("semanticTokens")?;
              let semantic_tokens: HashMap<String, String> =
                  serde_json::from_value(tokens_map.clone()).ok()?;

              Some(ThemeManifest {
                  id: id.to_string(),
                  name: name.to_string(),
                  theme_type: theme_type.clone(),
                  is_builtin: true,
                  semantic_tokens,
              })
          })
          .collect()
  }
  ```

- [ ] **Step 5: 实现自定义主题的读写辅助函数（访问 `app_settings` 表）**

  ```rust
  const KEY_CUSTOM_THEMES: &str = "custom_themes";
  const KEY_ACTIVE_THEME: &str = "active_theme";

  /// 从 app_settings 读取自定义主题列表
  async fn read_custom_themes(state: &AppState) -> Result<Vec<ThemeManifest>, AppError> {
      let row: Option<(String,)> = sqlx::query_as(
          "SELECT value FROM app_settings WHERE key = ?",
      )
      .bind(KEY_CUSTOM_THEMES)
      .fetch_optional(&state.db)
      .await
      .map_err(|e| AppError::Storage(e.to_string()))?;

      match row {
          None => Ok(vec![]),
          Some((json,)) => serde_json::from_str(&json)
              .map_err(|e| AppError::Storage(format!("corrupt custom_themes: {e}"))),
      }
  }

  /// 将自定义主题列表持久化到 app_settings
  async fn write_custom_themes(
      state: &AppState,
      themes: &[ThemeManifest],
  ) -> Result<(), AppError> {
      let json = serde_json::to_string(themes)
          .map_err(|e| AppError::Storage(e.to_string()))?;
      let now = chrono::Utc::now().timestamp_millis();
      sqlx::query(
          "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
      )
      .bind(KEY_CUSTOM_THEMES)
      .bind(&json)
      .bind(now)
      .execute(&state.db)
      .await
      .map_err(|e| AppError::Storage(e.to_string()))?;
      Ok(())
  }
  ```

  > **依赖**：`AppState` 中已有 `db: sqlx::SqlitePool`（M1/M2 已建立）。若 M10 先于数据库 task 实施，需确认 `AppState` 字段名。

- [ ] **Step 6: 注册模块**

  在 `src-tauri/src/commands/mod.rs` 中添加 `pub mod theme;`。

  在 `src-tauri/src/lib.rs` 的 `tauri::Builder` 调用链中，将所有 theme commands 加入 `invoke_handler`：

  ```rust
  .invoke_handler(tauri::generate_handler![
      // ... 已有 commands ...
      commands::theme::list_themes,
      commands::theme::get_theme,
      commands::theme::create_custom_theme,
      commands::theme::update_theme_token,
      commands::theme::save_custom_theme,
      commands::theme::delete_custom_theme,
      commands::theme::export_theme,
      commands::theme::import_theme,
      commands::theme::set_active_theme,
  ])
  ```

- [ ] **Commit:** `feat(theme/rust): add ThemeManifest type, validation helpers, and app_settings KV accessors`

---

### Task 2: Rust — 8 个 IPC Commands 实现

**Files:**
- Modify: `src-tauri/src/commands/theme.rs`

- [ ] **Step 1: `list_themes` — 内置 + 自定义合并列表**

  ```rust
  #[tauri::command]
  #[specta::specta]
  pub async fn list_themes(
      state: tauri::State<'_, AppState>,
      app_handle: tauri::AppHandle,
  ) -> Result<Vec<ThemeManifest>, AppError> {
      let mut themes = load_builtin_themes(&app_handle);
      let custom = read_custom_themes(&state).await?;
      themes.extend(custom);
      Ok(themes)
  }
  ```

- [ ] **Step 2: `get_theme` — 按 ID 查找**

  ```rust
  #[tauri::command]
  #[specta::specta]
  pub async fn get_theme(
      id: String,
      state: tauri::State<'_, AppState>,
      app_handle: tauri::AppHandle,
  ) -> Result<ThemeManifest, AppError> {
      let all = list_themes(state, app_handle).await?;
      all.into_iter()
          .find(|t| t.id == id)
          .ok_or_else(|| AppError::NotFound(format!("theme '{id}' not found")))
  }
  ```

- [ ] **Step 3: `create_custom_theme` — 克隆 base 主题，生成新 UUID**

  ```rust
  #[tauri::command]
  #[specta::specta]
  pub async fn create_custom_theme(
      base_id: String,
      name: String,
      state: tauri::State<'_, AppState>,
      app_handle: tauri::AppHandle,
  ) -> Result<ThemeManifest, AppError> {
      // 找到 base 主题
      let base = get_theme(base_id, state.clone(), app_handle).await?;

      // 名称预校验（完整校验在 save 时做，这里先做基础检查）
      let trimmed = name.trim();
      if trimmed.is_empty() {
          return Err(AppError::Validation("theme name must not be empty".into()));
      }
      if trimmed.len() > 50 {
          return Err(AppError::Validation(
              "theme name must not exceed 50 characters".into(),
          ));
      }

      let new_theme = ThemeManifest {
          id: Uuid::new_v4().to_string(),
          name: trimmed.to_string(),
          theme_type: base.theme_type,
          is_builtin: false,
          semantic_tokens: base.semantic_tokens, // 完整克隆所有 token 值
      };

      // 持久化
      let mut customs = read_custom_themes(&state).await?;
      customs.push(new_theme.clone());
      write_custom_themes(&state, &customs).await?;

      Ok(new_theme)
  }
  ```

- [ ] **Step 4: `update_theme_token` — 实时修改单个 token（不持久化）**

  此命令仅做内存级别更新（前端主动调用 `save_custom_theme` 才落盘）。但由于 Rust 后端无编辑临时状态（前端管理），此命令的实际作用是校验值合法性并返回 OK，持久化由前端决定何时触发 `save_custom_theme`。

  ```rust
  #[tauri::command]
  #[specta::specta]
  pub async fn update_theme_token(
      _id: String,
      token: String,
      value: String,
  ) -> Result<(), AppError> {
      // 校验 token key 合法
      if !REQUIRED_TOKENS.contains(&token.as_str()) {
          return Err(AppError::Validation(format!("unknown token key: {token}")));
      }
      // 校验颜色值合法
      if !is_valid_css_color(&value) {
          return Err(AppError::Validation(format!(
              "invalid CSS color for token '{token}': {value}"
          )));
      }
      // 无需服务器端状态，前端本地管理 editingTheme
      Ok(())
  }
  ```

- [ ] **Step 5: `save_custom_theme` — 完整持久化**

  ```rust
  #[tauri::command]
  #[specta::specta]
  pub async fn save_custom_theme(
      theme: ThemeManifest,
      state: tauri::State<'_, AppState>,
  ) -> Result<(), AppError> {
      if theme.is_builtin {
          return Err(AppError::Validation("cannot save builtin theme".into()));
      }
      validate_theme_manifest(&theme)?;

      let mut customs = read_custom_themes(&state).await?;
      if let Some(pos) = customs.iter().position(|t| t.id == theme.id) {
          customs[pos] = theme; // 更新已有
      } else {
          customs.push(theme);  // 不应出现，防御性插入
      }
      write_custom_themes(&state, &customs).await
  }
  ```

- [ ] **Step 6: `delete_custom_theme`**

  ```rust
  #[tauri::command]
  #[specta::specta]
  pub async fn delete_custom_theme(
      id: String,
      state: tauri::State<'_, AppState>,
  ) -> Result<(), AppError> {
      let mut customs = read_custom_themes(&state).await?;
      let before = customs.len();
      customs.retain(|t| t.id != id);
      if customs.len() == before {
          return Err(AppError::NotFound(format!("custom theme '{id}' not found")));
      }
      write_custom_themes(&state, &customs).await?;

      // 若删除的是当前激活主题，回退到默认内置主题
      let active = read_active_theme_id(&state).await?;
      if active == id {
          write_active_theme_id(&state, "tokyo-night").await?;
      }
      Ok(())
  }
  ```

- [ ] **Step 7: `export_theme` — 返回 JSON 字符串供前端触发下载**

  ```rust
  #[tauri::command]
  #[specta::specta]
  pub async fn export_theme(
      id: String,
      state: tauri::State<'_, AppState>,
      app_handle: tauri::AppHandle,
  ) -> Result<String, AppError> {
      let theme = get_theme(id, state, app_handle).await?;
      serde_json::to_string_pretty(&theme)
          .map_err(|e| AppError::Io(e.to_string()))
  }
  ```

- [ ] **Step 8: `import_theme` — 解析 + schema 校验 + 冲突处理**

  ```rust
  #[tauri::command]
  #[specta::specta]
  pub async fn import_theme(
      json: String,
      state: tauri::State<'_, AppState>,
  ) -> Result<ThemeManifest, AppError> {
      let mut theme: ThemeManifest = serde_json::from_str(&json)
          .map_err(|e| AppError::Validation(format!("invalid JSON: {e}")))?;

      // 不允许导入内置主题 flag
      theme.is_builtin = false;

      validate_theme_manifest(&theme)?;

      let mut customs = read_custom_themes(&state).await?;

      // ID 冲突：内置主题 ID 或已存在的自定义主题 ID → 生成新 UUID
      let builtin_ids = ["tokyo-night", "tokyo-night-storm", "tokyo-night-light"];
      let id_conflict = builtin_ids.contains(&theme.id.as_str())
          || customs.iter().any(|t| t.id == theme.id);
      if id_conflict {
          theme.id = Uuid::new_v4().to_string();
      }

      customs.push(theme.clone());
      write_custom_themes(&state, &customs).await?;

      Ok(theme)
  }
  ```

- [ ] **Step 9: `set_active_theme` — 写 KV + emit 事件**

  ```rust
  /// 持久化激活主题 ID 的辅助函数
  async fn read_active_theme_id(state: &AppState) -> Result<String, AppError> {
      let row: Option<(String,)> = sqlx::query_as(
          "SELECT value FROM app_settings WHERE key = ?",
      )
      .bind(KEY_ACTIVE_THEME)
      .fetch_optional(&state.db)
      .await
      .map_err(|e| AppError::Storage(e.to_string()))?;
      Ok(row.map(|(v,)| v).unwrap_or_else(|| "tokyo-night".to_string()))
  }

  async fn write_active_theme_id(state: &AppState, id: &str) -> Result<(), AppError> {
      let now = chrono::Utc::now().timestamp_millis();
      sqlx::query(
          "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
      )
      .bind(KEY_ACTIVE_THEME)
      .bind(id)
      .bind(now)
      .execute(&state.db)
      .await
      .map_err(|e| AppError::Storage(e.to_string()))?;
      Ok(())
  }

  #[tauri::command]
  #[specta::specta]
  pub async fn set_active_theme(
      id: String,
      state: tauri::State<'_, AppState>,
      app_handle: tauri::AppHandle,
  ) -> Result<(), AppError> {
      // 验证 ID 存在
      get_theme(id.clone(), state.clone(), app_handle.clone()).await?;

      write_active_theme_id(&state, &id).await?;

      // 通知前端主题已变更（前端 store 监听此事件并更新 activeThemeId）
      app_handle
          .emit("theme:changed", &id)
          .map_err(|e| AppError::Io(e.to_string()))?;

      Ok(())
  }
  ```

- [ ] **Commit:** `feat(theme/rust): implement all 8 IPC commands for theme CRUD, import/export, and activation`

---

### Task 3: Rust — TDD 单元测试

**Files:**
- Modify: `src-tauri/src/commands/theme.rs`（在文件末尾 `#[cfg(test)]` 模块）

- [ ] **Step 1: 测试 schema 校验——缺少 token**

  ```rust
  #[cfg(test)]
  mod tests {
      use super::*;

      fn make_full_tokens() -> HashMap<String, String> {
          REQUIRED_TOKENS
              .iter()
              .map(|k| (k.to_string(), "#1a1b26".to_string()))
              .collect()
      }

      #[test]
      fn test_validation_missing_token() {
          let mut tokens = make_full_tokens();
          tokens.remove("bg.primary"); // 移除一个必须 token

          let theme = ThemeManifest {
              id: "test-id".to_string(),
              name: "Test Theme".to_string(),
              theme_type: ThemeType::Dark,
              is_builtin: false,
              semantic_tokens: tokens,
          };

          let err = validate_theme_manifest(&theme).unwrap_err();
          assert!(
              matches!(&err, AppError::Validation(msg) if msg.contains("missing required token")),
              "Expected Validation error about missing token, got: {err:?}"
          );
      }
  ```

- [ ] **Step 2: 测试 schema 校验——颜色格式非法**

  ```rust
      #[test]
      fn test_validation_invalid_color() {
          let mut tokens = make_full_tokens();
          tokens.insert("bg.primary".to_string(), "not-a-color".to_string());

          let theme = ThemeManifest {
              id: "test-id".to_string(),
              name: "Test Theme".to_string(),
              theme_type: ThemeType::Dark,
              is_builtin: false,
              semantic_tokens: tokens,
          };

          let err = validate_theme_manifest(&theme).unwrap_err();
          assert!(
              matches!(&err, AppError::Validation(msg) if msg.contains("invalid CSS color")),
              "Expected Validation error about invalid color, got: {err:?}"
          );
      }
  ```

- [ ] **Step 3: 测试 schema 校验——名称过长**

  ```rust
      #[test]
      fn test_validation_name_too_long() {
          let theme = ThemeManifest {
              id: "test-id".to_string(),
              name: "A".repeat(51), // 51 字符，超出限制
              theme_type: ThemeType::Dark,
              is_builtin: false,
              semantic_tokens: make_full_tokens(),
          };

          let err = validate_theme_manifest(&theme).unwrap_err();
          assert!(
              matches!(&err, AppError::Validation(msg) if msg.contains("exceed 50 characters")),
              "Expected Validation error about name length, got: {err:?}"
          );
      }
  ```

- [ ] **Step 4: 测试 `create_custom_theme` 克隆保留所有 token 值**

  此测试验证克隆逻辑（无需数据库，直接测试 token 拷贝）：

  ```rust
      #[test]
      fn test_clone_preserves_all_tokens() {
          // 构造一个有完整 token 的"模拟 base 主题"
          let base_tokens = make_full_tokens();
          // 插入一个有特殊值的 token 以验证克隆精确性
          let mut base_tokens_custom = base_tokens.clone();
          base_tokens_custom.insert("bg.primary".to_string(), "#abcdef".to_string());

          let base = ThemeManifest {
              id: "tokyo-night".to_string(),
              name: "Tokyo Night".to_string(),
              theme_type: ThemeType::Dark,
              is_builtin: true,
              semantic_tokens: base_tokens_custom.clone(),
          };

          // 模拟克隆逻辑（与 create_custom_theme 内部一致）
          let cloned = ThemeManifest {
              id: Uuid::new_v4().to_string(),
              name: "My Theme".to_string(),
              theme_type: base.theme_type.clone(),
              is_builtin: false,
              semantic_tokens: base.semantic_tokens.clone(),
          };

          // 验证所有 token 值完整保留
          for key in REQUIRED_TOKENS {
              assert_eq!(
                  cloned.semantic_tokens.get(*key),
                  base_tokens_custom.get(*key),
                  "Token '{key}' value mismatch after clone"
              );
          }

          // 验证 ID 已生成新值（不同于 base）
          assert_ne!(cloned.id, base.id);
          assert!(!cloned.is_builtin);
      }
  }  // end mod tests
  ```

- [ ] **Step 5: 运行测试验证通过**

  ```bash
  cd src-tauri && cargo test -- theme::tests 2>&1
  ```

  确认 4 个测试全部通过（PASSED）。

- [ ] **Commit:** `test(theme/rust): add schema validation and clone preservation unit tests`

---

### Task 4: 前端 — 扩展 `store/theme.ts`

**Files:**
- Modify: `src/store/theme.ts`
- Modify: `src/lib/bindings.ts`（tauri-specta 重新生成后自动更新，此处记录手动占位类型）

- [ ] **Step 1: 定义 TypeScript 侧的 `ThemeManifest` 类型（bindings.ts 生成前临时）**

  在 `src/store/theme.ts` 顶部引入（bindings 生成后改为从 bindings.ts 引入）：

  ```typescript
  // TODO: 待 tauri-specta 重新生成后替换为：
  // import type { ThemeManifest } from '@/lib/bindings'
  export interface ThemeManifest {
    id: string
    name: string
    themeType: 'dark' | 'light'
    isBuiltin: boolean
    semanticTokens: Record<string, string>
  }
  ```

- [ ] **Step 2: 扩展 Zustand store 状态接口**

  ```typescript
  import { create } from 'zustand'
  import { commands } from '@/lib/bindings'

  interface ThemeState {
    // 持久状态
    themes: ThemeManifest[]
    activeThemeId: string

    // 编辑临时状态（编辑期间不影响已保存的 themes[]）
    editingTheme: ThemeManifest | null
    isEditorOpen: boolean

    // Actions
    loadThemes: () => Promise<void>
    setActive: (id: string) => Promise<void>

    // 编辑器操作
    startEdit: (themeId: string) => void
    updateToken: (token: string, value: string) => void // 仅更新本地 editingTheme
    saveEdit: () => Promise<void>
    discardEdit: () => void

    // 导入 / 导出 / 删除
    importTheme: (json: string) => Promise<ThemeManifest>
    exportTheme: (id: string) => Promise<string>   // 返回 JSON 字符串
    deleteTheme: (id: string) => Promise<void>
  }
  ```

- [ ] **Step 3: 实现 store 逻辑**

  ```typescript
  export const useThemeStore = create<ThemeState>((set, get) => ({
    themes: [],
    activeThemeId: 'tokyo-night',
    editingTheme: null,
    isEditorOpen: false,

    loadThemes: async () => {
      const themes = await commands.listThemes()
      set({ themes })
    },

    setActive: async (id: string) => {
      await commands.setActiveTheme(id)
      set({ activeThemeId: id })
      // applyThemeTokens 由 useThemePreview 监听 activeThemeId 变化后自动调用
    },

    startEdit: (themeId: string) => {
      const theme = get().themes.find((t) => t.id === themeId) ?? null
      if (!theme) return
      set({ editingTheme: { ...theme, semanticTokens: { ...theme.semanticTokens } }, isEditorOpen: true })
    },

    updateToken: (token: string, value: string) => {
      const { editingTheme } = get()
      if (!editingTheme) return
      set({
        editingTheme: {
          ...editingTheme,
          semanticTokens: { ...editingTheme.semanticTokens, [token]: value },
        },
      })
      // CSS 变量实时应用（不等待 Rust，纯前端）
      applyTokenToRoot(token, value)
    },

    saveEdit: async () => {
      const { editingTheme, themes } = get()
      if (!editingTheme) return
      await commands.saveCustomTheme(editingTheme)
      set({
        isEditorOpen: false,
        editingTheme: null,
        themes: themes.map((t) => (t.id === editingTheme.id ? editingTheme : t)),
      })
    },

    discardEdit: () => {
      // 恢复原主题 CSS 变量（由 useThemePreview 处理）
      set({ isEditorOpen: false, editingTheme: null })
    },

    importTheme: async (json: string) => {
      const theme = await commands.importTheme(json)
      set((state) => ({ themes: [...state.themes, theme] }))
      return theme
    },

    exportTheme: async (id: string) => {
      return commands.exportTheme(id)
    },

    deleteTheme: async (id: string) => {
      await commands.deleteCustomTheme(id)
      set((state) => ({
        themes: state.themes.filter((t) => t.id !== id),
        // 若删除的是激活主题，回退到默认（后端已处理，这里同步前端状态）
        activeThemeId: state.activeThemeId === id ? 'tokyo-night' : state.activeThemeId,
      }))
    },
  }))

  // ──────────────────────────────────────────────
  // CSS 变量应用辅助（token key → CSS 变量名映射）
  // ──────────────────────────────────────────────

  /** 将 semantic token key 转换为 CSS 变量名，例如 "bg.primary" → "--color-bg-primary" */
  function tokenToCssVar(token: string): string {
    return `--color-${token.replace(/\./g, '-')}`
  }

  /** 将单个 token 值写入 :root */
  function applyTokenToRoot(token: string, value: string): void {
    document.documentElement.style.setProperty(tokenToCssVar(token), value)
  }

  /** 将完整 ThemeManifest 的所有 token 批量写入 :root */
  export function applyThemeManifest(manifest: ThemeManifest): void {
    for (const [token, value] of Object.entries(manifest.semanticTokens)) {
      applyTokenToRoot(token, value)
    }
  }
  ```

- [ ] **Step 4: 在 App.tsx 启动时监听 `theme:changed` 事件**

  在 `src/App.tsx` 中（或 store 初始化 hook 中）：

  ```typescript
  import { listen } from '@tauri-apps/api/event'
  import { useThemeStore, applyThemeManifest } from '@/store/theme'

  // 在应用启动时调用一次
  export async function setupThemeListeners() {
    const store = useThemeStore.getState()
    await store.loadThemes()

    // 监听 Rust emit 的 theme:changed 事件（set_active_theme 触发）
    await listen<string>('theme:changed', (event) => {
      const id = event.payload
      const themes = useThemeStore.getState().themes
      const manifest = themes.find((t) => t.id === id)
      if (manifest) {
        applyThemeManifest(manifest)
        useThemeStore.setState({ activeThemeId: id })
      }
    })
  }
  ```

- [ ] **Commit:** `feat(theme/store): extend useThemeStore with editingTheme, CRUD actions, and CSS variable application`

---

### Task 5: 前端 — `hooks/useThemePreview.ts`

**Files:**
- Create: `src/hooks/useThemePreview.ts`

- [ ] **Step 1: 实现 hook**

  此 hook 负责：编辑期间将 `editingTheme` 的 token 覆盖写入 `:root`；放弃编辑时恢复原激活主题的 token。

  ```typescript
  import { useEffect, useRef } from 'react'
  import { useThemeStore, applyThemeManifest } from '@/store/theme'

  /**
   * useThemePreview
   *
   * 监听 editingTheme 变化：
   * - 进入编辑（editingTheme 从 null 变为对象）：记录原 token 快照
   * - 编辑中（editingTheme.semanticTokens 变化）：实时写入 CSS 变量
   * - 退出编辑（editingTheme 变回 null）：恢复原 token 快照
   *
   * 在 ThemeEditor 组件的顶层调用此 hook 即可。
   */
  export function useThemePreview(): void {
    const { editingTheme, activeThemeId, themes } = useThemeStore()
    // 进入编辑前的原始 token 快照（用于放弃时恢复）
    const originalTokensRef = useRef<Record<string, string> | null>(null)

    useEffect(() => {
      if (editingTheme) {
        // 第一次进入编辑：记录当前激活主题 token 作为恢复基准
        if (!originalTokensRef.current) {
          const activeManifest = themes.find((t) => t.id === activeThemeId)
          originalTokensRef.current = activeManifest
            ? { ...activeManifest.semanticTokens }
            : null
        }
        // 将编辑中的 token 批量写入 :root
        applyThemeManifest(editingTheme)
      } else {
        // 退出编辑（保存或放弃）：恢复原主题
        if (originalTokensRef.current) {
          const activeManifest = themes.find((t) => t.id === activeThemeId)
          if (activeManifest) {
            applyThemeManifest(activeManifest)
          }
          originalTokensRef.current = null
        }
      }
    }, [editingTheme, activeThemeId, themes])
  }
  ```

- [ ] **Commit:** `feat(theme/hooks): add useThemePreview for live CSS variable override during editing`

---

### Task 6: 前端 — `ThemePreview` 组件

**Files:**
- Create: `src/components/settings/theme/ThemePreview.tsx`

- [ ] **Step 1: 实现小型 UI 预览面板**

  `ThemePreview` 是一个纯展示组件，全部使用 Tailwind 语义色类（`bg-bg-primary`、`text-text-primary` 等），因此它天然随 CSS 变量变化而实时更新，无需额外逻辑。

  ```tsx
  // src/components/settings/theme/ThemePreview.tsx

  export function ThemePreview() {
    return (
      <div className="rounded-lg overflow-hidden border border-border-default text-sm w-full select-none">
        {/* 侧边栏模拟 */}
        <div className="flex h-48">
          <div className="w-1/3 bg-bg-sidebar p-2 flex flex-col gap-1 border-r border-border-default">
            <div className="text-text-muted text-xs uppercase tracking-wider mb-1">Sidebar</div>
            <div className="rounded px-2 py-1 bg-bg-hover text-text-primary text-xs cursor-pointer">
              Active Item
            </div>
            <div className="rounded px-2 py-1 text-text-secondary text-xs hover:bg-bg-hover cursor-pointer">
              Normal Item
            </div>
            <div className="rounded px-2 py-1 text-text-disabled text-xs">
              Disabled Item
            </div>
          </div>

          {/* 主内容区模拟 */}
          <div className="flex-1 bg-bg-primary p-3 flex flex-col gap-2">
            <div className="text-text-primary font-medium text-xs">Main Content</div>
            <div className="text-text-secondary text-xs">Secondary text sample</div>
            <div className="text-text-muted text-xs">Muted text sample</div>

            {/* 按钮行 */}
            <div className="flex gap-1 mt-auto">
              <button className="px-2 py-1 rounded bg-accent text-xs text-white hover:bg-accent-hover transition-colors">
                Primary
              </button>
              <button className="px-2 py-1 rounded border border-border-default text-text-secondary text-xs hover:bg-bg-hover transition-colors">
                Secondary
              </button>
            </div>
          </div>
        </div>

        {/* 输入框模拟 */}
        <div className="bg-bg-secondary p-2 border-t border-border-default">
          <div className="rounded border border-border-default bg-bg-input px-2 py-1 text-text-primary text-xs focus-within:border-border-focus">
            <span className="text-text-muted">Search or type...</span>
          </div>
        </div>

        {/* 状态色展示条 */}
        <div className="bg-bg-secondary flex gap-1 p-2 border-t border-border-default">
          {(
            [
              ['status-error', 'Error'],
              ['status-warning', 'Warn'],
              ['status-success', 'OK'],
              ['status-info', 'Info'],
            ] as const
          ).map(([cls, label]) => (
            <span
              key={cls}
              className={`text-${cls} text-xs px-1`}
            >
              {label}
            </span>
          ))}
        </div>
      </div>
    )
  }
  ```

  > **注意**：Tailwind 动态类名（`text-${cls}`）在 JIT 模式下不会被扫描到。需在 `tailwind.config.ts` 的 `safelist` 中列出这 4 个类，或改为内联 style 从 CSS 变量读取。推荐改用内联 style：
  >
  > ```tsx
  > <span style={{ color: `var(--color-status-${key})` }} className="text-xs px-1">
  >   {label}
  > </span>
  > ```

- [ ] **Commit:** `feat(theme/ui): add ThemePreview component with live CSS variable rendering`

---

### Task 7: 前端 — `ThemeEditor` 组件

**Files:**
- Create: `src/components/settings/theme/ThemeEditor.tsx`

- [ ] **Step 1: 定义 token 分组配置**

  ```typescript
  // src/components/settings/theme/ThemeEditor.tsx
  import { useThemeStore } from '@/store/theme'
  import { useThemePreview } from '@/hooks/useThemePreview'
  import { ThemePreview } from './ThemePreview'

  type TokenGroup = {
    label: string
    tokens: { key: string; label: string }[]
  }

  const TOKEN_GROUPS: TokenGroup[] = [
    {
      label: '背景色',
      tokens: [
        { key: 'bg.primary',   label: 'Primary Background' },
        { key: 'bg.secondary', label: 'Secondary Background' },
        { key: 'bg.sidebar',   label: 'Sidebar Background' },
        { key: 'bg.input',     label: 'Input Background' },
        { key: 'bg.hover',     label: 'Hover Background' },
        { key: 'bg.selection', label: 'Selection Background' },
      ],
    },
    {
      label: '文字色',
      tokens: [
        { key: 'text.primary',   label: 'Primary Text' },
        { key: 'text.secondary', label: 'Secondary Text' },
        { key: 'text.muted',     label: 'Muted Text' },
        { key: 'text.disabled',  label: 'Disabled Text' },
      ],
    },
    {
      label: '强调色',
      tokens: [
        { key: 'accent.primary', label: 'Accent Primary' },
        { key: 'accent.hover',   label: 'Accent Hover' },
        { key: 'accent.muted',   label: 'Accent Muted' },
      ],
    },
    {
      label: '边框',
      tokens: [
        { key: 'border.default', label: 'Default Border' },
        { key: 'border.focus',   label: 'Focus Border' },
      ],
    },
    {
      label: '状态色',
      tokens: [
        { key: 'status.error',   label: 'Error' },
        { key: 'status.warning', label: 'Warning' },
        { key: 'status.success', label: 'Success' },
        { key: 'status.info',    label: 'Info' },
      ],
    },
  ]
  ```

- [ ] **Step 2: 实现 `TokenRow` 子组件（色块 + hex 输入 + color picker 双向同步）**

  ```tsx
  interface TokenRowProps {
    tokenKey: string
    label: string
    value: string
    onChange: (token: string, value: string) => void
  }

  function TokenRow({ tokenKey, label, value, onChange }: TokenRowProps) {
    // 将带 alpha 的 hex (#RRGGBBAA) 截断为 6 位供 <input type="color"> 使用
    const pickerValue = value.startsWith('#') ? value.slice(0, 7) : '#000000'

    function handlePickerChange(e: React.ChangeEvent<HTMLInputElement>) {
      onChange(tokenKey, e.target.value)
    }

    function handleHexChange(e: React.ChangeEvent<HTMLInputElement>) {
      const raw = e.target.value
      // 允许用户键入过程中不完整的值，只有完整时才触发更新
      if (/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(raw)) {
        onChange(tokenKey, raw)
      }
    }

    return (
      <div className="flex items-center gap-3 py-1.5">
        {/* 色块 + color picker（叠加，点色块即触发 picker） */}
        <div className="relative w-8 h-8 rounded border border-border-default overflow-hidden shrink-0 cursor-pointer">
          <div
            className="absolute inset-0"
            style={{ backgroundColor: value }}
          />
          <input
            type="color"
            value={pickerValue}
            onChange={handlePickerChange}
            className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
            aria-label={`Color picker for ${label}`}
          />
        </div>

        {/* Token 标签 */}
        <span className="text-text-secondary text-xs flex-1 min-w-0 truncate" title={tokenKey}>
          {label}
          <span className="text-text-muted ml-1 font-mono">{tokenKey}</span>
        </span>

        {/* Hex 输入框 */}
        <input
          type="text"
          defaultValue={value}
          key={value} // key 变化时强制重渲染（避免受控/非受控混用问题）
          onChange={handleHexChange}
          className="w-28 px-2 py-1 rounded border border-border-default bg-bg-input text-text-primary text-xs font-mono focus:border-border-focus outline-none"
          aria-label={`Hex value for ${label}`}
          spellCheck={false}
        />
      </div>
    )
  }
  ```

- [ ] **Step 3: 实现 `ThemeEditor` 主组件**

  ```tsx
  export function ThemeEditor() {
    useThemePreview() // 注册实时预览 hook

    const { editingTheme, updateToken, saveEdit, discardEdit } = useThemeStore()

    if (!editingTheme) return null

    return (
      <div className="flex gap-6 h-full overflow-hidden">
        {/* 左侧：token 编辑区（可滚动） */}
        <div className="flex-1 overflow-y-auto pr-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-text-primary font-semibold text-sm">
              编辑主题：{editingTheme.name}
            </h2>
            <span className="text-text-muted text-xs px-2 py-0.5 rounded border border-border-default">
              {editingTheme.themeType === 'dark' ? 'Dark' : 'Light'}
            </span>
          </div>

          {TOKEN_GROUPS.map((group) => (
            <div key={group.label} className="mb-5">
              <div className="text-text-muted text-xs uppercase tracking-wider mb-2 border-b border-border-default pb-1">
                {group.label}
              </div>
              {group.tokens.map(({ key, label }) => (
                <TokenRow
                  key={key}
                  tokenKey={key}
                  label={label}
                  value={editingTheme.semanticTokens[key] ?? '#000000'}
                  onChange={updateToken}
                />
              ))}
            </div>
          ))}
        </div>

        {/* 右侧：预览面板 + 操作按钮 */}
        <div className="w-64 shrink-0 flex flex-col gap-4">
          <div className="text-text-muted text-xs uppercase tracking-wider">预览</div>
          <ThemePreview />

          <div className="mt-auto flex flex-col gap-2">
            <button
              onClick={saveEdit}
              className="w-full px-3 py-2 rounded bg-accent hover:bg-accent-hover text-white text-sm transition-colors"
            >
              保存主题
            </button>
            <button
              onClick={discardEdit}
              className="w-full px-3 py-2 rounded border border-border-default text-text-secondary hover:bg-bg-hover text-sm transition-colors"
            >
              放弃修改
            </button>
          </div>
        </div>
      </div>
    )
  }
  ```

- [ ] **Commit:** `feat(theme/ui): add ThemeEditor with token groups, dual-sync color picker, and live preview`

---

### Task 8: 前端 — `ThemeSelector` 组件

**Files:**
- Create: `src/components/settings/theme/ThemeSelector.tsx`

- [ ] **Step 1: 实现主题卡片（`ThemeCard`）子组件**

  ```tsx
  // src/components/settings/theme/ThemeSelector.tsx
  import { useThemeStore, type ThemeManifest } from '@/store/theme'
  import { ThemeEditor } from './ThemeEditor'

  // 颜色预览条展示的 5 个主要 token
  const PREVIEW_TOKENS = [
    'bg.primary',
    'bg.sidebar',
    'text.primary',
    'accent.primary',
    'status.success',
  ] as const

  interface ThemeCardProps {
    theme: ThemeManifest
    isActive: boolean
    onActivate: () => void
    onEdit: () => void
    onDelete: () => void
    onExport: () => void
  }

  function ThemeCard({ theme, isActive, onActivate, onEdit, onDelete, onExport }: ThemeCardProps) {
    return (
      <div
        className={[
          'rounded-lg border p-3 cursor-pointer transition-colors',
          isActive
            ? 'border-accent-primary bg-bg-hover'
            : 'border-border-default bg-bg-secondary hover:bg-bg-hover',
        ].join(' ')}
        onClick={onActivate}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && onActivate()}
        aria-pressed={isActive}
      >
        {/* 标题行 */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-text-primary text-sm font-medium truncate">{theme.name}</span>
          <span className="ml-2 text-xs px-1.5 py-0.5 rounded border border-border-default text-text-muted shrink-0">
            {theme.themeType === 'dark' ? 'Dark' : 'Light'}
          </span>
        </div>

        {/* 颜色预览条 */}
        <div className="flex gap-1 mb-3 h-5 rounded overflow-hidden">
          {PREVIEW_TOKENS.map((tk) => (
            <div
              key={tk}
              className="flex-1"
              style={{ backgroundColor: theme.semanticTokens[tk] ?? 'transparent' }}
              title={tk}
            />
          ))}
        </div>

        {/* 操作按钮行 */}
        <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={onEdit}
            disabled={theme.isBuiltin}
            title={theme.isBuiltin ? '内置主题不可编辑' : '编辑主题'}
            className="px-2 py-0.5 rounded text-xs border border-border-default text-text-secondary hover:bg-bg-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            编辑
          </button>
          <button
            onClick={onExport}
            className="px-2 py-0.5 rounded text-xs border border-border-default text-text-secondary hover:bg-bg-hover transition-colors"
          >
            导出
          </button>
          <button
            onClick={onDelete}
            disabled={theme.isBuiltin}
            title={theme.isBuiltin ? '内置主题不可删除' : '删除主题'}
            className="px-2 py-0.5 rounded text-xs border border-border-default text-status-error hover:bg-bg-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            删除
          </button>
        </div>
      </div>
    )
  }
  ```

- [ ] **Step 2: 实现 `ThemeSelector` 主组件（含新建、导入逻辑）**

  ```tsx
  export function ThemeSelector() {
    const {
      themes,
      activeThemeId,
      isEditorOpen,
      setActive,
      startEdit,
      deleteTheme,
      exportTheme,
      importTheme,
      createCustomTheme, // 需在 store 中补充此 action（见 Step 3）
      loadThemes,
    } = useThemeStore()

    // 新建主题弹窗本地状态
    const [showCreateDialog, setShowCreateDialog] = React.useState(false)
    const [createName, setCreateName] = React.useState('')
    const [createBaseId, setCreateBaseId] = React.useState('tokyo-night')

    // 下载导出文件
    async function handleExport(theme: ThemeManifest) {
      const json = await exportTheme(theme.id)
      const blob = new Blob([json], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${theme.name}.echonote-theme.json`
      a.click()
      URL.revokeObjectURL(url)
    }

    // 导入文件
    function handleImportClick() {
      const input = document.createElement('input')
      input.type = 'file'
      input.accept = '.json,.echonote-theme.json'
      input.onchange = async (e) => {
        const file = (e.target as HTMLInputElement).files?.[0]
        if (!file) return
        const text = await file.text()
        try {
          await importTheme(text)
        } catch (err) {
          // TODO: 接入 toast 通知系统（M10 范围内用 alert 临时替代）
          alert(`导入失败：${err}`)
        }
      }
      input.click()
    }

    // 新建主题确认
    async function handleCreateConfirm() {
      if (!createName.trim()) return
      await createCustomTheme(createBaseId, createName.trim())
      setShowCreateDialog(false)
      setCreateName('')
    }

    if (isEditorOpen) {
      return <ThemeEditor />
    }

    return (
      <div className="flex flex-col gap-4 p-4">
        {/* 操作栏 */}
        <div className="flex gap-2">
          <button
            onClick={() => setShowCreateDialog(true)}
            className="px-3 py-1.5 rounded bg-accent hover:bg-accent-hover text-white text-sm transition-colors"
          >
            + 新建主题
          </button>
          <button
            onClick={handleImportClick}
            className="px-3 py-1.5 rounded border border-border-default text-text-secondary hover:bg-bg-hover text-sm transition-colors"
          >
            导入主题
          </button>
        </div>

        {/* 主题卡片网格 */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {themes.map((theme) => (
            <ThemeCard
              key={theme.id}
              theme={theme}
              isActive={theme.id === activeThemeId}
              onActivate={() => setActive(theme.id)}
              onEdit={() => startEdit(theme.id)}
              onDelete={() => {
                if (confirm(`确认删除主题"${theme.name}"？`)) {
                  deleteTheme(theme.id)
                }
              }}
              onExport={() => handleExport(theme)}
            />
          ))}
        </div>

        {/* 新建主题弹窗（简易实现，生产级可替换为 shadcn/ui Dialog） */}
        {showCreateDialog && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-bg-secondary rounded-lg border border-border-default p-5 w-80 shadow-xl">
              <h3 className="text-text-primary font-semibold mb-4">新建主题</h3>

              <div className="mb-3">
                <label className="text-text-secondary text-xs block mb-1">主题名称</label>
                <input
                  type="text"
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                  maxLength={50}
                  placeholder="我的主题"
                  className="w-full px-2 py-1.5 rounded border border-border-default bg-bg-input text-text-primary text-sm focus:border-border-focus outline-none"
                  autoFocus
                />
              </div>

              <div className="mb-4">
                <label className="text-text-secondary text-xs block mb-1">基于</label>
                <select
                  value={createBaseId}
                  onChange={(e) => setCreateBaseId(e.target.value)}
                  className="w-full px-2 py-1.5 rounded border border-border-default bg-bg-input text-text-primary text-sm focus:border-border-focus outline-none"
                >
                  {themes.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => { setShowCreateDialog(false); setCreateName('') }}
                  className="px-3 py-1.5 rounded border border-border-default text-text-secondary hover:bg-bg-hover text-sm transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={handleCreateConfirm}
                  disabled={!createName.trim()}
                  className="px-3 py-1.5 rounded bg-accent hover:bg-accent-hover text-white text-sm transition-colors disabled:opacity-50"
                >
                  创建
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }
  ```

- [ ] **Step 3: 在 `store/theme.ts` 补充 `createCustomTheme` action**

  ```typescript
  // 在 ThemeState interface 中添加：
  createCustomTheme: (baseId: string, name: string) => Promise<void>

  // 在 create() 实现中添加：
  createCustomTheme: async (baseId: string, name: string) => {
    const theme = await commands.createCustomTheme(baseId, name)
    set((state) => ({ themes: [...state.themes, theme] }))
  },
  ```

- [ ] **Commit:** `feat(theme/ui): add ThemeSelector with card list, create dialog, import/export, and delete`

---

### Task 9: 前端 — 路由接入（Settings 页面集成）

**Files:**
- Modify: `src/components/settings/SettingsPage.tsx`（或对应的 `/settings/theme` 路由组件）
- Modify: `src/router.tsx`（确认 `/settings/theme` 路由存在）

- [ ] **Step 1: 确认 `/settings/theme` 路由存在（M1 已建立）**

  在 `src/router.tsx` 中确认存在如下路由定义：

  ```typescript
  // /settings/theme → ThemeSettingsPage
  ```

  若不存在，添加：

  ```typescript
  import { ThemeSettingsPage } from '@/pages/settings/ThemeSettingsPage'
  // 在路由树中注册 path: '/settings/theme'
  ```

- [ ] **Step 2: 创建 `ThemeSettingsPage` 页面组件**

  ```tsx
  // src/pages/settings/ThemeSettingsPage.tsx
  import React, { useEffect } from 'react'
  import { ThemeSelector } from '@/components/settings/theme/ThemeSelector'
  import { useThemeStore } from '@/store/theme'

  export function ThemeSettingsPage() {
    const { loadThemes } = useThemeStore()

    useEffect(() => {
      loadThemes()
    }, [loadThemes])

    return (
      <div className="flex flex-col h-full bg-bg-primary">
        <div className="px-4 pt-4 pb-2 border-b border-border-default">
          <h1 className="text-text-primary font-semibold text-base">主题</h1>
          <p className="text-text-muted text-xs mt-0.5">自定义应用外观，创建或导入主题</p>
        </div>
        <div className="flex-1 overflow-y-auto">
          <ThemeSelector />
        </div>
      </div>
    )
  }
  ```

- [ ] **Commit:** `feat(theme/routing): wire ThemeSettingsPage into /settings/theme route`

---

### Task 10: 前端 — TDD 测试（hex 输入框 ↔ color picker 双向同步）

**Files:**
- Create: `src/components/settings/theme/__tests__/TokenRow.test.tsx`

- [ ] **Step 1: 编写测试**

  ```tsx
  // src/components/settings/theme/__tests__/TokenRow.test.tsx
  import React from 'react'
  import { describe, it, expect, vi } from 'vitest'
  import { render, screen, fireEvent } from '@testing-library/react'
  import userEvent from '@testing-library/user-event'

  // TokenRow 需要从 ThemeEditor.tsx 单独导出（见 Step 2）
  import { TokenRow } from '../ThemeEditor'

  describe('TokenRow — hex input ↔ color picker bidirectional sync', () => {
    it('color picker 变化后 hex 输入框显示新值', async () => {
      const onChange = vi.fn()

      render(
        <TokenRow
          tokenKey="bg.primary"
          label="Primary Background"
          value="#1a1b26"
          onChange={onChange}
        />
      )

      const picker = screen.getByLabelText('Color picker for Primary Background')

      // 模拟 picker 变化为新颜色
      fireEvent.change(picker, { target: { value: '#ff0000' } })

      expect(onChange).toHaveBeenCalledWith('bg.primary', '#ff0000')
    })

    it('hex 输入框键入合法完整颜色后触发 onChange', async () => {
      const onChange = vi.fn()
      const user = userEvent.setup()

      render(
        <TokenRow
          tokenKey="bg.primary"
          label="Primary Background"
          value="#1a1b26"
          onChange={onChange}
        />
      )

      const hexInput = screen.getByLabelText('Hex value for Primary Background')

      // 清空并键入新的合法 hex
      await user.clear(hexInput)
      await user.type(hexInput, '#aabbcc')

      expect(onChange).toHaveBeenCalledWith('bg.primary', '#aabbcc')
    })

    it('hex 输入框键入不完整颜色时不触发 onChange', async () => {
      const onChange = vi.fn()
      const user = userEvent.setup()

      render(
        <TokenRow
          tokenKey="bg.primary"
          label="Primary Background"
          value="#1a1b26"
          onChange={onChange}
        />
      )

      const hexInput = screen.getByLabelText('Hex value for Primary Background')

      await user.clear(hexInput)
      await user.type(hexInput, '#abc') // 3 位合法，但键入过程中有 1、2 位的中间状态

      // onChange 只在合法完整颜色时被调用（#abc 是合法的 3 位 hex，应触发一次）
      const calls = onChange.mock.calls.filter(([, v]) =>
        /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(v)
      )
      expect(calls.length).toBeGreaterThanOrEqual(1)
    })

    it('color picker value 截断为 6 位（忽略 alpha）', () => {
      const onChange = vi.fn()

      render(
        <TokenRow
          tokenKey="bg.selection"
          label="Selection Background"
          value="#3d59a144" // 8 位含 alpha
          onChange={onChange}
        />
      )

      const picker = screen.getByLabelText(
        'Color picker for Selection Background'
      ) as HTMLInputElement

      // picker 的值应为截断后的 6 位
      expect(picker.value).toBe('#3d59a1')
    })
  })
  ```

- [ ] **Step 2: 导出 `TokenRow` 以便测试引入**

  在 `src/components/settings/theme/ThemeEditor.tsx` 中将 `TokenRow` 改为命名导出：

  ```typescript
  export function TokenRow(...) { ... }
  ```

- [ ] **Step 3: 运行测试**

  ```bash
  npm run test -- src/components/settings/theme/__tests__/TokenRow.test.tsx
  ```

  确认 4 个测试全部通过（PASSED）。

- [ ] **Commit:** `test(theme/ui): add TokenRow bidirectional sync tests for hex input and color picker`

---

### Task 11: tauri-specta 类型重新生成 + 最终集成验收

**Files:**
- Modify: `src/lib/bindings.ts`（自动生成，不手写）
- Modify: `src-tauri/src/lib.rs`（确认 specta export 调用包含 theme commands）

- [ ] **Step 1: 重新生成 `bindings.ts`**

  在 `src-tauri/src/lib.rs` 的 specta 导出配置中确认包含所有 theme 命令：

  ```rust
  // 在 specta 导出块中（与其他 commands 同级）
  .commands(collect_commands![
      // ... 已有 commands ...
      commands::theme::list_themes,
      commands::theme::get_theme,
      commands::theme::create_custom_theme,
      commands::theme::update_theme_token,
      commands::theme::save_custom_theme,
      commands::theme::delete_custom_theme,
      commands::theme::export_theme,
      commands::theme::import_theme,
      commands::theme::set_active_theme,
  ])
  ```

  执行 `cargo build`（开发构建时 tauri-specta 自动写入 `src/lib/bindings.ts`）。

- [ ] **Step 2: 将 `store/theme.ts` 中的临时类型替换为 bindings.ts 导入**

  ```typescript
  // 替换顶部 interface 定义为：
  import type { ThemeManifest } from '@/lib/bindings'
  ```

  同时删除手写的 `ThemeManifest` interface。

- [ ] **Step 3: 完整用户流程手动验收**

  按以下流程逐步验证：

  1. 启动应用 → 导航到 Settings → Theme
  2. 确认看到 3 个内置主题卡片（Tokyo Night / Tokyo Night Storm / Tokyo Night Light）
  3. 内置主题的"编辑"和"删除"按钮为灰色不可点击状态
  4. 点击内置主题卡片 → 激活（卡片边框变为 accent 色）
  5. 点击"+ 新建主题" → 输入名称"My Dark Theme" → 基于"Tokyo Night" → 点"创建"
  6. 新主题卡片出现在列表末尾
  7. 点击新主题卡片的"编辑" → 进入编辑器
  8. 修改 `bg.primary` 颜色 → 右侧预览和整个 app UI 实时变化
  9. 点"保存主题" → 回到列表，颜色预览条显示新颜色
  10. 点击新主题"导出" → 浏览器下载 `My Dark Theme.echonote-theme.json`
  11. 点击"导入主题" → 选择上述 JSON → 新主题（新 ID）出现在列表
  12. 点击新主题"删除" → 确认 → 主题从列表消失

- [ ] **Step 4: 运行全量测试**

  ```bash
  # Rust 单元测试
  cd src-tauri && cargo test -- theme::tests

  # 前端测试
  cd .. && npm run test -- src/components/settings/theme/__tests__/
  ```

  确认所有测试通过。

- [ ] **Commit:** `feat(m10): regenerate bindings, replace temp types, complete theme editor integration`

---

## 实施顺序总结

| 顺序 | Task | 关键产物 | 预估工时 |
|------|------|---------|---------|
| 1 | Task 1 | `ThemeManifest` 类型 + KV 辅助函数 | 1h |
| 2 | Task 2 | 8 个 IPC commands | 2h |
| 3 | Task 3 | Rust 单元测试（4 cases） | 0.5h |
| 4 | Task 4 | `store/theme.ts` 扩展 | 1h |
| 5 | Task 5 | `useThemePreview` hook | 0.5h |
| 6 | Task 6 | `ThemePreview` 组件 | 0.5h |
| 7 | Task 7 | `ThemeEditor` 组件 | 1.5h |
| 8 | Task 8 | `ThemeSelector` 组件 | 1.5h |
| 9 | Task 9 | 路由接入 | 0.5h |
| 10 | Task 10 | 前端 TDD 测试（4 cases） | 0.5h |
| 11 | Task 11 | bindings 生成 + 集成验收 | 1h |
| **合计** | | | **~10.5h** |

## 关键依赖与注意事项

1. **M1 已交付物核查**：实施前确认以下文件已存在：
   - `src/store/theme.ts`（基础 3 主题切换逻辑）
   - `resources/themes/tokyo-night.json`、`tokyo-night-storm.json`、`tokyo-night-light.json`
   - `src/styles/globals.css`（已含 CSS 变量 `--color-*` 定义）
   - `src-tauri/src/commands/theme.rs`（M1 中已有骨架，M10 在此基础上扩展）
   - `app_settings` 数据库表（M1/M2 已建立 schema）

2. **22 个 token 数量**：规格正文列出 19 个 token，`REQUIRED_TOKENS` 常量中补全至 22 个需与 M1 `resources/themes/tokyo-night.json` 实际 key 保持一致。实施 Task 1 前先 `cat resources/themes/tokyo-night.json | jq '.semanticTokens | keys'` 确认实际 key 列表，同步更新常量。

3. **Tailwind 动态类名**：`ThemePreview` 中使用内联 `style` 而非动态 Tailwind 类名，避免 JIT 扫描遗漏。

4. **color picker alpha 通道**：`<input type="color">` 不支持 alpha。含 alpha 的 token（如 `bg.selection: "#3d59a144"`）在 picker 中截断展示 6 位，用户修改后 alpha 信息丢失。此为已知限制，v3.0.0 范围内接受；hex 输入框仍支持手动输入 8 位 hex。

5. **`chrono` crate 依赖**：`write_custom_themes` 中使用 `chrono::Utc::now()`，需在 `Cargo.toml` 中添加 `chrono = { version = "0.4", features = ["serde"] }`（若 M1/M2 未添加）。
