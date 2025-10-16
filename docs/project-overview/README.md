# EchoNote Project Overview

Review this overview before modifying core modules to understand dependency boundaries.

## 1. Design Goals
- Deliver an offline-first experience for transcription and calendar management.
- Keep engines pluggable so speech, translation, and calendar providers can evolve independently.
- Maintain desktop-grade security, maintainability, and predictable performance.

<details>
<summary>中文</summary>

- 提供离线优先的语音转录和日程管理体验。
- 通过可插拔引擎支持语音、翻译、日历提供商的独立演进。
- 在桌面环境保证数据安全、可维护性与稳定性能。

</details>

<details>
<summary>Français</summary>

- Offrir une expérience hors-ligne pour la transcription et la gestion d’agenda.
- Garder des moteurs interchangeables afin de faire évoluer parole, traduction et calendriers indépendamment.
- Maintenir un niveau de sécurité, de maintenabilité et de performance adapté au poste de travail.

</details>

## 2. Architecture Summary
```
┌───────────┐      ┌──────────┐      ┌───────────┐
│    UI     │ ───▶ │   Core   │ ───▶ │  Engines  │
└───────────┘      └──────────┘      └───────────┘
        │                 │                   │
        ▼                 ▼                   ▼
     utils/          data/ layer        External services
```
- **UI layer** (`ui/`): PyQt6 widgets, dialogs, notifications, and localisation assets.
- **Core layer** (`core/`): domain managers coordinating database, engines, and UI interactions.
- **Engines layer** (`engines/`): concrete implementations for audio capture, speech recognition, translation, and calendar sync.
- **Data layer** (`data/`): SQLite schema, models, encryption, storage utilities, and secrets management.
- **Utilities** (`utils/`): logging, error handling, resource monitoring, startup optimisation, and i18n.

<details>
<summary>中文</summary>

```
┌───────────┐      ┌──────────┐      ┌───────────┐
│   UI 层   │ ───▶ │  Core 层 │ ───▶ │ Engines 层 │
└───────────┘      └──────────┘      └───────────┘
        │                 │                   │
        ▼                 ▼                   ▼
   utils/ 工具       data/ 数据层        外部服务 (音频、日历)
```
- **UI 层** (`ui/`)：PyQt6 组件、对话框、通知与国际化文本。
- **Core 层** (`core/`)：业务管理器，负责调度数据库、引擎和 UI 事件。
- **Engines 层** (`engines/`)：音频捕获、语音识别、翻译、日历同步的具体实现。
- **数据层** (`data/`)：SQLite schema、模型、加密、存储工具及密钥管理。
- **工具层** (`utils/`)：日志、异常处理、资源监控、启动优化与国际化支持。

</details>

<details>
<summary>Français</summary>

```
┌───────────┐      ┌──────────┐      ┌───────────┐
│    UI     │ ───▶ │   Core   │ ───▶ │  Engines  │
└───────────┘      └──────────┘      └───────────┘
        │                 │                   │
        ▼                 ▼                   ▼
     utils/          data/ layer        Services externes
```
- **Couche UI** (`ui/`) : widgets PyQt6, dialogues, notifications et textes localisés.
- **Couche Core** (`core/`) : gestionnaires métier coordonnant base de données, moteurs et UI.
- **Couche Engines** (`engines/`) : implémentations pour capture audio, reconnaissance vocale, traduction et synchronisation calendrier.
- **Couche Données** (`data/`) : schéma SQLite, modèles, chiffrement, stockage et gestion des secrets.
- **Utilitaires** (`utils/`) : journalisation, gestion d’erreurs, surveillance des ressources, optimisation du démarrage, i18n.

</details>

## 3. Key Modules
| Module | Path | Responsibility |
| ------ | ---- | -------------- |
| Config Manager | `config/app_config.py` | Load defaults, validate schema, persist user overrides |
| Database Connection | `data/database/connection.py` | Thread-safe SQLite access, schema initialisation, optional SQLCipher key |
| Database Models | `data/database/models.py` | CRUD helpers for tasks, calendar events, attachments, auto-task configs, sync status |
| Encryption & Tokens | `data/security/` | AES-GCM utilities, OAuth token vault, secrets helper |
| Transcription Manager | `core/transcription/manager.py` | Queue orchestration, engine coordination, format conversion |
| Task Queue | `core/transcription/task_queue.py` | Async worker pool with retry/backoff and pause/resume support |
| Realtime Recorder | `core/realtime/recorder.py` | Microphone capture, streaming transcription, translation dispatch, file persistence |
| Calendar Manager | `core/calendar/manager.py` | Local CRUD, sync scheduling, colour policies, provider state tracking |
| Timeline Manager | `core/timeline/manager.py` | Timeline queries, pagination, linking attachments to events |
| Auto Task Scheduler | `core/timeline/auto_task_scheduler.py` | Prepare and trigger meeting recordings/transcriptions based on calendar rules |

<details>
<summary>中文</summary>

| 模块 | 位置 | 作用 |
| ---- | ---- | ---- |
| 配置管理 | `config/app_config.py` | 加载默认配置、验证必填项、保存用户偏好 |
| 数据库连接 | `data/database/connection.py` | 线程安全的 SQLite 访问、schema 初始化、可选 SQLCipher 密钥 |
| 数据模型 | `data/database/models.py` | 任务、日历事件、附件、自动任务配置、同步状态的 CRUD 工具 |
| 加密与令牌 | `data/security/` | AES-GCM 工具、OAuth 凭据保险箱、密钥管理 |
| 转录管理 | `core/transcription/manager.py` | 任务队列调度、引擎协同、格式转换 |
| 任务队列 | `core/transcription/task_queue.py` | 支持重试/退避与暂停/恢复的异步工作池 |
| 实时录制 | `core/realtime/recorder.py` | 音频捕获、流式转录、翻译派发、文件落地 |
| 日历管理 | `core/calendar/manager.py` | 本地 CRUD、同步计划、颜色策略、账户状态追踪 |
| 时间线管理 | `core/timeline/manager.py` | 时间线查询、分页、关联事件附件 |
| 自动任务调度 | `core/timeline/auto_task_scheduler.py` | 基于日历规则准备并触发会议录音/转录 |

</details>

<details>
<summary>Français</summary>

| Module | Emplacement | Rôle |
| ------ | ----------- | ---- |
| Gestionnaire de config | `config/app_config.py` | Charger les valeurs par défaut, valider le schéma, persister les préférences |
| Connexion base | `data/database/connection.py` | Accès SQLite thread-safe, initialisation du schéma, clé SQLCipher optionnelle |
| Modèles de données | `data/database/models.py` | CRUD pour tâches, événements, pièces jointes, auto-tâches, statut de synchronisation |
| Chiffrement & tokens | `data/security/` | Outils AES-GCM, coffre OAuth, gestionnaire de secrets |
| Gestionnaire transcription | `core/transcription/manager.py` | Orchestration de file, coordination moteur, conversion de formats |
| File de tâches | `core/transcription/task_queue.py` | Pool asynchrone avec retry/backoff et prise en charge pause/reprise |
| Enregistreur temps réel | `core/realtime/recorder.py` | Capture micro, transcription en continu, traduction, persistance des fichiers |
| Gestionnaire calendrier | `core/calendar/manager.py` | CRUD local, planification des synchronisations, politique de couleurs, suivi des comptes |
| Gestionnaire timeline | `core/timeline/manager.py` | Requêtes chronologiques, pagination, association des pièces jointes |
| Planificateur auto-tâches | `core/timeline/auto_task_scheduler.py` | Préparer/déclencher enregistrements et transcriptions selon les règles calendrier |

</details>

## 4. Data & Security
- **Database**: `~/.echonote/data.db` encrypted when SQLCipher is available; keys managed under `data/security`.
- **File storage**: recordings and transcripts live in `~/Documents/EchoNote/` unless reconfigured.
- **Secrets**: OAuth credentials stored via the secrets manager to avoid plaintext exposure.
- **Logging**: every subsystem writes to `~/.echonote/logs/echonote.log` for unified diagnostics.

<details>
<summary>中文</summary>

- **数据库**：`~/.echonote/data.db`，若系统支持 SQLCipher 则自动开启加密，密钥由 `data/security` 管理。
- **文件存储**：录音与转录默认保存在 `~/Documents/EchoNote/`，可在设置中自定义。
- **敏感信息**：OAuth 凭据通过安全存储管理，避免明文暴露。
- **日志**：所有模块统一写入 `~/.echonote/logs/echonote.log`，便于诊断。

</details>

<details>
<summary>Français</summary>

- **Base** : `~/.echonote/data.db`, chiffrée si SQLCipher disponible ; clés gérées par `data/security`.
- **Fichiers** : enregistrements et transcriptions stockés dans `~/Documents/EchoNote/` sauf configuration contraire.
- **Secrets** : identifiants OAuth conservés via le gestionnaire sécurisé afin d’éviter toute exposition en clair.
- **Logs** : chaque sous-système écrit dans `~/.echonote/logs/echonote.log` pour un diagnostic unifié.

</details>

## 5. Dependency Management
- Runtime dependencies are listed in `requirements.txt`; development extras in `requirements-dev.txt`.
- Runtime checks for FFmpeg and system resources are implemented in `utils/ffmpeg_checker` and `utils/resource_monitor`.
- Model cache paths are configurable through the config manager.

<details>
<summary>中文</summary>

- 运行依赖位于 `requirements.txt`，开发依赖位于 `requirements-dev.txt`。
- `utils/ffmpeg_checker` 与 `utils/resource_monitor` 在运行期检测依赖与资源状态。
- 模型缓存路径可通过配置管理器自定义。

</details>

<details>
<summary>Français</summary>

- Dépendances runtime dans `requirements.txt`, dépendances de développement dans `requirements-dev.txt`.
- Vérifications FFmpeg et surveillance des ressources implémentées dans `utils/ffmpeg_checker` et `utils/resource_monitor`.
- Les chemins de cache des modèles sont configurables via le gestionnaire de configuration.

</details>

## 6. Testing Strategy
- **Unit tests**: cover configuration, database models, and utilities.
- **Integration tests**: exercise transcription pipelines, calendar sync, and schedulers.
- **Performance baseline**: `tests/e2e_performance_test.py` measures throughput for regression tracking.

<details>
<summary>中文</summary>

- **单元测试**：覆盖配置、数据库模型与工具模块。
- **集成测试**：验证转录流水线、日历同步、调度器流程。
- **性能基线**：`tests/e2e_performance_test.py` 评估转录吞吐。

</details>

<details>
<summary>Français</summary>

- **Unitaires** : configuration, modèles de données, utilitaires.
- **Intégration** : pipelines de transcription, synchronisation calendrier, planificateurs.
- **Performance** : `tests/e2e_performance_test.py` mesure le débit pour le suivi des régressions.

</details>

## 7. Maintenance Guidelines
- Follow naming and structure rules from `docs/CODE_STANDARDS.md`.
- When adding new engines, preserve existing interfaces so the core layer remains stable.
- Trim unused assets and noisy logs to keep startup fast and trace files readable.
- Rotate encryption keys periodically and confirm schema versions before release.

<details>
<summary>中文</summary>

- 遵循 `docs/CODE_STANDARDS.md` 中的命名与结构约定。
- 引入新引擎时保持既有接口，避免核心层大幅调整。
- 优先清理冗余资源与噪声日志，确保启动性能与可读性。
- 定期轮换密钥并确认数据库 schema 版本。

</details>

<details>
<summary>Français</summary>

- Suivre les règles de `docs/CODE_STANDARDS.md` pour la structure et la nomenclature.
- Préserver les interfaces existantes lors de l’ajout de nouveaux moteurs afin de stabiliser la couche core.
- Nettoyer les ressources inutilisées et les logs verbeux pour conserver un démarrage rapide et des traces lisibles.
- Faire tourner régulièrement les clés de chiffrement et vérifier la version du schéma avant publication.

</details>

## 8. Future Enhancements
- Introduce more translation adapters with consistent capability detection.
- Expand cross-platform packaging scripts for official releases.
- Provide analytic dashboards to visualise usage patterns and model performance.

<details>
<summary>中文</summary>

- 增加更多翻译引擎的可插拔适配。
- 扩展跨平台打包脚本，提供正式发行版本。
- 构建可视化分析仪表盘，展示使用统计与模型表现。

</details>

<details>
<summary>Français</summary>

- Ajouter de nouveaux adaptateurs de traduction avec détection de capacités homogène.
- Étendre les scripts de packaging multiplateforme pour les releases officielles.
- Fournir des tableaux de bord d’analyse afin de visualiser l’usage et les performances des modèles.

</details>

Contributions that keep the architecture cohesive and secure are always welcome.
