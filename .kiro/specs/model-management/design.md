# 模型管理功能设计文档

## 概述

模型管理功能为 EchoNote 提供完整的本地 Whisper 模型生命周期管理能力。该功能深度集成到现有架构中，遵循项目的模块化、DRY 和可维护性原则。

### 设计原则

1. **最小侵入性**：在现有代码基础上扩展，避免大规模重构
2. **统一管理**：所有模型相关操作集中在模型管理器中
3. **响应式更新**：使用 Qt Signal 机制实现模型列表的实时同步
4. **异步处理**：模型下载等耗时操作使用异步机制，不阻塞 UI
5. **错误恢复**：完善的错误处理和自动恢复机制

### 技术栈

- **模型下载**：`huggingface_hub` 库（官方推荐）
- **异步处理**：`asyncio` + `QThread`
- **进度通知**：Qt Signal/Slot 机制
- **文件操作**：`pathlib`、`shutil`
- **模型验证**：`faster-whisper` 的模型加载机制

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                         UI Layer                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Model Management Page (Settings)                    │  │
│  │  - Model List View                                   │  │
│  │  - Download Progress                                 │  │
│  │  - Model Details Dialog                              │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Qt Signals
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      Core Layer                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ModelManager                                        │  │
│  │  - Model Registry                                    │  │
│  │  - Download Queue                                    │  │
│  │  - Model Validation                                  │  │
│  │  - Usage Statistics                                  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Engine Layer                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  FasterWhisperEngine (Modified)                      │  │
│  │  - Dynamic Model Loading                             │  │
│  │  - Model Registry Integration                        │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 目录结构

```
echonote/
├── core/
│   └── models/
│       ├── __init__.py
│       ├── manager.py              # 模型管理器
│       ├── downloader.py           # 模型下载器
│       ├── registry.py             # 模型注册表
│       └── validator.py            # 模型验证器
├── ui/
│   └── settings/
│       └── model_management_page.py  # 模型管理界面
└── data/
    └── database/
        └── models.py               # 添加 ModelUsageStats 模型
```

## 核心组件设计

### 1. 模型注册表（ModelRegistry）

**职责**：

- 维护所有支持的模型元数据
- 跟踪已下载模型的状态
- 提供模型查询接口

**数据结构**：

```python
@dataclass
class ModelInfo:
    """模型元数据"""
    name: str                    # 模型名称，如 "base"
    full_name: str              # 完整名称，如 "Whisper Base Multilingual"
    size_mb: int                # 模型大小（MB）
    speed: str                  # 速度特征：fast/medium/slow
    accuracy: str               # 准确度：low/medium/high
    languages: List[str]        # 支持的语言，["multi"] 表示多语言
    huggingface_id: str         # Hugging Face 模型 ID
    is_downloaded: bool = False # 是否已下载
    local_path: Optional[str] = None  # 本地路径
    download_date: Optional[datetime] = None  # 下载日期
    last_used: Optional[datetime] = None  # 最后使用时间
    usage_count: int = 0        # 使用次数
```

**实现**：

```python
class ModelRegistry:
    """模型注册表，管理所有模型的元数据和状态"""

    # 支持的模型定义
    SUPPORTED_MODELS = {
        "tiny": ModelInfo(
            name="tiny",
            full_name="Whisper Tiny Multilingual",
            size_mb=75,
            speed="fastest",
            accuracy="low",
            languages=["multi"],
            huggingface_id="guillaumekln/faster-whisper-tiny"
        ),
        "tiny.en": ModelInfo(
            name="tiny.en",
            full_name="Whisper Tiny English",
            size_mb=75,
            speed="fastest",
            accuracy="low",
            languages=["en"],
            huggingface_id="guillaumekln/faster-whisper-tiny.en"
        ),
        "base": ModelInfo(
            name="base",
            full_name="Whisper Base Multilingual",
            size_mb=142,
            speed="fast",
            accuracy="medium",
            languages=["multi"],
            huggingface_id="guillaumekln/faster-whisper-base"
        ),
        # ... 其他模型定义
    }

    def __init__(self, model_dir: Path):
        self.model_dir = model_dir
        self._models: Dict[str, ModelInfo] = {}
        self._load_models()

    def _load_models(self):
        """加载模型元数据并扫描本地模型"""
        # 复制支持的模型定义
        self._models = {k: copy.deepcopy(v) for k, v in self.SUPPORTED_MODELS.items()}

        # 扫描本地模型目录
        self._scan_local_models()

    def _scan_local_models(self):
        """扫描本地模型目录，更新模型状态"""
        for model_name, model_info in self._models.items():
            model_path = self.model_dir / model_name
            if model_path.exists():
                model_info.is_downloaded = True
                model_info.local_path = str(model_path)
                # 读取下载日期（从文件元数据）
                model_info.download_date = datetime.fromtimestamp(
                    model_path.stat().st_mtime
                )

    def get_model(self, name: str) -> Optional[ModelInfo]:
        """获取模型信息"""
        return self._models.get(name)

    def get_all_models(self) -> List[ModelInfo]:
        """获取所有模型信息"""
        return list(self._models.values())

    def get_downloaded_models(self) -> List[ModelInfo]:
        """获取已下载的模型"""
        return [m for m in self._models.values() if m.is_downloaded]

    def update_model_status(self, name: str, **kwargs):
        """更新模型状态"""
        if name in self._models:
            for key, value in kwargs.items():
                setattr(self._models[name], key, value)

    def mark_model_used(self, name: str):
        """标记模型被使用"""
        if name in self._models:
            self._models[name].last_used = datetime.now()
            self._models[name].usage_count += 1
```

### 2. 模型下载器（ModelDownloader）

**职责**：

- 从 Hugging Face 下载模型
- 提供下载进度通知
- 支持下载取消和断点续传
- 验证下载的模型完整性

**实现**：

```python
class ModelDownloader(QObject):
    """模型下载器，使用 huggingface_hub 下载模型"""

    # Qt Signals
    download_started = pyqtSignal(str)  # model_name
    download_progress = pyqtSignal(str, int, float)  # model_name, progress%, speed_mbps
    download_completed = pyqtSignal(str)  # model_name
    download_failed = pyqtSignal(str, str)  # model_name, error_message
    download_cancelled = pyqtSignal(str)  # model_name

    def __init__(self, model_dir: Path, registry: ModelRegistry):
        super().__init__()
        self.model_dir = model_dir
        self.registry = registry
        self._download_queue: asyncio.Queue = asyncio.Queue()
        self._active_downloads: Dict[str, bool] = {}  # model_name -> is_active
        self._cancel_flags: Dict[str, bool] = {}  # model_name -> should_cancel

    async def download_model(self, model_name: str):
        """下载指定模型"""
        model_info = self.registry.get_model(model_name)
        if not model_info:
            self.download_failed.emit(model_name, "Unknown model")
            return

        if model_info.is_downloaded:
            logger.info(f"Model {model_name} already downloaded")
            return

        # 检查磁盘空间
        if not self._check_disk_space(model_info.size_mb):
            self.download_failed.emit(
                model_name,
                f"Insufficient disk space. Need at least {model_info.size_mb}MB"
            )
            return

        # 标记为活动下载
        self._active_downloads[model_name] = True
        self._cancel_flags[model_name] = False

        self.download_started.emit(model_name)

        try:
            # 使用 huggingface_hub 下载
            from huggingface_hub import snapshot_download

            target_dir = self.model_dir / model_name
            target_dir.mkdir(parents=True, exist_ok=True)

            # 下载模型（带进度回调）
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: snapshot_download(
                    repo_id=model_info.huggingface_id,
                    local_dir=str(target_dir),
                    local_dir_use_symlinks=False,
                    resume_download=True,
                    # 进度回调
                    tqdm_class=self._create_progress_callback(model_name)
                )
            )

            # 检查是否被取消
            if self._cancel_flags.get(model_name, False):
                # 删除部分下载的文件
                shutil.rmtree(target_dir, ignore_errors=True)
                self.download_cancelled.emit(model_name)
                return

            # 验证模型
            if not self._validate_model(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
                self.download_failed.emit(model_name, "Model validation failed")
                return

            # 更新注册表
            self.registry.update_model_status(
                model_name,
                is_downloaded=True,
                local_path=str(target_dir),
                download_date=datetime.now()
            )

            self.download_completed.emit(model_name)
            logger.info(f"Model {model_name} downloaded successfully")

        except Exception as e:
            logger.error(f"Error downloading model {model_name}: {e}")
            self.download_failed.emit(model_name, str(e))

        finally:
            self._active_downloads.pop(model_name, None)
            self._cancel_flags.pop(model_name, None)

    def cancel_download(self, model_name: str):
        """取消下载"""
        if model_name in self._active_downloads:
            self._cancel_flags[model_name] = True
            logger.info(f"Cancelling download for model: {model_name}")

    def _check_disk_space(self, required_mb: int) -> bool:
        """检查磁盘空间是否足够"""
        import shutil
        stat = shutil.disk_usage(self.model_dir)
        available_mb = stat.free / (1024 * 1024)
        # 需要额外 20% 的空间作为缓冲
        return available_mb >= required_mb * 1.2

    def _create_progress_callback(self, model_name: str):
        """创建进度回调类"""
        downloader = self

        class ProgressCallback:
            def __init__(self, *args, **kwargs):
                self.last_update = time.time()
                self.last_bytes = 0

            def update(self, n=1):
                # 每秒更新一次进度
                now = time.time()
                if now - self.last_update >= 1.0:
                    # 计算下载速度
                    bytes_diff = n - self.last_bytes
                    time_diff = now - self.last_update
                    speed_mbps = (bytes_diff / time_diff) / (1024 * 1024)

                    # 发送进度信号
                    progress = int((n / self.total) * 100) if hasattr(self, 'total') else 0
                    downloader.download_progress.emit(model_name, progress, speed_mbps)

                    self.last_update = now
                    self.last_bytes = n

        return ProgressCallback

    def _validate_model(self, model_path: Path) -> bool:
        """验证模型完整性"""
        try:
            # 尝试加载模型
            from faster_whisper import WhisperModel
            model = WhisperModel(str(model_path), device="cpu", compute_type="int8")
            # 如果能成功加载，说明模型完整
            return True
        except Exception as e:
            logger.error(f"Model validation failed: {e}")
            return False
```

### 3. 模型管理器（ModelManager）

**职责**：

- 统一管理模型的生命周期
- 协调下载器和注册表
- 提供模型删除功能
- 管理模型使用统计
- 通知 UI 和其他组件模型状态变化

**实现**：

```python
class ModelManager(QObject):
    """模型管理器，统一管理模型的生命周期"""

    # Qt Signals
    models_updated = pyqtSignal()  # 模型列表更新
    model_downloaded = pyqtSignal(str)  # model_name
    model_deleted = pyqtSignal(str)  # model_name

    def __init__(self, config_manager, db_connection):
        super().__init__()
        self.config = config_manager
        self.db = db_connection

        # 模型目录
        model_dir_str = self.config.get("transcription.faster_whisper.model_dir")
        if not model_dir_str:
            model_dir_str = str(Path.home() / ".echonote" / "models")
        self.model_dir = Path(model_dir_str)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # 初始化组件
        self.registry = ModelRegistry(self.model_dir)
        self.downloader = ModelDownloader(self.model_dir, self.registry)
        self.validator = ModelValidator(self.registry)

        # 连接下载器信号
        self.downloader.download_completed.connect(self._on_download_completed)

        # 启动时验证所有模型
        self.validator.validate_all_models()

        logger.info("ModelManager initialized")

    def get_all_models(self) -> List[ModelInfo]:
        """获取所有模型信息"""
        return self.registry.get_all_models()

    def get_downloaded_models(self) -> List[ModelInfo]:
        """获取已下载的模型"""
        return self.registry.get_downloaded_models()

    def get_model(self, name: str) -> Optional[ModelInfo]:
        """获取指定模型信息"""
        return self.registry.get_model(name)

    async def download_model(self, model_name: str):
        """下载模型"""
        await self.downloader.download_model(model_name)

    def cancel_download(self, model_name: str):
        """取消下载"""
        self.downloader.cancel_download(model_name)

    def delete_model(self, model_name: str) -> bool:
        """删除模型"""
        model_info = self.registry.get_model(model_name)
        if not model_info or not model_info.is_downloaded:
            logger.warning(f"Model {model_name} not found or not downloaded")
            return False

        try:
            # 删除模型文件
            model_path = Path(model_info.local_path)
            if model_path.exists():
                shutil.rmtree(model_path)

            # 更新注册表
            self.registry.update_model_status(
                model_name,
                is_downloaded=False,
                local_path=None,
                download_date=None
            )

            # 发送信号
            self.model_deleted.emit(model_name)
            self.models_updated.emit()

            logger.info(f"Model {model_name} deleted successfully")
            return True

        except Exception as e:
            logger.error(f"Error deleting model {model_name}: {e}")
            return False

    def mark_model_used(self, model_name: str):
        """标记模型被使用"""
        self.registry.mark_model_used(model_name)
        # 保存使用统计到数据库
        self._save_usage_stats(model_name)

    def get_model_usage_stats(self, model_name: str) -> Dict[str, Any]:
        """获取模型使用统计"""
        model_info = self.registry.get_model(model_name)
        if not model_info:
            return {}

        return {
            "usage_count": model_info.usage_count,
            "last_used": model_info.last_used,
            "download_date": model_info.download_date
        }

    def recommend_model(self) -> str:
        """根据设备性能推荐模型"""
        import psutil

        # 获取系统内存
        memory_gb = psutil.virtual_memory().total / (1024 ** 3)

        # 检查是否有 GPU
        has_gpu = self._check_gpu_available()

        # 推荐逻辑
        if memory_gb < 8:
            return "tiny" if not has_gpu else "base"
        elif memory_gb < 16:
            return "small" if not has_gpu else "medium"
        else:
            return "medium" if not has_gpu else "large-v3"

    def _check_gpu_available(self) -> bool:
        """检查是否有可用的 GPU"""
        try:
            import torch
            return torch.cuda.is_available()
        except:
            return False

    def _on_download_completed(self, model_name: str):
        """处理下载完成事件"""
        self.model_downloaded.emit(model_name)
        self.models_updated.emit()

    def _save_usage_stats(self, model_name: str):
        """保存使用统计到数据库"""
        # 实现数据库保存逻辑
        pass
```

### 4. 模型验证器（ModelValidator）

**职责**：

- 验证已下载模型的完整性
- 检测损坏的模型
- 提供修复建议

**实现**：

```python
class ModelValidator:
    """模型验证器，验证模型完整性"""

    def __init__(self, registry: ModelRegistry):
        self.registry = registry

    def validate_all_models(self) -> Dict[str, bool]:
        """验证所有已下载的模型"""
        results = {}
        for model in self.registry.get_downloaded_models():
            results[model.name] = self.validate_model(model.name)
        return results

    def validate_model(self, model_name: str) -> bool:
        """验证单个模型"""
        model_info = self.registry.get_model(model_name)
        if not model_info or not model_info.is_downloaded:
            return False

        model_path = Path(model_info.local_path)

        # 检查文件是否存在
        if not model_path.exists():
            logger.warning(f"Model path does not exist: {model_path}")
            return False

        # 检查文件大小（粗略验证）
        actual_size_mb = sum(
            f.stat().st_size for f in model_path.rglob('*') if f.is_file()
        ) / (1024 * 1024)

        expected_size_mb = model_info.size_mb
        # 允许 10% 的误差
        if not (expected_size_mb * 0.9 <= actual_size_mb <= expected_size_mb * 1.1):
            logger.warning(
                f"Model size mismatch: expected ~{expected_size_mb}MB, "
                f"got {actual_size_mb:.1f}MB"
            )
            return False

        # 尝试加载模型（最可靠的验证方式）
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel(str(model_path), device="cpu", compute_type="int8")
            return True
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            return False
```

## UI 设计

### 模型管理页面（ModelManagementPage）

**布局**：

```
┌─────────────────────────────────────────────────────────────┐
│  模型管理                                                     │
├─────────────────────────────────────────────────────────────┤
│  [推荐模型卡片]（如果没有任何模型下载）                        │
│  根据您的设备配置，推荐使用 base 模型                         │
│  [一键下载]                                                  │
├─────────────────────────────────────────────────────────────┤
│  已下载模型 (2)                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ ✓ base                                    [配置] [删除]│  │
│  │   142 MB | 速度: 快 | 准确度: 中                       │  │
│  │   使用次数: 15 | 最后使用: 2小时前                     │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │ ✓ small                                   [配置] [删除]│  │
│  │   466 MB | 速度: 中 | 准确度: 高                       │  │
│  │   使用次数: 3 | 最后使用: 1天前                        │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  可下载模型                                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ tiny                                          [下载]   │  │
│  │   75 MB | 速度: 最快 | 准确度: 低                      │  │
│  │   支持多语言                                           │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │ medium                                        [下载]   │  │
│  │   1.5 GB | 速度: 慢 | 准确度: 高                       │  │
│  │   支持多语言                                           │  │
│  │   [████████░░░░░░░░░░░░] 45% (2.5 MB/s, 剩余 30秒)    │  │
│  │   [取消下载]                                           │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**实现**：

```python
class ModelManagementPage(BaseSettingsPage):
    """模型管理页面"""

    def __init__(self, settings_manager, i18n, model_manager):
        super().__init__(settings_manager, i18n)
        self.model_manager = model_manager

        # 连接信号
        self.model_manager.models_updated.connect(self._refresh_model_list)
        self.model_manager.downloader.download_progress.connect(
            self._update_download_progress
        )

        self.setup_ui()

    def setup_ui(self):
        """设置 UI"""
        # 推荐模型卡片（如果需要）
        self._create_recommendation_card()

        # 已下载模型列表
        self.add_section_title("已下载模型")
        self.downloaded_models_layout = QVBoxLayout()
        self.content_layout.addLayout(self.downloaded_models_layout)

        # 可下载模型列表
        self.add_section_title("可下载模型")
        self.available_models_layout = QVBoxLayout()
        self.content_layout.addLayout(self.available_models_layout)

        # 刷新模型列表
        self._refresh_model_list()

    def _create_recommendation_card(self):
        """创建推荐模型卡片"""
        downloaded_models = self.model_manager.get_downloaded_models()
        if downloaded_models:
            return  # 已有模型，不显示推荐

        recommended = self.model_manager.recommend_model()
        # 创建推荐卡片 UI
        # ...

    def _refresh_model_list(self):
        """刷新模型列表"""
        # 清空现有列表
        self._clear_layout(self.downloaded_models_layout)
        self._clear_layout(self.available_models_layout)

        # 获取所有模型
        all_models = self.model_manager.get_all_models()

        for model in all_models:
            if model.is_downloaded:
                self._add_downloaded_model_card(model)
            else:
                self._add_available_model_card(model)

    def _add_downloaded_model_card(self, model: ModelInfo):
        """添加已下载模型卡片"""
        # 创建模型卡片 UI
        # ...

    def _add_available_model_card(self, model: ModelInfo):
        """添加可下载模型卡片"""
        # 创建模型卡片 UI
        # ...
```

## 集成设计

### 1. 与 FasterWhisperEngine 集成

**修改点**：

```python
class FasterWhisperEngine(SpeechEngine):
    def __init__(self, model_size='base', device='cpu', compute_type='int8',
                 model_manager=None):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model_manager = model_manager  # 新增

        # 如果提供了 model_manager，使用其管理的模型路径
        if self.model_manager:
            model_info = self.model_manager.get_model(model_size)
            if model_info and model_info.is_downloaded:
                self.download_root = str(Path(model_info.local_path).parent)
                # 标记模型被使用
                self.model_manager.mark_model_used(model_size)
            else:
                raise ValueError(
                    f"Model {model_size} is not downloaded. "
                    f"Please download it first."
                )
        else:
            # 向后兼容：使用默认路径
            self.download_root = os.path.expanduser('~/.echonote/models')

        self.model = None
        # ...
```

### 2. 与批量转录界面集成

**修改点**：

```python
class BatchTranscribeWidget(QWidget):
    def __init__(self, ..., model_manager):
        # ...
        self.model_manager = model_manager

        # 连接模型更新信号
        self.model_manager.models_updated.connect(self._update_model_list)

    def _create_engine_selector(self):
        """创建引擎选择器"""
        # ...
        self.model_combo = QComboBox()
        self._update_model_list()
        # ...

    def _update_model_list(self):
        """更新模型列表"""
        current_model = self.model_combo.currentText()
        self.model_combo.clear()

        # 获取已下载的模型
        downloaded_models = self.model_manager.get_downloaded_models()

        if not downloaded_models:
            self.model_combo.addItem("请先下载模型")
            self.model_combo.setEnabled(False)
            # 显示引导按钮
            self._show_download_guide()
        else:
            self.model_combo.setEnabled(True)
            for model in downloaded_models:
                self.model_combo.addItem(model.name)

            # 恢复之前的选择
            index = self.model_combo.findText(current_model)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
```

### 3. 与实时录制界面集成

**修改点**：类似批量转录界面，更新模型选择列表。

### 4. 与设置界面集成

**修改点**：

```python
class TranscriptionSettingsPage(BaseSettingsPage):
    def __init__(self, settings_manager, i18n, managers):
        # ...
        self.model_manager = managers.get('model_manager')

        # 连接模型更新信号
        if self.model_manager:
            self.model_manager.models_updated.connect(self._update_model_list)

    def _create_engine_configs(self):
        """创建引擎配置"""
        # ...
        # Whisper 模型选择
        self.model_size_combo = QComboBox()
        self._update_model_list()
        # ...

    def _update_model_list(self):
        """更新模型列表"""
        if not self.model_manager:
            return

        current_model = self.model_size_combo.currentText()
        self.model_size_combo.clear()

        downloaded_models = self.model_manager.get_downloaded_models()
        for model in downloaded_models:
            self.model_size_combo.addItem(model.name)

        # 恢复选择
        index = self.model_size_combo.findText(current_model)
        if index >= 0:
            self.model_size_combo.setCurrentIndex(index)
```

## 数据模型

### 数据库 Schema

```sql
-- 模型使用统计表
CREATE TABLE model_usage_stats (
    id TEXT PRIMARY KEY,
    model_name TEXT NOT NULL,
    usage_count INTEGER DEFAULT 0,
    last_used TIMESTAMP,
    total_transcription_duration REAL DEFAULT 0,  -- 累计转录时长（秒）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_model_usage_name ON model_usage_stats(model_name);
```

### 配置文件扩展

```json
{
  "transcription": {
    "faster_whisper": {
      "model_dir": "~/.echonote/models",
      "auto_download_recommended": false,
      "default_model": "base"
    }
  }
}
```

## 错误处理

### 错误类型和处理策略

1. **网络错误**

   - 错误消息："网络连接失败，请检查网络设置"
   - 处理：提供"重试"按钮，支持断点续传

2. **磁盘空间不足**

   - 错误消息："磁盘空间不足，需要至少 XXX MB 空间"
   - 处理：提前检测，阻止下载，建议清理空间

3. **模型验证失败**

   - 错误消息："模型文件损坏，请重新下载"
   - 处理：自动删除损坏文件，提供"重新下载"按钮

4. **权限不足**

   - 错误消息："无法访问模型目录，请检查文件权限"
   - 处理：提供"选择其他目录"选项

5. **模型正在使用**
   - 错误消息："模型正在使用中，无法删除"
   - 处理：禁用删除按钮，显示提示

## 性能优化

### 1. 异步操作

- 所有模型下载使用异步机制，不阻塞 UI
- 模型扫描在后台线程执行
- 模型验证使用线程池并发执行

### 2. 缓存策略

- 模型列表缓存在内存中，避免重复扫描
- 使用文件系统监听器（watchdog）监控模型目录变化

### 3. 进度更新优化

- 下载进度每秒更新一次，避免过于频繁的 UI 刷新
- 使用节流（throttle）机制限制信号发射频率

## 测试策略

### 单元测试

1. **ModelRegistry 测试**

   - 测试模型扫描
   - 测试模型状态更新
   - 测试模型查询

2. **ModelDownloader 测试**

   - 测试下载流程（使用 mock）
   - 测试取消下载
   - 测试错误处理

3. **ModelValidator 测试**
   - 测试模型验证逻辑
   - 测试损坏模型检测

### 集成测试

1. **端到端下载测试**

   - 测试完整的下载流程
   - 测试下载后模型可用性

2. **UI 集成测试**
   - 测试模型列表同步
   - 测试下载进度显示

## 部署和迁移

### 首次部署

1. 创建模型目录结构
2. 初始化模型注册表
3. 扫描现有模型（如果有）

### 数据迁移

如果用户已有旧版本的模型：

1. 扫描旧模型目录
2. 验证模型完整性
3. 更新注册表
4. 保留旧模型，不强制重新下载

## 未来扩展

### 1. 模型自动更新

- 检测 Hugging Face 上的模型更新
- 提供"更新模型"功能

### 2. 自定义模型支持

- 允许用户导入自定义训练的模型
- 提供模型格式转换工具

### 3. 模型性能基准测试

- 在用户设备上运行基准测试
- 提供性能报告，帮助用户选择最佳模型

### 4. 云端模型缓存

- 支持从 CDN 下载模型，提高下载速度
- 支持 P2P 模型分享（可选）

## 安全考虑

1. **模型来源验证**

   - 仅从官方 Hugging Face 仓库下载
   - 验证模型文件的 SHA256 校验和

2. **文件权限**

   - 模型文件设置为仅当前用户可读写（0600）
   - 模型目录设置为仅当前用户可访问（0700）

3. **磁盘配额**
   - 限制模型总大小（可配置，默认 10GB）
   - 超过配额时提示用户删除旧模型

## 总结

模型管理功能的设计遵循以下原则：

1. **最小侵入**：在现有架构上扩展，避免大规模重构
2. **用户友好**：提供直观的 UI 和清晰的错误提示
3. **性能优先**：异步操作，不阻塞 UI
4. **可维护性**：模块化设计，清晰的职责划分
5. **可扩展性**：为未来功能预留扩展点

通过这个设计，用户可以方便地管理本地 Whisper 模型，系统可以自动同步模型列表到所有相关界面，确保功能的一致性和可用性。
