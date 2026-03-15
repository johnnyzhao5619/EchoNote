# Unified Workspace and Local AI Notes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用硬切换方式把现有“批量转写 + 实时录音 + 文本查看/编辑 + 录音回放”整合为一个统一的录音/文档工作台，并补齐本地摘要、会议整理与模型管理能力。

**Architecture:** 当前系统的问题不是“少一个页面”，而是“缺少一个统一资产层”。本方案先建立 `workspace_items + workspace_assets` 作为全部录音、文稿、摘要、会议整理结果的单一事实源，再让批量转写、实时录音、时间线、日历都把产出写入该层。UI 上以新的 `workspace` 页替换 `batch_transcribe` 和 `realtime_record` 两个入口，模型管理上新增 Text AI provider/runtime 抽象，使用 `onnxruntime` 负责轻量摘要/抽取，使用本地 GGUF runtime 负责更强会议整理。 

**Tech Stack:** Python 3.10+, PySide6, SQLite, QSS, `onnxruntime`, 轻量文本提取库（`python-docx` / `pypdf`），本地 GGUF runtime（优先 `llama.cpp` 子进程封装），现有 `faster-whisper` / `ModelManager` / `SettingsManager` / `FileManager`。

---

## 1. 现状审查结论

### 1.1 当前代码结构的真实问题

1. 页面是按“采集方式”拆的，不是按“资产生命周期”拆的。
   - `ui/batch_transcribe/widget.py` 负责批量导入与任务队列。
   - `ui/realtime_record/widget.py` 负责实时录音与流式文本。
   - `ui/timeline/widget.py` 负责历史事件与附件浏览。
   - 结果：同一份会议资产被分散在三个页面和两套数据表达里。
2. 文本查看/编辑逻辑已经重复。
   - `ui/batch_transcribe/transcript_viewer.py` 是可编辑对话框。
   - `ui/common/transcript_translation_viewer.py` 是只读对比查看器。
   - 这两套能力最终都在处理“文本资产”，应该收敛为统一编辑器组件。
3. 持久化模型缺少“文档/笔记”这一层。
   - `transcription_tasks` 是任务表，不是长期内容表。
   - `event_attachments` 只能表达 `recording/transcript/translation`，并且强绑定 `calendar_events`。
   - 现在没有任何实体可以代表“独立于日历事件存在的一篇文档/一份会议纪要/一个可编辑文本”。
4. 模型管理只覆盖语音与翻译。
   - `core/models/manager.py` 现有语义是 speech/translation。
   - 摘要、抽取、会议整理、GGUF 文本模型没有 provider/runtime/catalog。
5. 存储路径定义有重复。
   - `data/storage/file_manager.py` 和 `core/realtime/config.py` 都在表达录音/转写/翻译目录。
   - 新工作台如果继续沿用散点路径定义，会继续扩大技术债。

### 1.2 与需求的对应结论

1. 需求 1 不是“新增一个 Notes 风格页签”，而是要引入统一资产工作台。
2. 需求 2 不能直接塞进 `translation` 或 `transcription`，需要新的 Text AI 能力层。
3. 参照 AnythingLLM 的正确借鉴点不是网页视觉，而是：
   - 工作区/知识资产集中管理
   - 模型与 provider 配置集中治理
   - 基于模板的会议整理产出
   - 文档先入库，再在工作区里衍生摘要/问答/整理结果
4. 用户已明确要求硬切换，因此不应保留“旧页面继续主用、新页面再复制一套”的双轨设计。

## 2. 产品与架构决策

### 2.1 页面信息架构

1. 用新的 `workspace` 页面替换侧边栏中的 `batch_transcribe` 与 `realtime_record`。
2. `timeline` 保留为“时间/事件视角”页面，但其打开文本、录音、摘要时都跳转/打开 `workspace` 资产。
3. `calendar_hub` 保留为日程管理页，不再承载文档编辑职责。
4. `workspace` 页面分为三列：
   - 左列：库筛选与集合切换（全部、录音、文档、会议、最近编辑、待整理）
   - 中列：资产列表（类似 Notes / AnythingLLM workspace documents）
   - 右列：编辑与回放面板（文本编辑器 + 录音播放器 + AI 操作区）

### 2.2 数据模型决策

1. 新增 `workspace_items` 表，表达“一个可被管理的内容单元”。
   - `item_type`: `recording` / `document` / `meeting_note` / `summary`
   - `source_kind`: `batch_transcription` / `realtime_recording` / `manual_import` / `ai_generated`
   - `source_event_id`, `source_task_id`: 可选回链
   - `title`, `status`, `primary_text_asset_id`, `primary_audio_asset_id`
2. 新增 `workspace_assets` 表，表达一个 item 关联的多个资产。
   - `asset_role`: `audio` / `transcript` / `translation` / `summary` / `meeting_brief` / `outline` / `action_items` / `source_document`
3. `transcription_tasks` 保留为运行态队列表，不再承担长期内容库职责。
4. `event_attachments` 不再作为主数据源。
   - 硬切换后，时间线和日历通过 `source_event_id` 查询 `workspace_items/workspace_assets`。
   - 旧附件读写路径统一移除，避免双写。

### 2.3 本地 AI 能力决策

1. 摘要能力拆成两条路径，避免“大模型是唯一答案”：
   - `extractive`: MiniLM embeddings + TextRank/MMR，用于稳定、快速、低资源摘要
   - `abstractive-small`: Flan-T5-Small ONNX INT8，用于本地轻量生成式摘要
2. 会议整理使用可选的本地 GGUF provider：
   - `gemma-3-1b/4b`
   - `apertus-8b` 作为高质量可选项
3. 默认策略：
   - 没有生成模型时，仍能输出 extractive summary
   - 有 Flan-T5 时，提供“简要摘要”
   - 有 GGUF 模型时，解锁“会议纪要 / 行动项 / 决策摘要 / 风险项”
4. 所有 AI 结果都写回 `workspace_assets`，并且默认可编辑，不是弹窗即弃。

### 2.4 模型管理决策

1. `core/models/manager.py` 升级为三大类模型统一入口：
   - Speech
   - Translation
   - Text AI
2. `ui/settings/model_management_page.py` 增加第三个标签页 `Text AI Models`。
3. Text AI 模型按 runtime/provider 分组，而不是把 ONNX 与 GGUF 平铺成一串按钮。
4. 设置页新增 `Workspace AI`/`Meeting AI` 配置页，管理：
   - 默认摘要策略
   - 默认会议整理模板
   - 首选生成模型
   - CPU/GPU/内存阈值与回退策略

## 3. 关键假设与建议

1. 假设：首期“文档”范围应覆盖 `txt / md / srt / docx / pdf`。
   - 理由：用户要求“全部录音和文档”，如果只支持文本文件会明显不完整；而这五类已经覆盖会议资料的主流输入。
2. 假设：时间线继续是事件视角，不与工作台合并为一个超重页面。
   - 理由：时间/日历筛选与文稿深度编辑是两种心智模型，强行合并会让页面职责发散。
3. 假设：GGUF 模型通过统一本地 runtime 抽象接入，而不是每个模型单独写一套调用逻辑。
   - 理由：Gemma/Apertus 只是模型族差异，不应该复制调用与下载逻辑。
4. 建议：把 `ui/batch_transcribe/transcript_viewer.py` 的编辑能力抽出来复用，而不是再做第三套编辑器。
   - 理由：当前编辑、保存、导出、搜索已经存在，可作为工作台右侧编辑器的行为基底。

## 4. 外部参考（用于设计取舍，不做直接照搬）

1. AnythingLLM GitHub README 强调“all your documents, tools, and agents in one private workspace”，适合作为本次“统一工作台”信息架构参考。
2. AnythingLLM 文档的 model/provider 配置和 appearance/customization 说明，适合参考其“集中模型管理 + 分层设置”的做法，而不是仿制网页布局。
3. AnythingLLM 的 Meeting Agent 文档证明会议整理应以模板化输出组织（summary / action items / decisions），而不是只给一个自由文本框。

参考链接：
- `https://github.com/Mintplex-Labs/anything-llm`
- `https://docs.anythingllm.com/customize/appearance`
- `https://docs.anythingllm.com/features/meeting-agent`
- `https://docs.anythingllm.com/features/chatting-with-documents/import-custom-models`

## 5. 实施顺序总览

1. 先建统一内容数据层，再改写入口。
2. 先收敛持久化与服务边界，再做 UI。
3. 先接入 extractive + ONNX 小模型，再加 GGUF 大模型。
4. 先完成硬切换与清理，再补文档、i18n、主题与回归矩阵。

### Task 1: 建立统一工作台数据模型

**Files:**
- Create: `core/workspace/__init__.py`
- Modify: `data/database/schema.sql`
- Modify: `data/database/models.py`
- Modify: `data/storage/file_manager.py`
- Test: `tests/unit/data/test_database_models.py`

**Step 1: Write the failing test**

```python
def test_workspace_item_round_trip(db_connection):
    item = WorkspaceItem(title="Weekly Sync", item_type="meeting_note")
    item.save(db_connection)

    loaded = WorkspaceItem.get_by_id(db_connection, item.id)
    assert loaded is not None
    assert loaded.title == "Weekly Sync"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/data/test_database_models.py -k workspace_item_round_trip -v`
Expected: FAIL with `NameError` or missing table/model errors for `WorkspaceItem`.

**Step 3: Write minimal implementation**

```python
class WorkspaceItem:
    ...

class WorkspaceAsset:
    ...
```

同时在 `data/database/schema.sql` 增加 `workspace_items` 与 `workspace_assets`，并在 `FileManager` 中增加统一的 `Workspace` 子目录解析，移除新的路径硬编码入口。

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/data/test_database_models.py -k "workspace_item or workspace_asset" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add data/database/schema.sql data/database/models.py data/storage/file_manager.py tests/unit/data/test_database_models.py core/workspace/__init__.py
git commit -m "feat: add workspace persistence model"
```

### Task 2: 建立工作台领域服务与导入编排

**Files:**
- Create: `core/workspace/manager.py`
- Create: `core/workspace/import_service.py`
- Create: `core/workspace/document_parser.py`
- Modify: `main.py`
- Modify: `utils/app_initializer.py`
- Test: `tests/unit/core/test_workspace_manager.py`

**Step 1: Write the failing test**

```python
def test_import_document_creates_workspace_item(workspace_manager, tmp_path):
    doc = tmp_path / "agenda.md"
    doc.write_text("# Agenda", encoding="utf-8")

    item_id = workspace_manager.import_document(str(doc))
    item = workspace_manager.get_item(item_id)

    assert item.item_type == "document"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/core/test_workspace_manager.py::test_import_document_creates_workspace_item -v`
Expected: FAIL because `WorkspaceManager` does not exist.

**Step 3: Write minimal implementation**

```python
class WorkspaceManager:
    def import_document(self, file_path: str) -> str:
        ...
```

实现要求：
- 支持 `txt/md/srt/docx/pdf` 文本抽取
- 所有导入都落到 `workspace_items/workspace_assets`
- `main.py` 初始化时注册 `workspace_manager`

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/core/test_workspace_manager.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/workspace/manager.py core/workspace/import_service.py core/workspace/document_parser.py main.py utils/app_initializer.py tests/unit/core/test_workspace_manager.py
git commit -m "feat: add workspace import manager"
```

### Task 3: 让批量转写与实时录音都写入工作台

**Files:**
- Modify: `core/transcription/manager.py`
- Modify: `core/realtime/recorder.py`
- Modify: `core/realtime/archiver.py`
- Modify: `core/timeline/manager.py`
- Modify: `ui/calendar_hub/widget.py`
- Test: `tests/unit/core/test_transcription_manager.py`
- Test: `tests/unit/core/test_realtime_recorder.py`
- Test: `tests/unit/core/test_timeline_manager.py`

**Step 1: Write the failing test**

```python
def test_completed_batch_task_publishes_workspace_item(manager, workspace_manager, temp_dir):
    audio = temp_dir / "meeting.wav"
    audio.write_bytes(b"fake")

    task_id = manager.add_task(str(audio))
    manager._publish_completed_task_to_workspace(task_id)

    assert workspace_manager.list_items()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/core/test_transcription_manager.py -k workspace -v`
Expected: FAIL because publish hook is missing.

**Step 3: Write minimal implementation**

```python
def _publish_completed_task_to_workspace(self, task_id: str) -> None:
    ...
```

实现要求：
- 批量转写完成后生成 `recording/document` 对应的 `workspace_item`
- 实时录音结束后生成带 `audio + transcript + translation` 资产的 `workspace_item`
- 若录音来自日历事件，写入 `source_event_id`
- 时间线和日历改为从工作台读取文本/录音资产，不再以 `event_attachments` 为主路径

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/core/test_transcription_manager.py tests/unit/core/test_realtime_recorder.py tests/unit/core/test_timeline_manager.py -k workspace -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/transcription/manager.py core/realtime/recorder.py core/realtime/archiver.py core/timeline/manager.py ui/calendar_hub/widget.py tests/unit/core/test_transcription_manager.py tests/unit/core/test_realtime_recorder.py tests/unit/core/test_timeline_manager.py
git commit -m "feat: publish transcription artifacts to workspace"
```

### Task 4: 引入本地 Text AI 引擎与模型目录

**Files:**
- Create: `engines/text_ai/__init__.py`
- Create: `engines/text_ai/base.py`
- Create: `engines/text_ai/extractive_engine.py`
- Create: `engines/text_ai/onnx_summarizer.py`
- Create: `engines/text_ai/gguf_chat_engine.py`
- Create: `core/models/text_ai_registry.py`
- Modify: `core/models/manager.py`
- Modify: `utils/app_initializer.py`
- Test: `tests/unit/core/test_text_ai_registry.py`
- Test: `tests/unit/core/test_model_manager.py`

**Step 1: Write the failing test**

```python
def test_model_manager_lists_text_ai_models(model_manager):
    models = model_manager.get_all_text_ai_models()
    assert any(model.model_id == "flan-t5-small-int8" for model in models)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/core/test_model_manager.py -k text_ai -v`
Expected: FAIL because Text AI registry APIs are missing.

**Step 3: Write minimal implementation**

```python
class TextAIModelInfo:
    ...

class ExtractiveEngine(TextAIEngine):
    ...
```

实现要求：
- ONNX 类模型与 GGUF 类模型统一进入 `ModelManager`
- `extractive` 不依赖大模型也可运行
- `gguf_chat_engine` 通过统一 runtime 配置调用，不在业务层散落 subprocess 逻辑

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/core/test_model_manager.py tests/unit/core/test_text_ai_registry.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add engines/text_ai core/models/text_ai_registry.py core/models/manager.py utils/app_initializer.py tests/unit/core/test_model_manager.py tests/unit/core/test_text_ai_registry.py
git commit -m "feat: add local text ai model runtime"
```

### Task 5: 建立摘要与会议整理服务

**Files:**
- Create: `core/workspace/summary_service.py`
- Create: `core/workspace/meeting_brief_service.py`
- Modify: `core/workspace/manager.py`
- Modify: `core/settings/manager.py`
- Modify: `config/default_config.json`
- Test: `tests/unit/core/test_workspace_summary_service.py`

**Step 1: Write the failing test**

```python
def test_generate_meeting_brief_writes_summary_assets(workspace_manager, workspace_item):
    result = workspace_manager.generate_meeting_brief(workspace_item.id)
    assert "summary_asset_id" in result
    assert "action_items_asset_id" in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/core/test_workspace_summary_service.py -v`
Expected: FAIL because summary service is missing.

**Step 3: Write minimal implementation**

```python
class SummaryService:
    def summarize(self, item_id: str, strategy: str = "extractive") -> dict:
        ...
```

实现要求：
- `extractive summary`
- `abstractive summary`
- `meeting brief`（至少输出 summary / decisions / action_items / next_steps）
- 结果全部落盘为独立资产，可再次编辑
- 设置默认策略来自 `workspace_ai.*` 配置，而非页面硬编码

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/core/test_workspace_summary_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/workspace/summary_service.py core/workspace/meeting_brief_service.py core/workspace/manager.py core/settings/manager.py config/default_config.json tests/unit/core/test_workspace_summary_service.py
git commit -m "feat: add local summary and meeting brief pipeline"
```

### Task 6: 升级模型管理与 AI 设置页面

**Files:**
- Modify: `ui/settings/model_management_page.py`
- Create: `ui/settings/workspace_ai_page.py`
- Modify: `ui/settings/widget.py`
- Modify: `resources/translations/i18n_outline.json`
- Modify: `resources/translations/zh_CN.json`
- Modify: `resources/translations/en_US.json`
- Modify: `resources/translations/fr_FR.json`
- Test: `tests/ui/test_model_management_page.py`
- Test: `tests/ui/test_workspace_ai_settings_page.py`
- Test: `tests/unit/test_i18n_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_model_management_exposes_text_ai_tab(qapp, mock_i18n, mock_settings_manager, model_manager):
    page = ModelManagementPage(mock_settings_manager, mock_i18n, model_manager)
    assert page.tabs.count() == 3
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_model_management_page.py -k text_ai -v`
Expected: FAIL because only speech/translation tabs exist.

**Step 3: Write minimal implementation**

```python
self.tabs.addTab(self.text_ai_tab, self.i18n.t("settings.model_management.text_ai_tab"))
```

实现要求：
- AnythingLLM 风格的“provider/runtime + model card + download/manage”结构
- `workspace_ai_page` 负责默认模板/策略，不把行为配置塞进模型页
- 所有新 i18n key 先更新 `i18n_outline.json`

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_model_management_page.py tests/ui/test_workspace_ai_settings_page.py tests/unit/test_i18n_outline_contract.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/settings/model_management_page.py ui/settings/workspace_ai_page.py ui/settings/widget.py resources/translations/i18n_outline.json resources/translations/zh_CN.json resources/translations/en_US.json resources/translations/fr_FR.json tests/ui/test_model_management_page.py tests/ui/test_workspace_ai_settings_page.py tests/unit/test_i18n_outline_contract.py
git commit -m "feat: add workspace ai settings and model management"
```

### Task 7: 落地新的 Workspace 页面并复用现有编辑/播放能力

**Files:**
- Create: `ui/workspace/__init__.py`
- Create: `ui/workspace/widget.py`
- Create: `ui/workspace/item_list.py`
- Create: `ui/workspace/editor_panel.py`
- Create: `ui/workspace/recording_panel.py`
- Modify: `ui/common/audio_player.py`
- Modify: `ui/batch_transcribe/transcript_viewer.py`
- Modify: `ui/common/transcript_translation_viewer.py`
- Test: `tests/ui/test_workspace_widget.py`
- Test: `tests/ui/test_timeline_audio_player.py`

**Step 1: Write the failing test**

```python
def test_workspace_widget_shows_editor_and_audio_regions(qapp, mock_i18n, workspace_manager):
    widget = WorkspaceWidget(workspace_manager, mock_i18n)
    assert widget.item_list is not None
    assert widget.editor_panel is not None
    assert widget.recording_panel is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_workspace_widget.py::test_workspace_widget_shows_editor_and_audio_regions -v`
Expected: FAIL because `WorkspaceWidget` does not exist.

**Step 3: Write minimal implementation**

```python
class WorkspaceWidget(BaseWidget):
    ...
```

实现要求：
- 右侧文本编辑器具备搜索、编辑、保存、导出
- 录音回放直接复用 `ui/common/audio_player.py`
- 旧的 `TranscriptViewerDialog` 编辑逻辑下沉到 `editor_panel`，避免第三套实现

**Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_workspace_widget.py tests/ui/test_timeline_audio_player.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/workspace ui/common/audio_player.py ui/batch_transcribe/transcript_viewer.py ui/common/transcript_translation_viewer.py tests/ui/test_workspace_widget.py tests/ui/test_timeline_audio_player.py
git commit -m "feat: add unified workspace ui"
```

### Task 8: 硬切换导航，移除旧页面重复职责

**Files:**
- Modify: `ui/navigation.py`
- Modify: `ui/sidebar.py`
- Modify: `ui/main_window.py`
- Delete: `ui/batch_transcribe/widget.py`
- Delete: `ui/realtime_record/widget.py`
- Modify: `tests/unit/test_main_window_search.py`
- Modify: `tests/unit/test_main_window.py`
- Modify: `tests/ui/test_settings_widget.py`
- Test: `tests/unit/test_main_window_search.py`
- Test: `tests/unit/test_main_window.py`

**Step 1: Write the failing test**

```python
def test_sidebar_exposes_workspace_entry():
    assert any(item.page_name == "workspace" for item in NAV_ITEMS)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_main_window_search.py tests/unit/test_main_window.py -k workspace -v`
Expected: FAIL because navigation still exposes `batch_transcribe` and `realtime_record`.

**Step 3: Write minimal implementation**

```python
NAV_ITEMS = (
    NavigationItem(page_name="workspace", ...),
    ...
)
```

实现要求：
- 侧边栏替换为 `workspace / calendar_hub / timeline / settings`
- `MainWindow._create_pages()` 注册 `WorkspaceWidget`
- 删除旧页面入口与重复跳转逻辑
- 仅保留底层服务，不保留页面级重复实现

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_main_window_search.py tests/unit/test_main_window.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ui/navigation.py ui/sidebar.py ui/main_window.py tests/unit/test_main_window_search.py tests/unit/test_main_window.py tests/ui/test_settings_widget.py
git rm ui/batch_transcribe/widget.py ui/realtime_record/widget.py
git commit -m "refactor: hard switch shell to unified workspace"
```

### Task 9: 主题、文档、索引与最终清理

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/README.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `resources/themes/light.qss`
- Modify: `resources/themes/dark.qss`
- Modify: `resources/themes/theme_outline.json`
- Modify: `ui/constants.py`
- Test: `tests/unit/test_theme_outline_contract.py`

**Step 1: Write the failing test**

```python
def test_theme_outline_covers_workspace_roles():
    assert "workspace-editor-panel" in load_outline_roles()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_theme_outline_contract.py -q`
Expected: FAIL because new workspace semantic roles are not declared.

**Step 3: Write minimal implementation**

```python
ROLE_WORKSPACE_EDITOR_PANEL = "workspace-editor-panel"
```

实现要求：
- 新页面所有 role 进入 `theme_outline.json`
- `AGENTS.md`、`docs/README.md` 更新到新的目录与职责
- `CHANGELOG.md` 记录硬切换与维护性收益
- 删除已废弃说明文档与无效路径引用

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_theme_outline_contract.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add AGENTS.md docs/README.md README.md CHANGELOG.md resources/themes/light.qss resources/themes/dark.qss resources/themes/theme_outline.json ui/constants.py
git commit -m "docs: finalize workspace rollout references"
```

## 6. 完整回归命令

按阶段执行，不要一次性全跑到失败后再回头定位：

```bash
pytest tests/unit/data/test_database_models.py -v
pytest tests/unit/core/test_workspace_manager.py -v
pytest tests/unit/core/test_transcription_manager.py tests/unit/core/test_realtime_recorder.py tests/unit/core/test_timeline_manager.py -v
pytest tests/unit/core/test_model_manager.py tests/unit/core/test_text_ai_registry.py tests/unit/core/test_workspace_summary_service.py -v
pytest tests/ui/test_model_management_page.py tests/ui/test_workspace_ai_settings_page.py tests/ui/test_workspace_widget.py -v
pytest tests/unit/test_main_window.py tests/unit/test_main_window_search.py -v
pytest tests/unit/test_i18n_outline_contract.py tests/unit/test_theme_outline_contract.py -v
pytest tests/ui -v
```

## 7. 验收标准

1. 用户只能看到一个统一的录音/文档工作台入口。
2. 批量转写、实时录音、手动导入的文档都能在同一列表中管理。
3. 文本可编辑、可保存、可导出，录音可回放，且两者在同一工作台联动。
4. 摘要与会议整理支持本地运行，并且无大模型时仍有 extractive 可用回退。
5. 模型管理可同时管理 speech / translation / text-ai 三类模型。
6. 时间线与日历不再依赖旧附件主路径，而是消费统一工作台资产。
7. 旧页面级重复逻辑被删除，而不是继续并存。

## 8. 风险提示

1. `event_attachments` 到 `workspace_assets` 的硬切换会影响 timeline/calendar 查询路径，这是本次改造的最大风险点，必须优先用测试封住。
2. GGUF runtime 的打包和跨平台可执行文件分发会影响发布时间，建议先把 runtime 抽象与 UI 落地，再补平台二进制打包。
3. 文档解析（尤其 PDF）可能带来依赖与文本质量波动，首期应把抽取失败明确暴露给 UI，而不是静默吞掉。

Plan complete and saved to docs/plans/2026-03-15-unified-workspace-and-local-ai.md. Two execution options:

1. Subagent-Driven (this session) - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. Parallel Session (separate) - Open a new session with executing-plans, batch execution with checkpoints

Which approach?
