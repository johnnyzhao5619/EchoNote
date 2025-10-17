<p align="center">
  <svg width="128" height="128" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="echonoteIconTitle">
    <title id="echonoteIconTitle">EchoNote Application Icon</title>
    <defs>
      <linearGradient id="pageGradient" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#4F46E5" />
        <stop offset="100%" stop-color="#22D3EE" />
      </linearGradient>
      <linearGradient id="waveGradient" x1="0%" y1="50%" x2="100%" y2="50%">
        <stop offset="0%" stop-color="#F472B6" />
        <stop offset="100%" stop-color="#FB923C" />
      </linearGradient>
    </defs>
    <rect x="16" y="16" width="80" height="96" rx="12" fill="url(#pageGradient)" />
    <rect x="26" y="28" width="60" height="18" rx="4" fill="#FFFFFFD9" />
    <rect x="26" y="54" width="60" height="8" rx="4" fill="#FFFFFF99" />
    <rect x="26" y="68" width="48" height="8" rx="4" fill="#FFFFFF99" />
    <rect x="26" y="82" width="54" height="8" rx="4" fill="#FFFFFF99" />
    <path d="M90 34 L110 24 L110 104 L90 94 Z" fill="#1E1B4B" opacity="0.2" />
    <path d="M96 58 C100 52 104 52 108 58 C112 64 116 64 120 58" stroke="url(#waveGradient)" stroke-width="6" stroke-linecap="round" fill="none" />
    <circle cx="94" cy="70" r="6" fill="#F8FAFC" opacity="0.85" />
    <circle cx="108" cy="70" r="6" fill="#F8FAFC" opacity="0.65" />
    <circle cx="120" cy="70" r="5" fill="#F8FAFC" opacity="0.45" />
  </svg>
</p>

<h1 align="center">EchoNote</h1>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-2563EB.svg" alt="MIT License badge"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-4B5563.svg" alt="Python 3.10+ badge">
  <img src="https://img.shields.io/badge/Desktop-Local%20First-0EA5E9.svg" alt="Desktop local-first badge">
</p>

<p align="center">
  <img src="data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20viewBox%3D%220%200%20128%20128%22%3E%3Cdefs%3E%3ClinearGradient%20id%3D%22grad%22%20x1%3D%220%25%22%20y1%3D%220%25%22%20x2%3D%22100%25%22%20y2%3D%22100%25%22%3E%3Cstop%20offset%3D%220%25%22%20stop-color%3D%22%234f46e5%22/%3E%3Cstop%20offset%3D%22100%25%22%20stop-color%3D%22%230ea5e9%22/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect%20width%3D%22128%22%20height%3D%22128%22%20rx%3D%2224%22%20fill%3D%22url%28%23grad%29%22/%3E%3Cg%20fill%3D%22none%22%20stroke%3D%22%23f8fafc%22%20stroke-width%3D%226%22%20stroke-linecap%3D%22round%22%3E%3Cpath%20d%3D%22M32%2064h8l6-20%2010%2040%2012-48%2010%2028%206-16h12%22/%3E%3C/g%3E%3Ccircle%20cx%3D%2296%22%20cy%3D%2232%22%20r%3D%2210%22%20fill%3D%22%2322d3ee%22%20opacity%3D%220.9%22/%3E%3C/svg%3E" alt="EchoNote Icon" width="120" height="120" />
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT" /></a>
  <img src="https://img.shields.io/badge/Desktop-PyQt6-9cf.svg" alt="Desktop: PyQt6" />
  <img src="https://img.shields.io/badge/Local--first-Privacy%20Focused-22c55e.svg" alt="Local-first privacy focused" />
</p>

> Local-first transcription, calendar orchestration, and timeline insights for desktop knowledge workers.

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
