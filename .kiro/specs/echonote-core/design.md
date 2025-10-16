# EchoNote 技术设计文档

## 概述

EchoNote 采用模块化、分层架构设计，遵循关注点分离原则。应用分为 UI 层、业务逻辑层、引擎层和数据层，确保各层职责清晰、易于测试和维护。

### 设计原则

1. **本地优先（Local-First）**：所有核心功能离线可用，云服务仅作为可选增强
2. **可插拔架构**：语音引擎、翻译服务、日历集成均采用插件模式
3. **DRY 原则**：避免代码重复，提取共享逻辑到工具模块
4. **性能优先**：异步处理、流式数据、资源限制
5. **安全第一**：敏感数据加密存储，安全的外部 API 通信

### 技术栈

- **UI 框架**：PyQt6
- **语音引擎**：faster-whisper（默认）、OpenAI/Google/Azure（可选）
- **数据库**：SQLite + SQLCipher（加密）
- **音频处理**：PyAudio、soundfile、librosa
- **HTTP 客户端**：httpx（同步/异步）
- **OAuth**：httpx（实际实现，轻量级）
- **任务调度**：APScheduler（BackgroundScheduler）
- **加密**：cryptography（AES-256）
- **打包**：PyInstaller（Windows）、py2app（macOS）

### 技术选择说明

**实际实现与设计文档的差异**：

1. **OAuth 实现**：使用 `httpx` 而非 `authlib`

   - 原因：httpx 更轻量，功能完全满足 OAuth 2.0 需求
   - 优势：减少依赖，统一 HTTP 客户端
   - 影响：无，OAuth 流程完全符合标准

2. **任务调度器**：使用 `BackgroundScheduler` 而非 `AsyncIOScheduler`

   - 原因：当前代码架构为同步模式，BackgroundScheduler 更适合
   - 优势：简化实现，避免异步复杂性
   - 影响：无，定时任务功能完全正常

3. **HTTP 客户端模式**：主要使用同步模式
   - 原因：日历同步等操作不需要高并发
   - 优势：代码更简洁，易于调试
   - 影响：无，性能满足需求

## 架构设计

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                         UI Layer (PyQt6)                     │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │ Sidebar  │  Batch   │ Realtime │ Calendar │ Timeline │  │
│  │          │Transcribe│  Record  │   Hub    │   View   │  │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Core Business Logic                     │
│  ┌──────────────┬──────────────┬──────────────────────────┐ │
│  │ Transcription│   Calendar   │   Timeline   │  Settings │ │
│  │   Manager    │   Manager    │   Manager    │  Manager  │ │
│  └──────────────┴──────────────┴──────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Engine Layer                            │
│  ┌──────────────┬──────────────┬──────────────────────────┐ │
│  │   Speech     │  Translation │   Audio      │  Calendar │ │
│  │   Engines    │   Engines    │   Capture    │  Sync     │ │
│  └──────────────┴──────────────┴──────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                       Data Layer                             │
│  ┌──────────────┬──────────────┬──────────────────────────┐ │
│  │   Database   │  File System │   Config     │  Security │ │
│  │  (SQLite)    │   Storage    │   Manager    │  Manager  │ │
│  └──────────────┴──────────────┴──────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 目录结构

```
echonote/
├── main.py                          # 应用入口
├── requirements.txt                 # Python 依赖
├── config/
│   ├── default_config.json         # 默认配置
│   └── app_config.py               # 配置加载器
├── ui/                              # UI 层
│   ├── main_window.py              # 主窗口
│   ├── sidebar.py                  # 侧边栏导航
│   ├── batch_transcribe/           # 批量转录 UI
│   │   ├── __init__.py
│   │   ├── widget.py               # 主界面
│   │   └── task_item.py            # 任务列表项
│   ├── realtime_record/            # 实时录制 UI
│   │   ├── __init__.py
│   │   ├── widget.py
│   │   └── audio_visualizer.py    # 音频波形可视化
│   ├── calendar_hub/               # 日历中心 UI
│   │   ├── __init__.py
│   │   ├── widget.py
│   │   ├── calendar_view.py       # 月/周/日视图
│   │   └── event_dialog.py        # 事件创建/编辑对话框
│   ├── timeline/                   # 时间线 UI
│   │   ├── __init__.py
│   │   ├── widget.py
│   │   └── event_card.py          # 事件卡片
│   ├── settings/                   # 设置 UI
│   │   ├── __init__.py
│   │   └── widget.py
│   └── common/                     # 共享 UI 组件
│       ├── __init__.py
│       ├── notification.py        # 桌面通知
│       └── progress_bar.py        # 进度条
├── core/                            # 业务逻辑层
│   ├── transcription/
│   │   ├── __init__.py
│   │   ├── manager.py             # 转录管理器
│   │   ├── task_queue.py          # 任务队列
│   │   └── format_converter.py    # 格式转换器（txt/srt/md）
│   ├── realtime/
│   │   ├── __init__.py
│   │   ├── recorder.py            # 实时录制管理器
│   │   └── audio_buffer.py        # 音频缓冲区
│   ├── calendar/
│   │   ├── __init__.py
│   │   ├── manager.py             # 日历管理器
│   │   └── sync_scheduler.py     # 同步调度器
│   ├── timeline/
│   │   ├── __init__.py
│   │   ├── manager.py             # 时间线管理器
│   │   └── auto_task_scheduler.py # 自动任务调度器
│   └── settings/
│       ├── __init__.py
│       └── manager.py             # 设置管理器
├── engines/                         # 引擎层
│   ├── speech/
│   │   ├── __init__.py
│   │   ├── base.py                # 抽象基类
│   │   ├── faster_whisper_engine.py
│   │   ├── openai_engine.py
│   │   ├── google_engine.py
│   │   └── azure_engine.py
│   ├── translation/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── google_translate.py
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── capture.py             # 音频捕获
│   │   └── vad.py                 # 语音活动检测
│   └── calendar_sync/
│       ├── __init__.py
│       ├── base.py
│       ├── google_calendar.py
│       └── outlook_calendar.py
├── data/                            # 数据层
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py          # 数据库连接管理
│   │   ├── models.py              # ORM 模型
│   │   └── migrations/            # 数据库迁移脚本
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── file_manager.py        # 文件存储管理
│   │   └── cache_manager.py       # 缓存管理
│   └── security/
│       ├── __init__.py
│       ├── encryption.py          # 加密/解密
│       └── oauth_manager.py       # OAuth token 管理
├── utils/                           # 工具模块
│   ├── __init__.py
│   ├── i18n.py                    # 国际化
│   ├── logger.py                  # 日志
│   ├── validators.py              # 输入验证
│   └── constants.py               # 常量定义
├── resources/                       # 资源文件
│   ├── icons/
│   ├── themes/
│   │   ├── light.qss
│   │   └── dark.qss
│   └── translations/
│       ├── zh_CN.json
│       ├── en_US.json
│       └── fr_FR.json
└── tests/                           # 测试
    ├── unit/
    ├── integration/
    └── fixtures/
```

## 核心组件设计

### 1. 批量转录系统

#### 1.1 转录管理器（TranscriptionManager）

**职责**：

- 管理转录任务队列
- 协调语音引擎执行转录
- 处理任务状态更新和通知

**关键方法**：

```python
class TranscriptionManager:
    def __init__(self, db_connection, speech_engine, config):
        self.task_queue = TaskQueue(max_concurrent=config.max_concurrent_tasks)
        self.speech_engine = speech_engine
        self.db = db_connection

    async def add_task(self, file_path: str, options: dict) -> str:
        """添加转录任务到队列，返回任务 ID"""

    async def start_processing(self):
        """开始处理队列中的任务"""

    async def process_task(self, task_id: str):
        """处理单个转录任务"""

    def get_task_status(self, task_id: str) -> dict:
        """获取任务状态"""

    def cancel_task(self, task_id: str):
        """取消任务"""
```

**数据流**：

```
用户选择文件 → 创建任务记录（DB）→ 加入队列 →
语音引擎处理 → 更新进度（DB + UI）→
生成内部格式 → 用户选择导出格式 → 保存文件 → 发送通知
```

#### 1.2 任务队列（TaskQueue）

**职责**：

- 维护待处理任务列表
- 控制并发执行数量
- 提供任务优先级管理

**实现要点**：

- 使用 `asyncio.Queue` 实现异步任务队列
- 使用 `asyncio.Semaphore` 限制并发数量
- 任务状态：`pending` → `processing` → `completed`/`failed`

#### 1.3 格式转换器（FormatConverter）

**职责**：

- 将内部统一格式转换为用户选择的输出格式

**支持格式**：

- **内部格式**：JSON，包含时间戳和文本片段
  ```json
  {
    "segments": [
      { "start": 0.0, "end": 2.5, "text": "Hello world" },
      { "start": 2.5, "end": 5.0, "text": "This is a test" }
    ]
  }
  ```
- **TXT**：纯文本，无时间戳
- **SRT**：字幕格式，包含序号、时间戳和文本
- **MD**：Markdown 格式，带时间戳标记

### 2. 实时转录与录制系统

#### 2.1 实时录制管理器（RealtimeRecorder）

**职责**：

- 管理音频捕获
- 协调实时转录和翻译
- 保存录音文件和转录文本

**关键方法**：

```python
class RealtimeRecorder:
    def __init__(self, audio_capture, speech_engine, translation_engine, db):
        self.audio_capture = audio_capture
        self.speech_engine = speech_engine
        self.translation_engine = translation_engine
        self.audio_buffer = AudioBuffer()
        self.db = db

    async def start_recording(self, input_source: str, options: dict):
        """开始录制和实时转录"""

    async def stop_recording(self) -> dict:
        """停止录制，返回录音文件路径和转录文本"""

    def get_transcription_stream(self) -> AsyncIterator[str]:
        """获取实时转录文本流"""

    def get_translation_stream(self) -> AsyncIterator[str]:
        """获取实时翻译文本流"""
```

**实现要点（参考 WhisperLiveKit）**：

1. **音频捕获**：

   - 使用 PyAudio 捕获音频流
   - 采样率：16kHz（Whisper 标准）
   - 缓冲区大小：512 samples（约 32ms）

2. **VAD（语音活动检测）**：

   - 使用 `silero-vad` 或 `webrtcvad`
   - 检测语音段落的开始和结束
   - 静音阈值：2 秒

3. **滑动窗口机制**：

   - 窗口大小：30 秒音频
   - 重叠：5 秒（确保上下文连贯）
   - 当检测到语音段落结束时，将窗口内音频发送给 Whisper

4. **异步处理流程**：
   ```
   音频捕获线程 → 音频缓冲区 → VAD 检测 →
   语音段落提取 → Whisper 转录（异步） →
   UI 更新（Qt Signal）→ 翻译（可选，异步） → UI 更新
   ```

#### 2.2 音频缓冲区（AudioBuffer）

**职责**：

- 缓存实时音频数据
- 提供滑动窗口访问
- 管理内存使用

**实现**：

```python
class AudioBuffer:
    def __init__(self, max_duration_seconds=60):
        self.buffer = collections.deque(maxlen=max_duration_seconds * 16000)

    def append(self, audio_chunk: np.ndarray):
        """添加音频块"""

    def get_window(self, duration_seconds: int) -> np.ndarray:
        """获取最近 N 秒的音频"""

    def clear(self):
        """清空缓冲区"""
```

### 3. 日历系统

#### 3.1 日历管理器（CalendarManager）

**职责**：

- 管理本地日历事件的 CRUD 操作
- 协调外部日历同步
- 处理事件查询和过滤

**关键方法**：

```python
class CalendarManager:
    def __init__(self, db, sync_adapters: dict):
        self.db = db
        self.sync_adapters = sync_adapters  # {'google': GoogleCalendarAdapter, ...}

    async def create_event(self, event_data: dict, sync_to: list = None) -> str:
        """创建本地事件，可选同步到外部日历"""

    async def update_event(self, event_id: str, event_data: dict):
        """更新本地事件"""

    async def delete_event(self, event_id: str):
        """删除本地事件"""

    def get_events(self, start_date, end_date, filters: dict = None) -> list:
        """查询事件"""

    async def sync_external_calendar(self, provider: str):
        """同步外部日历"""
```

**事件数据模型**：

```python
@dataclass
class CalendarEvent:
    id: str                      # UUID
    title: str
    event_type: str              # Event/Task/Appointment
    start_time: datetime
    end_time: datetime
    location: str = None
    attendees: list = None       # ['email1', 'email2']
    description: str = None
    reminder_minutes: int = None
    recurrence_rule: str = None  # iCalendar RRULE 格式
    source: str = 'local'        # local/google/outlook
    external_id: str = None      # 外部日历的事件 ID
    is_readonly: bool = False    # 外部同步的事件为只读
    attachments: list = None     # [{'type': 'recording', 'path': '...'}]
    created_at: datetime
    updated_at: datetime
```

#### 3.2 外部日历同步适配器

**基类设计**：

```python
class CalendarSyncAdapter(ABC):
    @abstractmethod
    async def authenticate(self, credentials: dict) -> dict:
        """OAuth 认证，返回 token"""

    @abstractmethod
    async def fetch_events(self, start_date, end_date, last_sync_token=None) -> dict:
        """获取事件，支持增量同步"""

    @abstractmethod
    async def push_event(self, event: CalendarEvent) -> str:
        """推送事件到外部日历，返回外部 ID"""

    @abstractmethod
    async def revoke_access(self):
        """撤销访问权限"""
```

**Google Calendar 适配器实现要点**：

- 使用 Google Calendar API v3
- OAuth 2.0 流程：
  1. 生成授权 URL
  2. 用户在浏览器中授权
  3. 接收回调并交换 token
  4. 存储 refresh_token（加密）
- 增量同步：使用 `syncToken` 参数
- 速率限制：每用户每秒 10 个请求

**Outlook Calendar 适配器实现要点**：

- 使用 Microsoft Graph API
- OAuth 2.0 流程类似 Google
- 增量同步：使用 `deltaLink`
- 速率限制：每应用每秒 2000 个请求

#### 3.3 同步调度器（SyncScheduler）

**职责**：

- 定期触发外部日历同步
- 处理同步冲突和错误

**实现**：

```python
class SyncScheduler:
    def __init__(self, calendar_manager, interval_minutes=15):
        self.calendar_manager = calendar_manager
        self.interval = interval_minutes
        self.scheduler = AsyncIOScheduler()

    def start(self):
        """启动定时同步"""
        self.scheduler.add_job(
            self._sync_all,
            'interval',
            minutes=self.interval
        )
        self.scheduler.start()

    async def _sync_all(self):
        """同步所有已连接的外部日历"""
```

### 4. 时间线系统

#### 4.1 时间线管理器（TimelineManager）

**职责**：

- 提供时间线视图的数据
- 管理事件的自动任务配置
- 处理搜索和过滤

**关键方法**：

```python
class TimelineManager:
    def __init__(self, calendar_manager, db):
        self.calendar_manager = calendar_manager
        self.db = db

    def get_timeline_events(self, center_time: datetime,
                           past_days: int, future_days: int,
                           page: int = 0, page_size: int = 50) -> dict:
        """获取时间线事件，分页加载"""

    async def set_auto_task(self, event_id: str, task_config: dict):
        """为事件设置自动任务"""

    def search_events(self, query: str, filters: dict) -> list:
        """搜索事件和关联的转录文本"""

    def get_event_artifacts(self, event_id: str) -> dict:
        """获取事件关联的录音和转录文本"""
```

**时间线数据结构**：

```python
{
    "current_time": "2025-10-07T10:00:00",
    "past_events": [
        {
            "event": CalendarEvent,
            "artifacts": {
                "recording": "/path/to/recording.mp3",
                "transcript": "/path/to/transcript.txt"
            }
        }
    ],
    "future_events": [
        {
            "event": CalendarEvent,
            "auto_tasks": {
                "enable_transcription": True,
                "enable_recording": True
            }
        }
    ]
}
```

#### 4.2 自动任务调度器（AutoTaskScheduler）

**职责**：

- 监控即将开始的事件
- 在事件开始时自动启动配置的任务
- 发送提醒通知

**实现**：

```python
class AutoTaskScheduler:
    def __init__(self, timeline_manager, realtime_recorder):
        self.timeline_manager = timeline_manager
        self.realtime_recorder = realtime_recorder
        self.scheduler = AsyncIOScheduler()

    def start(self):
        """启动调度器，每分钟检查一次"""
        self.scheduler.add_job(
            self._check_upcoming_events,
            'interval',
            minutes=1
        )
        self.scheduler.start()

    async def _check_upcoming_events(self):
        """检查即将开始的事件"""
        now = datetime.now()
        upcoming = self.timeline_manager.get_timeline_events(
            center_time=now,
            past_days=0,
            future_days=0.01  # 未来 15 分钟
        )

        for event_data in upcoming['future_events']:
            event = event_data['event']
            auto_tasks = event_data['auto_tasks']

            # 提前 5 分钟发送通知
            if event.start_time - now <= timedelta(minutes=5):
                self._send_reminder_notification(event, auto_tasks)

            # 事件开始时启动任务
            if event.start_time <= now <= event.end_time:
                await self._start_auto_tasks(event, auto_tasks)
```

### 5. 语音引擎系统

#### 5.1 语音引擎基类

**设计**：

```python
class SpeechEngine(ABC):
    @abstractmethod
    def get_name(self) -> str:
        """引擎名称"""

    @abstractmethod
    def get_supported_languages(self) -> list:
        """支持的语言列表"""

    @abstractmethod
    async def transcribe_file(self, audio_path: str, language: str = None) -> dict:
        """转录音频文件，返回内部格式"""

    @abstractmethod
    async def transcribe_stream(self, audio_chunk: np.ndarray,
                               language: str = None) -> str:
        """转录音频流，返回文本片段"""

    @abstractmethod
    def get_config_schema(self) -> dict:
        """返回引擎配置的 JSON Schema"""
```

#### 5.2 Faster-Whisper 引擎实现

**实现要点（参考 faster-whisper 和 WhisperLiveKit）**：

```python
class FasterWhisperEngine(SpeechEngine):
    def __init__(self, model_size='base', device='cpu', compute_type='int8'):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type
        )
        self.vad_model = self._load_vad_model()

    async def transcribe_file(self, audio_path: str, language: str = None) -> dict:
        """批量转录：直接处理整个文件"""
        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500
            )
        )

        return {
            "segments": [
                {
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text
                }
                for seg in segments
            ],
            "language": info.language
        }

    async def transcribe_stream(self, audio_chunk: np.ndarray,
                               language: str = None) -> str:
        """实时转录：使用 VAD + 滑动窗口"""
        # 1. VAD 检测语音活动
        speech_timestamps = self.vad_model(audio_chunk, return_seconds=True)

        if not speech_timestamps:
            return ""

        # 2. 提取语音段落
        speech_audio = self._extract_speech(audio_chunk, speech_timestamps)

        # 3. 转录
        segments, _ = self.model.transcribe(
            speech_audio,
            language=language,
            beam_size=1,  # 实时转录使用较小的 beam size
            vad_filter=False  # 已经做过 VAD
        )

        return " ".join([seg.text for seg in segments])
```

**模型选择与性能**：

- `tiny`: 最快，准确度较低，适合实时转录
- `base`: 平衡，默认选项
- `small`: 较准确，速度适中
- `medium`: 高准确度，速度较慢
- `large`: 最准确，速度最慢，适合批量转录

**GPU 加速**：

- CUDA（NVIDIA）：`device='cuda'`, `compute_type='float16'`
- CoreML（Apple Silicon）：`device='cpu'`, `compute_type='int8'`（faster-whisper 会自动使用 CoreML）

#### 5.3 云服务引擎实现

**OpenAI Whisper API**：

```python
class OpenAIEngine(SpeechEngine):
    def __init__(self, api_key: str):
        self.client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"}
        )

    async def transcribe_file(self, audio_path: str, language: str = None) -> dict:
        with open(audio_path, 'rb') as f:
            response = await self.client.post(
                "/audio/transcriptions",
                files={"file": f},
                data={
                    "model": "whisper-1",
                    "language": language,
                    "response_format": "verbose_json",
                    "timestamp_granularities": ["segment"]
                }
            )

        data = response.json()
        return {
            "segments": [
                {
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"]
                }
                for seg in data["segments"]
            ],
            "language": data["language"]
        }
```

**使用量跟踪**：

```python
class UsageTracker:
    def __init__(self, db):
        self.db = db

    def record_usage(self, engine: str, duration_seconds: float, cost: float):
        """记录 API 使用量"""

    def get_monthly_usage(self, engine: str) -> dict:
        """获取本月使用统计"""
```

## 数据模型

### 数据库 Schema

#### 1. 转录任务表（transcription_tasks）

```sql
CREATE TABLE transcription_tasks (
    id TEXT PRIMARY KEY,                    -- UUID
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER,
    audio_duration REAL,                    -- 秒
    status TEXT NOT NULL,                   -- pending/processing/completed/failed
    progress REAL DEFAULT 0,                -- 0-100
    language TEXT,
    engine TEXT NOT NULL,
    output_format TEXT,                     -- txt/srt/md
    output_path TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_tasks_status ON transcription_tasks(status);
CREATE INDEX idx_tasks_created ON transcription_tasks(created_at);
```

#### 2. 日历事件表（calendar_events）

```sql
CREATE TABLE calendar_events (
    id TEXT PRIMARY KEY,                    -- UUID
    title TEXT NOT NULL,
    event_type TEXT NOT NULL,               -- Event/Task/Appointment
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    location TEXT,
    attendees TEXT,                         -- JSON array
    description TEXT,
    reminder_minutes INTEGER,
    recurrence_rule TEXT,                   -- iCalendar RRULE
    source TEXT NOT NULL DEFAULT 'local',   -- local/google/outlook
    external_id TEXT,                       -- 外部日历的事件 ID
    is_readonly BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_time ON calendar_events(start_time, end_time);
CREATE INDEX idx_events_source ON calendar_events(source);
```

#### 3. 事件附件表（event_attachments）

```sql
CREATE TABLE event_attachments (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    attachment_type TEXT NOT NULL,          -- recording/transcript
    file_path TEXT NOT NULL,
    file_size INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES calendar_events(id) ON DELETE CASCADE
);

CREATE INDEX idx_attachments_event ON event_attachments(event_id);
```

#### 4. 自动任务配置表（auto_task_configs）

```sql
CREATE TABLE auto_task_configs (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    enable_transcription BOOLEAN DEFAULT 0,
    enable_recording BOOLEAN DEFAULT 0,
    transcription_language TEXT,
    enable_translation BOOLEAN DEFAULT 0,
    translation_target_language TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES calendar_events(id) ON DELETE CASCADE
);

CREATE INDEX idx_auto_tasks_event ON auto_task_configs(event_id);
```

#### 5. 外部日历同步状态表（calendar_sync_status）

```sql
CREATE TABLE calendar_sync_status (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,                 -- google/outlook
    user_email TEXT,
    last_sync_time TIMESTAMP,
    sync_token TEXT,                        -- 增量同步 token
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 6. 应用配置表（app_settings）

```sql
CREATE TABLE app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 7. API 使用统计表（api_usage）

```sql
CREATE TABLE api_usage (
    id TEXT PRIMARY KEY,
    engine TEXT NOT NULL,                   -- openai/google/azure
    duration_seconds REAL NOT NULL,
    cost REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_usage_engine_time ON api_usage(engine, timestamp);
```

### 配置文件结构

#### 应用配置（config/app_config.json）

```json
{
  "version": "1.0.0",
  "database": {
    "path": "~/.echonote/data.db",
    "encryption_enabled": true
  },
  "transcription": {
    "default_engine": "faster-whisper",
    "default_output_format": "txt",
    "default_save_path": "~/Documents/EchoNote/Transcripts",
    "max_concurrent_tasks": 2,
    "faster_whisper": {
      "model_size": "base",
      "device": "cpu",
      "compute_type": "int8"
    }
  },
  "realtime": {
    "default_input_source": "default",
    "default_gain": 1.0,
    "recording_format": "wav",
    "recording_save_path": "~/Documents/EchoNote/Recordings",
    "vad_threshold": 0.5,
    "silence_duration_ms": 2000
  },
  "calendar": {
    "default_view": "week",
    "sync_interval_minutes": 15,
    "colors": {
      "local": "#2196F3",
      "google": "#EA4335",
      "outlook": "#FF6F00"
    }
  },
  "timeline": {
    "past_days": 30,
    "future_days": 30,
    "reminder_minutes": 5,
    "page_size": 50
  },
  "ui": {
    "theme": "light",
    "language": "zh_CN"
  },
  "security": {
    "encryption_algorithm": "AES-256-GCM"
  }
}
```

#### 加密存储的敏感配置（~/.echonote/secrets.enc）

```json
{
  "api_keys": {
    "openai": "sk-...",
    "google_speech": "...",
    "azure_speech": "..."
  },
  "oauth_tokens": {
    "google_calendar": {
      "access_token": "...",
      "refresh_token": "...",
      "expires_at": "2025-10-08T10:00:00"
    },
    "outlook_calendar": {
      "access_token": "...",
      "refresh_token": "...",
      "expires_at": "2025-10-08T10:00:00"
    }
  }
}
```

## UI 设计

### 主窗口布局

```
┌─────────────────────────────────────────────────────────────┐
│  EchoNote                                          [- □ ×]   │
├──────────┬──────────────────────────────────────────────────┤
│          │                                                   │
│  [图标]  │                                                   │
│  批量转录 │                                                   │
│          │                                                   │
│  [图标]  │                                                   │
│  实时录制 │              主内容区域                            │
│          │                                                   │
│  [图标]  │                                                   │
│  日历中心 │                                                   │
│          │                                                   │
│  [图标]  │                                                   │
│  时间线   │                                                   │
│          │                                                   │
│  [图标]  │                                                   │
│  设置     │                                                   │
│          │                                                   │
└──────────┴──────────────────────────────────────────────────┘
```

### 批量转录界面

```
┌─────────────────────────────────────────────────────────────┐
│  批量转录                                                     │
├─────────────────────────────────────────────────────────────┤
│  [导入文件] [导入文件夹] [清空队列]    引擎: [faster-whisper▼] │
├─────────────────────────────────────────────────────────────┤
│  任务队列 (3 个任务)                                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 📄 interview_01.mp3                    [处理中] 45%   │  │
│  │    大小: 25.3 MB | 时长: 15:30 | 语言: 中文            │  │
│  │    [████████████░░░░░░░░░░░░░░]                       │  │
│  │    [暂停] [取消]                                       │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │ 📄 meeting_notes.m4a                   [待处理]       │  │
│  │    大小: 18.7 MB | 时长: 12:45 | 语言: 英文            │  │
│  │    [开始] [删除]                                       │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │ 📄 lecture_recording.wav               [已完成] ✓     │  │
│  │    大小: 45.2 MB | 时长: 30:00 | 语言: 中文            │  │
│  │    输出: /Documents/EchoNote/lecture_recording.txt    │  │
│  │    [查看] [导出为...] [删除]                           │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 实时录制界面

```
┌─────────────────────────────────────────────────────────────┐
│  实时录制与翻译                                               │
├─────────────────────────────────────────────────────────────┤
│  音频输入: [系统麦克风 ▼]    增益: [━━━━━●━━━━] 1.2x        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  音频波形                                              │  │
│  │  ▁▂▃▅▇█▇▅▃▂▁▁▂▃▅▇█▇▅▃▂▁▁▂▃▅▇█▇▅▃▂▁                    │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  源语言: [中文 ▼]    [●开始录制]    录制时长: 00:00:00      │
│                                                              │
│  ☑ 启用翻译    目标语言: [英文 ▼]                            │
├─────────────────────────────────────────────────────────────┤
│  转录文本:                                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  大家好，欢迎来到今天的会议。我们今天主要讨论...        │  │
│  │                                                        │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  翻译文本:                                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Hello everyone, welcome to today's meeting. Today    │  │
│  │  we will mainly discuss...                            │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  [导出转录] [导出翻译] [保存录音]                             │
└─────────────────────────────────────────────────────────────┘
```

### 日历中心界面

```
┌─────────────────────────────────────────────────────────────┐
│  日历中心                                                     │
├─────────────────────────────────────────────────────────────┤
│  [月] [周] [日]    2025年10月    [<] [今天] [>]              │
│                                                              │
│  已连接: ● Google (user@gmail.com)  ● Outlook (user@...)   │
│  [+ 添加账户]                                                │
├─────────────────────────────────────────────────────────────┤
│  周视图                                                      │
│  ┌──────┬──────┬──────┬──────┬──────┬──────┬──────┐        │
│  │ 周一 │ 周二 │ 周三 │ 周四 │ 周五 │ 周六 │ 周日 │        │
│  │  6   │  7   │  8   │  9   │  10  │  11  │  12  │        │
│  ├──────┼──────┼──────┼──────┼──────┼──────┼──────┤        │
│  │      │ 10:00│      │      │      │      │      │        │
│  │      │ 团队 │      │      │      │      │      │        │
│  │      │ 会议 │      │      │      │      │      │        │
│  │      │ (蓝) │      │      │      │      │      │        │
│  │      ├──────┤      │      │      │      │      │        │
│  │      │ 14:00│      │      │      │      │      │        │
│  │      │ 客户 │      │      │      │      │      │        │
│  │      │ 电话 │      │      │      │      │      │        │
│  │      │ (红) │      │      │      │      │      │        │
│  └──────┴──────┴──────┴──────┴──────┴──────┴──────┘        │
│                                                              │
│  [+ 创建事件]                                                │
└─────────────────────────────────────────────────────────────┘
```

### 时间线界面

```
┌─────────────────────────────────────────────────────────────┐
│  智能时间线                                                   │
├─────────────────────────────────────────────────────────────┤
│  [搜索事件...]                    [过滤: 全部 ▼]             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ▼ 未来事件                                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 📅 2025-10-08 14:00 - 15:00                           │  │
│  │ 产品评审会议                                           │  │
│  │ 地点: 会议室 A | 参会人: 张三, 李四                    │  │
│  │ ☑ 启用实时转录  ☑ 启用会议录音                         │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 📅 2025-10-09 10:00 - 11:30                           │  │
│  │ 客户需求讨论                                           │  │
│  │ 地点: 线上 | 参会人: 王五, 赵六                        │  │
│  │ ☐ 启用实时转录  ☐ 启用会议录音                         │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ━━━━━━━━━━━━━━━━ 现在 (2025-10-07 10:00) ━━━━━━━━━━━━━━━  │
│                                                              │
│  ▲ 过去事件                                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 📅 2025-10-06 15:00 - 16:00                           │  │
│  │ 技术分享会                                             │  │
│  │ 地点: 会议室 B | 参会人: 全体技术团队                  │  │
│  │ 🎙️ 录音 | 📄 转录文本                                  │  │
│  │ [播放录音] [查看转录]                                  │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 📅 2025-10-05 10:00 - 11:00                           │  │
│  │ 周例会                                                 │  │
│  │ 地点: 会议室 A | 参会人: 项目组成员                    │  │
│  │ 🎙️ 录音 | 📄 转录文本                                  │  │
│  │ [播放录音] [查看转录]                                  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  [加载更多...]                                               │
└─────────────────────────────────────────────────────────────┘
```

## 应用生命周期管理

### 概述

应用生命周期管理确保 EchoNote 在启动、运行和关闭的各个阶段都能正确处理资源、保存状态并提供良好的用户体验。

### 首次运行设置

#### 设计目标

1. 引导新用户完成初始配置
2. 提供友好的欢迎体验
3. 智能推荐最佳设置
4. 允许跳过非必需步骤

#### 向导架构

```python
FirstRunWizard (QWizard)
├── WelcomePage          # 欢迎页面
├── LanguagePage         # 语言选择
├── ThemePage            # 主题选择
├── ModelDownloadPage    # 模型下载
└── CompletePage         # 完成页面
```

#### 向导流程

```
┌─────────────┐
│  检测首次运行  │
└──────┬──────┘
       │
       ├─ 是 ──→ ┌──────────────┐
       │         │  创建配置目录   │
       │         │  初始化数据库   │
       │         └───────┬────────┘
       │                 │
       │                 ▼
       │         ┌──────────────┐
       │         │  显示主窗口    │
       │         └───────┬────────┘
       │                 │
       │                 ▼
       │         ┌──────────────┐
       │         │  显示欢迎向导  │
       │         │  - 选择语言   │
       │         │  - 选择主题   │
       │         │  - 下载模型   │
       │         └───────┬────────┘
       │                 │
       │                 ▼
       │         ┌──────────────┐
       │         │  保存配置     │
       │         │  应用设置     │
       │         └───────┬────────┘
       │                 │
       └─ 否 ──→────────┘
                         │
                         ▼
                 ┌──────────────┐
                 │  正常启动应用  │
                 └──────────────┘
```

#### 智能模型推荐

```python
def recommend_model(system_info):
    """
    基于系统资源推荐模型

    决策因素：
    - 系统内存大小
    - GPU 可用性
    - 磁盘空间
    """
    memory_gb = system_info['memory_gb']
    has_gpu = system_info['has_gpu']

    if memory_gb < 8:
        return 'tiny'      # 快速，低资源
    elif memory_gb < 16:
        return 'base'      # 平衡
    else:
        if has_gpu:
            return 'medium'  # 高质量 + GPU 加速
        else:
            return 'small'   # 高质量，CPU 友好
```

#### 异步模型下载

```python
# 使用 QThreadPool 避免阻塞 UI
class ModelDownloadPage(QWizardPage):
    def _start_download(self):
        # 在独立线程中运行
        def run_download():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                model_manager.download_model(model_name)
            )
            loop.close()

            # 安全更新 UI
            QMetaObject.invokeMethod(
                self, "_on_download_complete",
                Qt.ConnectionType.QueuedConnection
            )

        QThreadPool.globalInstance().start(
            DownloadRunnable(run_download)
        )
```

### 应用关闭流程

#### 设计目标

1. 防止数据丢失
2. 优雅停止所有后台任务
3. 清理系统资源
4. 保存应用状态

#### 关闭流程图

```
┌─────────────┐
│  用户点击关闭  │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ 检查运行中的任务  │
└──────┬──────────┘
       │
       ├─ 有任务 ──→ ┌──────────────────┐
       │             │ 显示确认对话框     │
       │             │ "有 X 个任务运行"  │
       │             └────────┬─────────┘
       │                      │
       │                      ├─ 取消 ──→ [继续运行]
       │                      │
       │                      └─ 确认 ──→ [继续关闭]
       │
       └─ 无任务 ──→ [继续关闭]
                      │
                      ▼
              ┌──────────────┐
              │  保存窗口状态  │
              └───────┬──────┘
                      │
                      ▼
              ┌──────────────┐
              │  执行清理流程  │
              │  (见下方详情)  │
              └───────┬──────┘
                      │
                      ▼
              ┌──────────────┐
              │  应用退出     │
              └──────────────┘
```

#### 清理流程详细步骤

```python
def _cleanup(self):
    """
    清理顺序（每步独立错误处理）：

    1. 关闭 UI 组件
       - 关闭所有转录查看器窗口

    2. 停止业务逻辑管理器
       - 停止转录管理器（等待最多3秒）
       - 停止实时录制器
       - 停止资源监控器

    3. 停止调度器
       - 停止自动任务调度器
       - 停止日历同步调度器

    4. 保存数据
       - 保存应用设置
       - 保存窗口状态

    5. 关闭数据连接
       - 关闭数据库连接

    6. 清理文件系统
       - 清理临时文件（1天以上）

    7. 断开信号连接
       - 断开所有 Qt 信号

    总超时限制：10秒
    """
```

#### 任务检测机制

```python
class TranscriptionManager:
    def has_running_tasks(self) -> bool:
        """
        检查是否有运行中的任务

        实现：
        - 查询数据库中 status='processing' 的任务
        - 返回布尔值
        """
        result = self.db.execute(
            "SELECT COUNT(*) as count FROM transcription_tasks "
            "WHERE status = 'processing'"
        )
        return result[0]['count'] > 0

class MainWindow:
    def _get_running_task_count(self) -> int:
        """
        获取运行中任务的精确数量

        统计：
        - 转录任务数量（从数据库）
        - 实时录制状态（布尔值）
        """
        count = 0

        # 统计转录任务
        if transcription_manager.has_running_tasks():
            result = db.execute(
                "SELECT COUNT(*) as count FROM transcription_tasks "
                "WHERE status = 'processing'"
            )
            count += result[0]['count']

        # 检查实时录制
        if realtime_recorder.is_recording:
            count += 1

        return count
```

#### 优雅停止任务

```python
class TranscriptionManager:
    def stop_all_tasks(self):
        """
        优雅停止所有任务

        步骤：
        1. 获取所有待处理和处理中的任务
        2. 逐个取消任务
        3. 停止任务处理线程
        4. 等待线程结束（带超时）
        """
        # 获取任务列表
        pending_tasks = self.db.execute(
            "SELECT id FROM transcription_tasks "
            "WHERE status IN ('pending', 'processing')"
        )

        # 取消每个任务
        for task_row in pending_tasks:
            try:
                self.cancel_task(task_row['id'])
            except Exception as e:
                logger.error(f"Error cancelling task: {e}")

        # 停止处理线程
        self.stop_processing()
```

#### 超时控制

```python
import time

def _cleanup(self):
    cleanup_start = time.time()

    # 执行各项清理...

    # 等待转录管理器停止（最多3秒）
    wait_start = time.time()
    while (transcription_manager._running and
           time.time() - wait_start < 3.0):
        time.sleep(0.1)

    if transcription_manager._running:
        logger.warning("Transcription manager did not stop within timeout")

    # 检查总清理时长
    cleanup_duration = time.time() - cleanup_start
    if cleanup_duration > 10.0:
        logger.warning(f"Cleanup took too long: {cleanup_duration:.2f}s")
```

### 状态持久化

#### 窗口状态

```python
def save_window_state(self):
    """保存窗口状态到 QSettings"""
    self.settings.setValue('window/geometry', self.saveGeometry())
    self.settings.setValue('window/state', self.saveState())
    self.settings.setValue('window/position', self.pos())
    self.settings.setValue('window/size', self.size())
    self.settings.setValue('window/maximized', self.isMaximized())

def restore_window_state(self):
    """从 QSettings 恢复窗口状态"""
    geometry = self.settings.value('window/geometry')
    if geometry:
        self.restoreGeometry(geometry)
    # ... 恢复其他状态
```

#### 应用配置

```python
class SettingsManager:
    def save_settings(self):
        """
        保存所有应用设置

        包括：
        - UI 设置（语言、主题）
        - 转录设置（引擎、模型）
        - 实时录制设置
        - 日历设置
        - 时间线设置
        """
        self.config_manager.save()
```

### 资源管理

#### 临时文件清理

```python
class FileManager:
    def cleanup_temp_files(self, older_than_days: int = 1):
        """
        清理临时文件

        策略：
        - 只清理超过指定天数的文件
        - 保留当前会话的临时文件
        - 使用 shutil.rmtree() 递归删除
        """
        temp_dir = Path.home() / '.echonote' / 'temp'
        cutoff_time = time.time() - (older_than_days * 86400)

        for item in temp_dir.iterdir():
            if item.stat().st_mtime < cutoff_time:
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                except Exception as e:
                    logger.error(f"Error cleaning up {item}: {e}")
```

#### 数据库连接管理

```python
class DatabaseConnection:
    def close_all(self):
        """
        关闭所有数据库连接

        步骤：
        1. 提交未完成的事务
        2. 关闭所有连接
        3. 清理连接池
        """
        for conn in self._connections:
            try:
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Error closing connection: {e}")

        self._connections.clear()
```

### 国际化支持

#### 翻译键结构

```json
{
  "app": {
    "exit_confirmation_title": "确认退出",
    "exit_confirmation_message": "有任务正在进行，确定要退出吗？",
    "exit_confirmation_message_with_count": "有 {count} 个任务正在进行..."
  },
  "wizard": {
    "title": "欢迎使用 EchoNote",
    "welcome": { ... },
    "language": { ... },
    "theme": { ... },
    "model": { ... },
    "complete": { ... }
  }
}
```

#### 支持的语言

- 🇨🇳 中文（简体）- zh_CN
- 🇺🇸 English - en_US
- 🇫🇷 Français - fr_FR

### 错误处理

#### 首次运行错误

```python
try:
    FirstRunSetup.setup()
except Exception as e:
    logger.error(f"First run setup failed: {e}")
    # 使用默认配置继续
    # 显示错误提示
```

#### 关闭流程错误

```python
def _cleanup(self):
    # 每个清理步骤独立错误处理
    try:
        # 步骤 1
    except Exception as e:
        logger.error(f"Error in step 1: {e}")
        # 继续下一步

    try:
        # 步骤 2
    except Exception as e:
        logger.error(f"Error in step 2: {e}")
        # 继续下一步

    # ... 确保所有步骤都尝试执行
```

### 性能考虑

1. **非阻塞操作**

   - 模型下载使用独立线程
   - UI 更新使用 QMetaObject.invokeMethod
   - 避免在主线程执行耗时操作

2. **超时控制**

   - 关闭流程总超时：10 秒
   - 任务停止超时：3 秒
   - 防止无限等待

3. **资源优化**
   - 只清理旧临时文件
   - 分步骤清理，降低内存峰值
   - 及时释放数据库连接

### 测试要点

1. **首次运行测试**

   - 向导显示和隐藏
   - 配置保存和应用
   - 模型下载和跳过
   - 取消向导

2. **关闭流程测试**

   - 无任务关闭
   - 有任务关闭（确认/取消）
   - 超时处理
   - 资源清理验证

3. **边界情况**
   - 磁盘空间不足
   - 网络断开
   - 数据库锁定
   - 权限不足

## 错误处理策略

### 错误分类

1. **用户输入错误**：

   - 不支持的文件格式
   - 无效的配置参数
   - 处理方式：显示友好的错误提示，阻止操作

2. **系统资源错误**：

   - 磁盘空间不足
   - 内存不足
   - 音频设备不可用
   - 处理方式：显示警告，建议用户释放资源或更改设置

3. **网络错误**：

   - 无法连接到外部 API
   - 网络超时
   - 处理方式：重试机制（指数退避），提示用户检查网络

4. **外部 API 错误**：

   - API 密钥无效
   - 速率限制
   - 服务不可用
   - 处理方式：显示具体错误信息，建议解决方案

5. **数据库错误**：
   - 数据库锁定
   - 数据损坏
   - 处理方式：记录详细日志，尝试自动修复，必要时提示用户

### 错误处理流程

```python
class ErrorHandler:
    @staticmethod
    def handle_error(error: Exception, context: dict) -> dict:
        """
        统一错误处理
        返回: {
            "user_message": "用户友好的错误消息",
            "technical_details": "技术细节（用于日志）",
            "suggested_action": "建议的解决方案",
            "retry_possible": True/False
        }
        """
        if isinstance(error, UnsupportedFormatError):
            return {
                "user_message": f"不支持的文件格式: {error.format}",
                "technical_details": str(error),
                "suggested_action": "支持的格式: MP3, WAV, M4A, MP4, AVI",
                "retry_possible": False
            }
        elif isinstance(error, NetworkError):
            return {
                "user_message": "网络连接失败",
                "technical_details": str(error),
                "suggested_action": "请检查网络连接后重试",
                "retry_possible": True
            }
        # ... 其他错误类型
```

### 日志策略

```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    logger = logging.getLogger('echonote')
    logger.setLevel(logging.DEBUG)

    # 文件日志（详细）
    file_handler = RotatingFileHandler(
        '~/.echonote/logs/app.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))

    # 控制台日志（简化）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        '%(levelname)s: %(message)s'
    ))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
```

## 测试策略

### 单元测试

**测试覆盖范围**：

- 核心业务逻辑（管理器类）
- 数据模型和验证
- 工具函数
- 格式转换器

**测试框架**：pytest

**示例**：

```python
# tests/unit/test_format_converter.py
import pytest
from core.transcription.format_converter import FormatConverter

def test_convert_to_txt():
    converter = FormatConverter()
    internal_format = {
        "segments": [
            {"start": 0.0, "end": 2.5, "text": "Hello world"},
            {"start": 2.5, "end": 5.0, "text": "This is a test"}
        ]
    }

    result = converter.convert(internal_format, "txt")
    assert result == "Hello world\nThis is a test"

def test_convert_to_srt():
    converter = FormatConverter()
    internal_format = {
        "segments": [
            {"start": 0.0, "end": 2.5, "text": "Hello world"}
        ]
    }

    result = converter.convert(internal_format, "srt")
    expected = """1
00:00:00,000 --> 00:00:02,500
Hello world
"""
    assert result == expected
```

### 集成测试

**测试场景**：

- 批量转录完整流程（文件导入 → 转录 → 导出）
- 实时录制完整流程（开始录制 → 转录 → 停止 → 保存）
- 日历同步流程（OAuth 认证 → 同步事件 → 本地存储）
- 自动任务触发流程（事件到期 → 启动任务 → 保存结果）

**测试数据**：

- 使用 fixtures 提供测试音频文件
- 使用 mock 模拟外部 API 响应

### 性能测试

**测试指标**：

- 转录速度：音频时长 vs 处理时长的比率（目标：> 1.0，即实时或更快）
- 内存使用：处理大文件时的峰值内存（目标：< 500MB）
- UI 响应性：主线程不阻塞，操作响应时间 < 100ms
- 数据库查询性能：复杂查询 < 100ms

**测试工具**：

- `memory_profiler`：内存分析
- `cProfile`：性能分析
- `pytest-benchmark`：基准测试

### UI 测试

**测试方法**：

- 手动测试：关键用户流程
- 自动化测试（可选）：使用 `pytest-qt` 测试 PyQt 组件

**测试清单**：

- [ ] 侧边栏导航切换
- [ ] 批量转录：导入文件、查看进度、导出结果
- [ ] 实时录制：选择音频源、开始/停止录制、查看实时转录
- [ ] 日历：创建事件、编辑事件、删除事件、切换视图
- [ ] 时间线：滚动加载、搜索事件、查看附件
- [ ] 设置：更改配置、切换主题、切换语言

## 安全设计

### 数据加密

#### 1. 敏感配置加密

**加密方案**：

- 算法：AES-256-GCM
- 密钥派生：PBKDF2（基于机器唯一标识符）
- 存储位置：`~/.echonote/secrets.enc`

**实现**：

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import os
import uuid

class SecurityManager:
    def __init__(self):
        self.key = self._derive_key()
        self.cipher = AESGCM(self.key)

    def _derive_key(self) -> bytes:
        """基于机器 UUID 派生加密密钥"""
        machine_id = str(uuid.getnode()).encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'echonote_salt_v1',  # 固定 salt
            iterations=100000,
        )
        return kdf.derive(machine_id)

    def encrypt(self, plaintext: str) -> bytes:
        """加密字符串"""
        nonce = os.urandom(12)
        ciphertext = self.cipher.encrypt(
            nonce,
            plaintext.encode(),
            None
        )
        return nonce + ciphertext

    def decrypt(self, encrypted: bytes) -> str:
        """解密字符串"""
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]
        plaintext = self.cipher.decrypt(nonce, ciphertext, None)
        return plaintext.decode()
```

#### 2. 数据库加密

**方案**：使用 SQLCipher 扩展

```python
import sqlcipher3 as sqlite3

def create_encrypted_connection(db_path: str, key: str):
    conn = sqlite3.connect(db_path)
    conn.execute(f"PRAGMA key = '{key}'")
    conn.execute("PRAGMA cipher_page_size = 4096")
    conn.execute("PRAGMA kdf_iter = 64000")
    return conn
```

### OAuth 安全

#### 1. Google Calendar OAuth 流程

**实际实现说明**：实际实现中使用 `httpx` 而非 `authlib`，因为 httpx 更轻量且功能完全满足需求。

```python
import httpx

class GoogleCalendarAdapter:
    CLIENT_ID = "your-client-id.apps.googleusercontent.com"
    CLIENT_SECRET = "your-client-secret"
    REDIRECT_URI = "http://localhost:8080/oauth/callback"
    SCOPES = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events"
    ]

    def get_authorization_url(self) -> str:
        """生成授权 URL"""
        params = {
            'client_id': self.CLIENT_ID,
            'redirect_uri': self.REDIRECT_URI,
            'response_type': 'code',
            'scope': ' '.join(self.SCOPES),
            'access_type': 'offline',
            'prompt': 'consent'
        }
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query_string}"

    def exchange_code_for_token(self, code: str) -> dict:
        """交换授权码为 token"""
        with httpx.Client() as client:
            response = client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    'code': code,
                    'client_id': self.CLIENT_ID,
                    'client_secret': self.CLIENT_SECRET,
                    'redirect_uri': self.REDIRECT_URI,
                    'grant_type': 'authorization_code'
                }
            )
            response.raise_for_status()
            return response.json()
```

#### 2. Token 刷新机制

**实际实现说明**：实际实现为同步方法，使用 httpx 的同步客户端。

```python
class OAuthManager:
    def refresh_token_if_needed(self, provider: str) -> dict:
        """检查 token 是否过期，如需要则刷新"""
        token_data = self.get_stored_token(provider)

        if datetime.now() >= token_data['expires_at']:
            # Token 已过期，刷新
            adapter = self.get_adapter(provider)
            new_token = adapter.refresh_access_token()
            self.store_token(provider, new_token)
            return new_token

        return token_data
```

### HTTPS 通信

**要求**：

- 所有外部 API 调用必须使用 HTTPS
- 验证 SSL 证书
- 使用 `httpx` 客户端，默认启用证书验证

**实际实现说明**：实际实现使用同步 httpx.Client，适合当前架构。

```python
import httpx

def make_api_request(url: str, headers: dict, data: dict):
    with httpx.Client(verify=True) as client:
        response = client.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
```

### 文件权限

**要求**：

- 配置文件：仅当前用户可读写（0600）
- 数据库文件：仅当前用户可读写（0600）
- 录音文件：用户可配置，默认仅当前用户可读写（0600）

```python
import os
import stat

def create_secure_file(file_path: str):
    """创建具有安全权限的文件"""
    with open(file_path, 'w') as f:
        pass
    os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
```

## 国际化（i18n）设计

### 翻译文件结构

**格式**：JSON

**位置**：`resources/translations/`

**示例（zh_CN.json）**：

```json
{
  "app": {
    "name": "EchoNote",
    "version": "1.0.0"
  },
  "sidebar": {
    "batch_transcribe": "批量转录",
    "realtime_record": "实时录制",
    "calendar_hub": "日历中心",
    "timeline": "时间线",
    "settings": "设置"
  },
  "batch_transcribe": {
    "title": "批量转录",
    "import_files": "导入文件",
    "import_folder": "导入文件夹",
    "clear_queue": "清空队列",
    "task_queue": "任务队列",
    "status": {
      "pending": "待处理",
      "processing": "处理中",
      "completed": "已完成",
      "failed": "失败"
    }
  },
  "errors": {
    "unsupported_format": "不支持的文件格式: {format}",
    "network_error": "网络连接失败",
    "api_key_invalid": "API 密钥无效"
  }
}
```

### i18n 管理器

```python
import json
from typing import Dict

class I18nManager:
    def __init__(self, language: str = 'zh_CN'):
        self.language = language
        self.translations = self._load_translations(language)

    def _load_translations(self, language: str) -> Dict:
        """加载翻译文件"""
        file_path = f'resources/translations/{language}.json'
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def t(self, key: str, **kwargs) -> str:
        """
        获取翻译文本
        支持嵌套键：'batch_transcribe.title'
        支持参数替换：t('errors.unsupported_format', format='MP4')
        """
        keys = key.split('.')
        value = self.translations

        for k in keys:
            value = value.get(k)
            if value is None:
                return key  # 如果找不到翻译，返回键本身

        if isinstance(value, str) and kwargs:
            return value.format(**kwargs)

        return value

    def change_language(self, language: str):
        """切换语言"""
        self.language = language
        self.translations = self._load_translations(language)
```

### PyQt 集成

```python
from PyQt6.QtCore import QObject, pyqtSignal

class I18nQtManager(QObject):
    language_changed = pyqtSignal(str)

    def __init__(self, language: str = 'zh_CN'):
        super().__init__()
        self.i18n = I18nManager(language)

    def t(self, key: str, **kwargs) -> str:
        return self.i18n.t(key, **kwargs)

    def change_language(self, language: str):
        self.i18n.change_language(language)
        self.language_changed.emit(language)

# 在 UI 组件中使用
class BatchTranscribeWidget(QWidget):
    def __init__(self, i18n: I18nQtManager):
        super().__init__()
        self.i18n = i18n
        self.i18n.language_changed.connect(self.update_ui_text)
        self.setup_ui()

    def setup_ui(self):
        self.title_label = QLabel(self.i18n.t('batch_transcribe.title'))
        self.import_button = QPushButton(self.i18n.t('batch_transcribe.import_files'))

    def update_ui_text(self):
        """语言切换时更新 UI 文本"""
        self.title_label.setText(self.i18n.t('batch_transcribe.title'))
        self.import_button.setText(self.i18n.t('batch_transcribe.import_files'))
```

## 打包与分发

### Windows 打包（PyInstaller）

**配置文件（echonote.spec）**：

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('resources', 'resources'),
        ('config', 'config'),
    ],
    hiddenimports=[
        'PyQt6',
        'faster_whisper',
        'httpx',
        'authlib',
        'cryptography',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='EchoNote',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icons/app_icon.ico'
)
```

**打包命令**：

```bash
# 安装 PyInstaller
pip install pyinstaller

# 打包
pyinstaller echonote.spec

# 输出: dist/EchoNote.exe
```

**代码签名（Windows）**：

```bash
# 使用 signtool（需要代码签名证书）
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com dist/EchoNote.exe
```

### macOS 打包（py2app）

**配置文件（setup.py）**：

```python
from setuptools import setup

APP = ['main.py']
DATA_FILES = [
    ('resources', ['resources']),
    ('config', ['config']),
]
OPTIONS = {
    'argv_emulation': True,
    'packages': [
        'PyQt6',
        'faster_whisper',
        'httpx',
        'authlib',
        'cryptography',
    ],
    'iconfile': 'resources/icons/app_icon.icns',
    'plist': {
        'CFBundleName': 'EchoNote',
        'CFBundleDisplayName': 'EchoNote',
        'CFBundleIdentifier': 'com.echonote.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSMicrophoneUsageDescription': 'EchoNote needs access to your microphone for real-time transcription.',
        'NSCalendarsUsageDescription': 'EchoNote needs access to your calendar for event management.',
    }
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
```

**打包命令**：

```bash
# 安装 py2app
pip install py2app

# 打包
python setup.py py2app

# 输出: dist/EchoNote.app
```

**代码签名（macOS）**：

```bash
# 使用 codesign（需要 Apple Developer 证书）
codesign --deep --force --verify --verbose --sign "Developer ID Application: Your Name" dist/EchoNote.app

# 公证（Notarization）
xcrun notarytool submit dist/EchoNote.app --apple-id your@email.com --password app-specific-password --wait

# 装订公证票据
xcrun stapler staple dist/EchoNote.app
```

### 依赖管理

**requirements.txt**：

```
PyQt6==6.6.0
faster-whisper==0.10.0
httpx==0.25.0
authlib==1.2.1
cryptography==41.0.5
sqlcipher3==0.5.1
PyAudio==0.2.13
soundfile==0.12.1
librosa==0.10.1
numpy==1.24.3
apscheduler==3.10.4
```

**开发依赖（requirements-dev.txt）**：

```
pytest==7.4.3
pytest-qt==4.2.0
pytest-asyncio==0.21.1
pytest-benchmark==4.0.0
memory-profiler==0.61.0
black==23.11.0
flake8==6.1.0
mypy==1.7.0
```

### 首次运行初始化

```python
import os
from pathlib import Path

class FirstRunSetup:
    @staticmethod
    def is_first_run() -> bool:
        """检查是否首次运行"""
        config_dir = Path.home() / '.echonote'
        return not config_dir.exists()

    @staticmethod
    def setup():
        """首次运行初始化"""
        config_dir = Path.home() / '.echonote'
        config_dir.mkdir(exist_ok=True)

        # 创建子目录
        (config_dir / 'logs').mkdir(exist_ok=True)
        (config_dir / 'models').mkdir(exist_ok=True)

        # 创建默认配置文件
        default_config = Path('config/app_config.json')
        user_config = config_dir / 'app_config.json'
        if not user_config.exists():
            import shutil
            shutil.copy(default_config, user_config)

        # 初始化数据库
        from data.database.connection import DatabaseConnection
        db = DatabaseConnection(str(config_dir / 'data.db'))
        db.initialize_schema()

        # 下载默认 Whisper 模型（如果未包含在安装包中）
        from engines.speech.faster_whisper_engine import FasterWhisperEngine
        FasterWhisperEngine.download_model('base')
```

## 性能优化

### 1. 异步处理

**原则**：

- UI 线程仅处理界面更新，不执行耗时操作
- 所有 I/O 操作（文件读写、网络请求、数据库查询）使用异步
- 使用 `asyncio` 和 `QThread` 结合

**实现模式**：

```python
from PyQt6.QtCore import QThread, pyqtSignal
import asyncio

class AsyncWorker(QThread):
    """异步工作线程"""
    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(Exception)

    def __init__(self, coro):
        super().__init__()
        self.coro = coro

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.coro)
            self.result_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(e)
        finally:
            loop.close()

# 在 UI 中使用
class BatchTranscribeWidget(QWidget):
    def start_transcription(self, file_path: str):
        worker = AsyncWorker(
            self.transcription_manager.process_task(file_path)
        )
        worker.result_ready.connect(self.on_transcription_complete)
        worker.error_occurred.connect(self.on_error)
        worker.start()
```

### 2. 内存优化

**策略**：

- 流式处理大文件，避免一次性加载到内存
- 使用生成器处理大量数据
- 及时释放不再使用的资源

**示例**：

```python
def process_large_audio_file(file_path: str, chunk_size: int = 30):
    """流式处理大音频文件"""
    import soundfile as sf

    with sf.SoundFile(file_path) as audio:
        sample_rate = audio.samplerate
        total_frames = len(audio)
        chunk_frames = chunk_size * sample_rate

        for start in range(0, total_frames, chunk_frames):
            audio.seek(start)
            chunk = audio.read(chunk_frames)
            yield chunk

            # 处理完一个块后，Python 会自动回收内存
```

### 3. 数据库优化

**索引策略**：

- 为常用查询字段创建索引
- 使用复合索引优化多条件查询

**查询优化**：

```python
# 使用参数化查询，避免 SQL 注入，同时利用查询缓存
cursor.execute(
    "SELECT * FROM calendar_events WHERE start_time >= ? AND end_time <= ?",
    (start_date, end_date)
)

# 批量插入
cursor.executemany(
    "INSERT INTO calendar_events (id, title, start_time, end_time) VALUES (?, ?, ?, ?)",
    events_data
)
```

**连接池**：

```python
class DatabaseConnectionPool:
    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool = queue.Queue(maxsize=pool_size)
        for _ in range(pool_size):
            self.pool.put(self._create_connection())

    def get_connection(self):
        return self.pool.get()

    def return_connection(self, conn):
        self.pool.put(conn)
```

### 4. UI 优化

**虚拟滚动**：

```python
from PyQt6.QtWidgets import QListView
from PyQt6.QtCore import QAbstractListModel

class TimelineModel(QAbstractListModel):
    """时间线数据模型，支持虚拟滚动"""
    def __init__(self, timeline_manager):
        super().__init__()
        self.timeline_manager = timeline_manager
        self.page_size = 50
        self.loaded_events = []

    def rowCount(self, parent=None):
        return len(self.loaded_events)

    def data(self, index, role):
        if role == Qt.DisplayRole:
            return self.loaded_events[index.row()]

    def canFetchMore(self, parent):
        """是否可以加载更多数据"""
        return True  # 根据实际情况判断

    def fetchMore(self, parent):
        """加载更多数据"""
        page = len(self.loaded_events) // self.page_size
        new_events = self.timeline_manager.get_timeline_events(
            page=page,
            page_size=self.page_size
        )

        self.beginInsertRows(
            parent,
            len(self.loaded_events),
            len(self.loaded_events) + len(new_events) - 1
        )
        self.loaded_events.extend(new_events)
        self.endInsertRows()
```

**延迟加载**：

```python
class EventCard(QWidget):
    """事件卡片，延迟加载附件信息"""
    def __init__(self, event: CalendarEvent):
        super().__init__()
        self.event = event
        self.attachments_loaded = False
        self.setup_ui()

    def showEvent(self, event):
        """卡片显示时才加载附件"""
        if not self.attachments_loaded:
            self.load_attachments()
            self.attachments_loaded = True
```

### 5. 缓存策略

**LRU 缓存**：

```python
from functools import lru_cache

class CalendarManager:
    @lru_cache(maxsize=128)
    def get_event(self, event_id: str) -> CalendarEvent:
        """缓存事件查询结果"""
        return self.db.query_event(event_id)
```

**文件缓存**：

```python
class CacheManager:
    def __init__(self, cache_dir: str, max_size_mb: int = 500):
        self.cache_dir = Path(cache_dir)
        self.max_size = max_size_mb * 1024 * 1024

    def cache_file(self, key: str, data: bytes):
        """缓存文件"""
        cache_path = self.cache_dir / key
        cache_path.write_bytes(data)
        self._cleanup_if_needed()

    def get_cached_file(self, key: str) -> bytes:
        """获取缓存文件"""
        cache_path = self.cache_dir / key
        if cache_path.exists():
            return cache_path.read_bytes()
        return None

    def _cleanup_if_needed(self):
        """清理超出大小限制的缓存"""
        total_size = sum(f.stat().st_size for f in self.cache_dir.iterdir())
        if total_size > self.max_size:
            # 删除最旧的文件
            files = sorted(
                self.cache_dir.iterdir(),
                key=lambda f: f.stat().st_mtime
            )
            for f in files:
                f.unlink()
                total_size -= f.stat().st_size
                if total_size <= self.max_size * 0.8:
                    break
```

## 部署与维护

### 自动更新机制

**检查更新**：

```python
import httpx

class UpdateChecker:
    UPDATE_URL = "https://api.echonote.com/version"

    async def check_for_updates(self, current_version: str) -> dict:
        """检查是否有新版本"""
        async with httpx.AsyncClient() as client:
            response = await client.get(self.UPDATE_URL)
            data = response.json()

            latest_version = data['version']
            if self._is_newer_version(latest_version, current_version):
                return {
                    'update_available': True,
                    'version': latest_version,
                    'download_url': data['download_url'],
                    'release_notes': data['release_notes']
                }

            return {'update_available': False}

    def _is_newer_version(self, latest: str, current: str) -> bool:
        """比较版本号"""
        latest_parts = [int(x) for x in latest.split('.')]
        current_parts = [int(x) for x in current.split('.')]
        return latest_parts > current_parts
```

### 崩溃报告

**异常捕获**：

```python
import sys
import traceback

def exception_hook(exctype, value, tb):
    """全局异常处理"""
    error_msg = ''.join(traceback.format_exception(exctype, value, tb))

    # 记录到日志
    logger.critical(f"Unhandled exception: {error_msg}")

    # 显示错误对话框
    from PyQt6.QtWidgets import QMessageBox
    QMessageBox.critical(
        None,
        "应用程序错误",
        f"应用程序遇到了一个错误:\n\n{value}\n\n详细信息已记录到日志文件。"
    )

    # 可选：发送崩溃报告到服务器
    # send_crash_report(error_msg)

sys.excepthook = exception_hook
```

### 日志轮转

**配置**：

```python
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

# 按大小轮转
file_handler = RotatingFileHandler(
    '~/.echonote/logs/app.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)

# 按时间轮转
time_handler = TimedRotatingFileHandler(
    '~/.echonote/logs/app.log',
    when='midnight',
    interval=1,
    backupCount=30
)
```

## 总结

本设计文档详细描述了 EchoNote 应用的技术架构、核心组件、数据模型、安全策略、性能优化和部署方案。设计遵循以下核心原则：

1. **模块化**：清晰的分层架构，各层职责明确
2. **可扩展**：可插拔的引擎系统，易于添加新功能
3. **本地优先**：核心功能离线可用，云服务作为可选增强
4. **安全第一**：敏感数据加密存储，安全的外部 API 通信
5. **性能优先**：异步处理、流式数据、资源限制
6. **用户友好**：清晰的错误提示、多语言支持、现代化 UI

下一步将基于此设计创建详细的实现任务列表。
