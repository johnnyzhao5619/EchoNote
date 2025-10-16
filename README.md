# EchoNote

> Local-first transcription, calendar orchestration, and timeline insights for desktop knowledge workers.

## 🌐 Language Overview
- [English](#english)
- [中文](#中文)
- [Français](#français)

---

### English
#### Project Snapshot
- **Framework**: PyQt6 entry point in `main.py`
- **Core Domains**: batch/real-time transcription, calendar sync, task automation, settings management
- **Operating Principles**: privacy-first, encrypted persistence, proactive resource checks

#### Feature Highlights
1. **Batch Transcription** – `core/transcription` coordinates Faster-Whisper engines, resumable queues, and export formatting.
2. **Real-time Recording** – `core/realtime` plus `engines/audio` provide capture, gain control, voice activity detection, and optional translation.
3. **Calendar Hub** – `core/calendar` stores local events while `engines/calendar_sync` integrates Google and Outlook accounts.
4. **Timeline Automation** – `core/timeline` links events with recordings, maintains auto-task rules, and exposes history queries.
5. **Secure Storage** – `data/database`, `data/security`, and `data/storage` deliver encrypted SQLite, token vaults, and file lifecycle helpers.
6. **System Health** – `utils/` centralises logging, diagnostics, resource monitoring, and FFmpeg checks.

#### Repository Layout
```
EchoNote/
├── main.py                # Application bootstrap & dependency wiring
├── config/                # Default configuration and runtime manager
├── core/                  # Feature managers (calendar, realtime, timeline, transcription, settings)
├── engines/               # Pluggable engines (audio capture, speech, translation, calendar sync)
├── data/                  # Database schema/models, encrypted storage, file management
├── ui/                    # Qt widgets, dialogs, and navigation shell
├── utils/                 # Logging, i18n, diagnostics, resource monitoring
└── tests/                 # Unit and integration suites
```

#### Environment Requirements
- Python 3.10 or newer
- Optional: PyAudio (microphone capture), FFmpeg (media formats), CUDA GPU (acceleration)
- First launch writes encrypted SQLite data, logs, and settings to `~/.echonote`

#### Run from Source
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python main.py
```

#### Configuration Notes
- Defaults live in `config/default_config.json`; user overrides persist to `~/.echonote/app_config.json`.
- Recordings and transcripts are stored under `~/Documents/EchoNote/` by default.
- Provide OAuth credentials in the settings UI before enabling Google or Outlook sync.

#### Quality & Testing
- `pytest tests/unit` – core logic and utilities
- `pytest tests/integration` – database, engines, and schedulers (requires local dependencies)
- Optional E2E and performance baselines reside in `tests/`

Install development extras with `pip install -r requirements-dev.txt` when running broader suites.

#### Documentation
- User handbook: `docs/user-guide/README.md`
- Quick start: `docs/quick-start/README.md`
- Project overview: `docs/project-overview/README.md`
- Developer resources: `docs/DEVELOPER_GUIDE.md`, `docs/API_REFERENCE.md`

#### License
Released under the [MIT License](LICENSE).

---

### 中文
#### 项目速览
- **框架**：PyQt6 桌面应用，入口位于 `main.py`
- **核心领域**：批量/实时转录、日历同步、自动任务、设置管理
- **运行原则**：隐私优先、加密持久化、主动的资源诊断

#### 核心特性
1. **批量转录** —— `core/transcription` 调度 Faster-Whisper 引擎、支持任务重试与多格式导出。
2. **实时录制** —— `core/realtime` 与 `engines/audio` 提供音频捕获、增益控制、语音活动检测与可选翻译。
3. **日历中心** —— `core/calendar` 管理本地事件，`engines/calendar_sync` 负责 Google/Outlook 账户对接。
4. **时间线自动化** —— `core/timeline` 关联事件与录音，维护自动任务规则并提供历史检索。
5. **安全存储** —— `data/database`、`data/security`、`data/storage` 提供加密 SQLite、令牌保管与文件生命周期管理。
6. **系统健康** —— `utils/` 集中处理日志、诊断、资源监控与 FFmpeg 检测。

#### 目录结构
```
EchoNote/
├── main.py                # 应用启动与依赖装配
├── config/                # 默认配置与运行时管理器
├── core/                  # 功能管理器（calendar、realtime、timeline、transcription、settings）
├── engines/               # 可插拔引擎（音频捕获、语音、翻译、日历同步）
├── data/                  # 数据库 schema/模型、加密存储、文件管理
├── ui/                    # Qt 组件、对话框与导航框架
├── utils/                 # 日志、国际化、诊断、资源监控
└── tests/                 # 单元与集成测试
```

#### 环境要求
- Python 3.10 及以上
- 可选依赖：PyAudio（麦克风采集）、FFmpeg（媒体格式）、CUDA GPU（加速）
- 首次启动会在 `~/.echonote` 下写入加密数据库、日志与配置

#### 运行项目
```bash
python -m venv .venv
source .venv/bin/activate   # Windows 使用 .venv\\Scripts\\activate
pip install -r requirements.txt
python main.py
```

#### 配置说明
- 默认配置位于 `config/default_config.json`，用户修改会保存到 `~/.echonote/app_config.json`。
- 录音与转录文件默认存放在 `~/Documents/EchoNote/`。
- 启用 Google 或 Outlook 同步前，请先在设置界面填入 OAuth 凭据。

#### 质量与测试
- `pytest tests/unit` —— 核心逻辑与工具单元测试
- `pytest tests/integration` —— 数据库、引擎与调度器集成测试（需本地依赖）
- 其他端到端与性能场景位于 `tests/`

如需运行更多测试，请先执行 `pip install -r requirements-dev.txt` 安装开发依赖。

#### 文档
- 使用手册：`docs/user-guide/README.md`
- 快速入门：`docs/quick-start/README.md`
- 项目说明：`docs/project-overview/README.md`
- 开发者参考：`docs/DEVELOPER_GUIDE.md`、`docs/API_REFERENCE.md`

#### 许可证
项目遵循 [MIT License](LICENSE)。

---

### Français
#### Aperçu du projet
- **Cadre** : application PyQt6 dont le point d’entrée est `main.py`
- **Domaines clés** : transcription batch/temps réel, synchronisation calendrier, automatisation des tâches, gestion des paramètres
- **Principes opérationnels** : confidentialité par défaut, persistance chiffrée, surveillance proactive des ressources

#### Fonctionnalités principales
1. **Transcription par lots** – `core/transcription` orchestre les moteurs Faster-Whisper, gère les files avec reprise et l’export multi-formats.
2. **Enregistrement en temps réel** – `core/realtime` et `engines/audio` gèrent la capture, le gain, la détection d’activité vocale et la traduction optionnelle.
3. **Hub calendrier** – `core/calendar` stocke les événements locaux et `engines/calendar_sync` connecte les comptes Google et Outlook.
4. **Automatisation de la timeline** – `core/timeline` relie événements et enregistrements, maintient les règles automatiques et expose les requêtes historiques.
5. **Stockage sécurisé** – `data/database`, `data/security` et `data/storage` fournissent SQLite chiffré, coffre à jetons et gestion du cycle de vie des fichiers.
6. **Santé du système** – `utils/` centralise journalisation, diagnostics, surveillance des ressources et contrôles FFmpeg.

#### Structure du dépôt
```
EchoNote/
├── main.py                # Initialisation de l’application et injection des dépendances
├── config/                # Configuration par défaut et gestionnaire d’exécution
├── core/                  # Gestionnaires métiers (calendar, realtime, timeline, transcription, settings)
├── engines/               # Moteurs interchangeables (capture audio, reconnaissance, traduction, synchronisation calendrier)
├── data/                  # Schéma/modèles SQLite, stockage chiffré, gestion des fichiers
├── ui/                    # Widgets Qt, boîtes de dialogue, shell de navigation
├── utils/                 # Journalisation, i18n, diagnostics, surveillance des ressources
└── tests/                 # Tests unitaires et d’intégration
```

#### Prérequis
- Python 3.10 ou supérieur
- Optionnel : PyAudio (capture micro), FFmpeg (formats média), GPU CUDA (accélération)
- Le premier lancement crée la base SQLite chiffrée, les journaux et la configuration dans `~/.echonote`

#### Exécution
```bash
python -m venv .venv
source .venv/bin/activate   # Windows : .venv\\Scripts\\activate
pip install -r requirements.txt
python main.py
```

#### Configuration
- Les valeurs par défaut résident dans `config/default_config.json`; les substitutions utilisateur sont stockées dans `~/.echonote/app_config.json`.
- Les enregistrements et transcriptions sont sauvegardés dans `~/Documents/EchoNote/`.
- Ajoutez les identifiants OAuth dans l’UI des paramètres avant d’activer la synchronisation Google ou Outlook.

#### Qualité & tests
- `pytest tests/unit` – logique cœur et utilitaires
- `pytest tests/integration` – base de données, moteurs et ordonnanceurs (dépendances locales requises)
- Les scénarios E2E et performance supplémentaires se trouvent dans `tests/`

Installez les dépendances de développement avec `pip install -r requirements-dev.txt` pour une couverture élargie.

#### Documentation
- Guide utilisateur : `docs/user-guide/README.md`
- Démarrage rapide : `docs/quick-start/README.md`
- Présentation du projet : `docs/project-overview/README.md`
- Ressources développeur : `docs/DEVELOPER_GUIDE.md`, `docs/API_REFERENCE.md`

#### Licence
Projet distribué sous [Licence MIT](LICENSE).
