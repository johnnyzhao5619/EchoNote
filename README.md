<h1 align="left">EchoNote</h1>

<p align="left">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-2563EB.svg" alt="MIT License badge"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-4B5563.svg" alt="Python 3.10+ badge">
  <img src="https://img.shields.io/badge/Desktop-Local%20First-0EA5E9.svg" alt="Desktop local-first badge">
</p>

## 🌐 Language Overview
- [English](#english)
- [中文](#中文)
- [Français](#français)

## 📚 Global Index
- [System Architecture Overview](#system-architecture-overview)
- [Core Capabilities Matrix](#core-capabilities-matrix)
- [Documentation Library](#documentation-library)
- [Developer Toolchain](#developer-toolchain)
- [License](#license)

### System Architecture Overview
```
EchoNote/
├── main.py                # PyQt6 bootstrap, dependency wiring, runtime orchestration
├── config/                # Default configuration and runtime config manager
├── core/                  # Feature domains: calendar, realtime, timeline, transcription, settings
├── engines/               # Integrations: audio capture, speech, translation, calendar sync
├── data/                  # Database schema/models, encrypted storage, file lifecycle helpers
├── ui/                    # Desktop UI components, dialogs, feature modules
├── utils/                 # Logging, diagnostics, i18n, startup & resource utilities
└── tests/                 # Unit, integration, and scenario harnesses
```

### Core Capabilities Matrix
| Domain | Purpose | Key Modules |
| --- | --- | --- |
| Batch & realtime transcription | Task queueing, model orchestration, export formats | `core/transcription`, `engines/speech/`, `ui/batch_transcribe`, `ui/realtime_record` |
| Calendar orchestration | Local persistence, Google/Outlook sync, OAuth lifecycle | `core/calendar`, `engines/calendar_sync`, `data/security/oauth_manager.py`, `ui/calendar_hub` |
| Timeline intelligence | Event correlation, automation rules, reminders | `core/timeline`, `ui/timeline` |
| Settings & preferences | Config surfaces, model downloads, appearance | `core/settings`, `ui/settings`, `core/models` |
| Platform services | Logging, error handling, startup health, resource safety | `utils/`, `data/security`, `engines/audio` |

### Documentation Library
| Audience | Focus | Location |
| --- | --- | --- |
| New users | Guided onboarding & workflows | `docs/quick-start/README.md`, `docs/user-guide/README.md` |
| Product overview | Value proposition & personas | `docs/project-overview/README.md` |
| API & architecture | Core services, data flow diagrams | `docs/DEVELOPER_GUIDE.md`, `docs/API_REFERENCE.md` |
| Accessibility & UX | Accessibility checklist, UI rationale | `docs/ACCESSIBILITY.md`, `ui/*/README.md` |
| Contribution | Coding standards, contribution process | `docs/CODE_STANDARDS.md`, `docs/CONTRIBUTING.md` |
| Cloud engines | External speech engine requirements | `engines/speech/CLOUD_ENGINES_IMPLEMENTATION.md` |

### Developer Toolchain
- Python 3.10+
- Optional accelerants: PyAudio (capture), FFmpeg (media), CUDA GPU (Faster-Whisper)
- Environment setup (`python -m venv .venv && source .venv/bin/activate`)
- Install dependencies with `pip install -r requirements.txt`
- Launch the desktop client via `python main.py`
- Extended tooling: `pip install -r requirements-dev.txt`
- Testing guardrails:
  - Unit tests – `pytest tests/unit`
  - Integration tests – `pytest tests/integration`
  - Performance/E2E harness – `pytest tests/e2e_performance_test.py`

### License
Released under the [MIT License](LICENSE).

---

### English
#### Project Snapshot
- **Framework**: PyQt6 entry point in `main.py`
- **Core Domains**: batch/real-time transcription, calendar sync, task automation, settings management
- **Operating Principles**: privacy-first, encrypted persistence, proactive resource checks

#### Quick Start Checklist
1. Create and activate a virtual environment.
2. `pip install -r requirements.txt`
3. Run `python main.py`
4. On first launch complete the guided setup (storage paths, FFmpeg check, model download recommendation).

#### Feature Highlights
1. **Batch Transcription** – `core/transcription` coordinates Faster-Whisper engines, resumable queues, and export formatting.
2. **Real-time Recording** – `core/realtime` plus `engines/audio` provide capture, gain control, voice activity detection, and optional translation.
3. **Calendar Hub** – `core/calendar` stores local events while `engines/calendar_sync` integrates Google and Outlook accounts.
4. **Timeline Automation** – `core/timeline` links events with recordings, maintains auto-task rules, and exposes history queries.
5. **Secure Storage** – `data/database`, `data/security`, and `data/storage` deliver encrypted SQLite, token vaults, and file lifecycle helpers.
6. **System Health** – `utils/` centralises logging, diagnostics, resource monitoring, and FFmpeg checks.

#### Environment Requirements
- Python 3.10 or newer
- Optional: PyAudio (microphone capture), FFmpeg (media formats), CUDA GPU (acceleration)
- First launch writes encrypted SQLite data, logs, and settings to `~/.echonote`

#### Configuration Notes
- Defaults live in `config/default_config.json`; user overrides persist to `~/.echonote/app_config.json`.
- Recordings and transcripts are stored under `~/Documents/EchoNote/` by default.
- Provide OAuth credentials in the settings UI before enabling Google or Outlook sync.

#### Operational Index
- **Runtime orchestration**: `main.py`, `utils/startup_optimizer.py`
- **Audio services**: `engines/audio/`, `core/realtime/`
- **Transcription pipeline**: `core/transcription/`, `core/models/`
- **Calendar sync**: `core/calendar/`, `engines/calendar_sync/`
- **UI modules**: `ui/main_window.py`, `ui/sidebar.py`, feature widgets under `ui/*`
- **Security**: `data/security/`, `utils/error_handler.py`
- **Testing suites**: `tests/core/test_model_manager.py`, placeholders under `tests/unit`, `tests/integration`

#### Quality & Testing
- `pytest tests/unit` – core logic and utilities
- `pytest tests/integration` – database, engines, and schedulers (requires local dependencies)
- Optional E2E and performance baselines reside in `tests/`

#### Documentation References
- User handbook: `docs/user-guide/README.md`
- Quick start: `docs/quick-start/README.md`
- Project overview: `docs/project-overview/README.md`
- Developer resources: `docs/DEVELOPER_GUIDE.md`, `docs/API_REFERENCE.md`

---

### 中文
#### 项目速览
- **框架**：PyQt6 桌面应用，入口位于 `main.py`
- **核心领域**：批量/实时转录、日历同步、自动任务、设置管理
- **运行原则**：隐私优先、加密持久化、主动的资源诊断

#### 快速启动清单
1. 创建并激活虚拟环境。
2. 执行 `pip install -r requirements.txt` 安装依赖。
3. 运行 `python main.py` 启动桌面客户端。
4. 首次启动按向导完成存储路径、FFmpeg 检测、模型下载建议等设置。

#### 核心特性
1. **批量转录** —— `core/transcription` 调度 Faster-Whisper 引擎、支持任务重试与多格式导出。
2. **实时录制** —— `core/realtime` 与 `engines/audio` 提供音频捕获、增益控制、语音活动检测与可选翻译。
3. **日历中心** —— `core/calendar` 管理本地事件，`engines/calendar_sync` 负责 Google/Outlook 账户对接。
4. **时间线自动化** —— `core/timeline` 关联事件与录音，维护自动任务规则并提供历史检索。
5. **安全存储** —— `data/database`、`data/security`、`data/storage` 提供加密 SQLite、令牌保管与文件生命周期管理。
6. **系统健康** —— `utils/` 集中处理日志、诊断、资源监控与 FFmpeg 检测。

#### 环境要求
- Python 3.10 及以上
- 可选依赖：PyAudio（麦克风采集）、FFmpeg（媒体格式）、CUDA GPU（加速）
- 首次启动会在 `~/.echonote` 下写入加密数据库、日志与配置

#### 配置索引
- 默认配置：`config/default_config.json`
- 用户配置：`~/.echonote/app_config.json`
- 录音/转录目录：`~/Documents/EchoNote/`
- OAuth 管理：`data/security/oauth_manager.py`

#### 模块索引
- **运行调度**：`main.py`、`utils/startup_optimizer.py`
- **音频链路**：`engines/audio/`、`core/realtime/`
- **转录与模型**：`core/transcription/`、`core/models/`
- **日历同步**：`core/calendar/`、`engines/calendar_sync/`
- **桌面界面**：`ui/main_window.py`、`ui/sidebar.py` 及功能子模块
- **安全机制**：`data/security/`、`utils/error_handler.py`
- **测试样例**：`tests/core/test_model_manager.py`、`tests/` 下的占位目录

#### 质量与测试
- `pytest tests/unit` —— 核心逻辑与工具单元测试
- `pytest tests/integration` —— 数据库、引擎与调度器集成测试（需本地依赖）
- 其他端到端与性能场景位于 `tests/`

#### 文档索引
- 使用手册：`docs/user-guide/README.md`
- 快速入门：`docs/quick-start/README.md`
- 项目说明：`docs/project-overview/README.md`
- 开发者参考：`docs/DEVELOPER_GUIDE.md`、`docs/API_REFERENCE.md`

---

### Français
#### Aperçu du projet
- **Cadre** : application PyQt6 dont le point d’entrée est `main.py`
- **Domaines clés** : transcription batch/temps réel, synchronisation calendrier, automatisation des tâches, gestion des paramètres
- **Principes opérationnels** : confidentialité par défaut, persistance chiffrée, surveillance proactive des ressources

#### Démarrage rapide
1. Créez et activez un environnement virtuel.
2. Installez les dépendances avec `pip install -r requirements.txt`.
3. Lancez `python main.py` pour ouvrir le client.
4. Suivez l’assistant initial (chemins de stockage, vérification FFmpeg, recommandation de modèle).

#### Fonctionnalités principales
1. **Transcription par lots** – `core/transcription` orchestre les moteurs Faster-Whisper, gère les files avec reprise et l’export multi-formats.
2. **Enregistrement en temps réel** – `core/realtime` et `engines/audio` gèrent la capture, le gain, la détection d’activité vocale et la traduction optionnelle.
3. **Hub calendrier** – `core/calendar` stocke les événements locaux et `engines/calendar_sync` connecte les comptes Google et Outlook.
4. **Automatisation de la timeline** – `core/timeline` relie événements et enregistrements, maintient les règles automatiques et expose les requêtes historiques.
5. **Stockage sécurisé** – `data/database`, `data/security` et `data/storage` fournissent SQLite chiffré, coffre à jetons et gestion du cycle de vie des fichiers.
6. **Santé du système** – `utils/` centralise journalisation, diagnostics, surveillance des ressources et contrôles FFmpeg.

#### Prérequis
- Python 3.10 ou supérieur
- Optionnel : PyAudio (capture micro), FFmpeg (formats média), GPU CUDA (accélération)
- Le premier lancement crée la base SQLite chiffrée, les journaux et la configuration dans `~/.echonote`

#### Index de configuration
- Configuration par défaut : `config/default_config.json`
- Surcharges utilisateur : `~/.echonote/app_config.json`
- Stockage des enregistrements : `~/Documents/EchoNote/`
- Gestion OAuth : `data/security/oauth_manager.py`

#### Index fonctionnel
- **Orchestration runtime** : `main.py`, `utils/startup_optimizer.py`
- **Chaîne audio** : `engines/audio/`, `core/realtime/`
- **Pipeline de transcription** : `core/transcription/`, `core/models/`
- **Synchronisation calendrier** : `core/calendar/`, `engines/calendar_sync/`
- **Interface utilisateur** : `ui/main_window.py`, `ui/sidebar.py`, modules `ui/*`
- **Sécurité & résilience** : `data/security/`, `utils/error_handler.py`
- **Tests** : `tests/core/test_model_manager.py`, suites `tests/`

#### Qualité & tests
- `pytest tests/unit` – logique cœur et utilitaires
- `pytest tests/integration` – base de données, moteurs et ordonnanceurs (dépendances locales requises)
- Scénarios E2E et performance supplémentaires dans `tests/`

#### Documentation
- Guide utilisateur : `docs/user-guide/README.md`
- Démarrage rapide : `docs/quick-start/README.md`
- Présentation du projet : `docs/project-overview/README.md`
- Ressources développeur : `docs/DEVELOPER_GUIDE.md`, `docs/API_REFERENCE.md`
