# EchoNote User Guide

This guide covers the day-to-day workflows, UI navigation, and troubleshooting tips for the EchoNote desktop application.

## 1. Feature Overview
- **Batch Transcription**: Supports MP3/WAV/FLAC/MP4. Queue concurrency is configurable under Settings.
- **Real-time Recording**: Microphone capture with gain control, voice activity detection, live transcription, and optional translation.
- **Calendar Hub**: Local event CRUD, Google/Outlook synchronization, reminders, and account health monitoring.
- **Timeline View**: Explore past and upcoming events, inspect recordings/transcripts, and configure auto-tasks.
- **Settings**: Manage themes, languages, model catalog, storage paths, and security secrets.

<details>
<summary>中文</summary>

- **批量转录**：支持 MP3/WAV/FLAC/MP4 等格式，任务队列与并发控制可在设置中调整。
- **实时录制**：麦克风捕获、语音活动检测、实时转录与可选翻译。
- **日历中心**：本地事件管理、Google/Outlook 同步、提醒与外部账号状态监控。
- **时间线视图**：按时间轴浏览历史与未来事件，查看录音/转录附件，配置自动任务。
- **设置**：主题、语言、模型管理、存储路径、安全密钥等。

</details>

<details>
<summary>Français</summary>

- **Transcription par lots** : prise en charge MP3/WAV/FLAC/MP4. La concurrence de la file se règle depuis les paramètres.
- **Enregistrement temps réel** : capture micro, contrôle du gain, détection d’activité vocale, transcription en direct et traduction optionnelle.
- **Hub calendrier** : CRUD local, synchronisation Google/Outlook, rappels et suivi de l’état des comptes.
- **Vue timeline** : explorer événements passés/à venir, consulter enregistrements/transcriptions, configurer les tâches automatiques.
- **Paramètres** : gérer thèmes, langues, catalogue de modèles, chemins de stockage et secrets de sécurité.

</details>

## 2. First-time Setup <a id="first-time-setup"></a>
<a id="first-launch"></a>
### 2.1 First Launch Checklist
1. Launch the app and follow the wizard to select your interface language, preferred theme, and download a speech model.
2. EchoNote performs dependency checks (FFmpeg, PyAudio) and shows guidance if anything is missing.
3. Wait for initialization to finish (5–10 seconds on the first launch) before exploring other modules.

<details>
<summary>中文</summary>

1. 启动应用并按照向导选择界面语言、主题并下载语音模型。
2. EchoNote 会检查 FFmpeg、PyAudio 等依赖，若缺失会给出指引。
3. 首次启动需要等待约 5-10 秒完成初始化，然后再切换到其他模块。

</details>

<details>
<summary>Français</summary>

1. Lancez l’application puis utilisez l’assistant pour choisir la langue, le thème et télécharger un modèle vocal.
2. EchoNote vérifie les dépendances (FFmpeg, PyAudio) et affiche des conseils en cas de manque.
3. Attendez la fin de l’initialisation (5–10 secondes au premier lancement) avant d’explorer d’autres modules.

</details>

<a id="first-transcription"></a>
### 2.2 Queue Your First Transcription
1. Open **Batch Transcribe** and import an audio/video file or folder.
2. Confirm the chosen model and optional translation language, then start the queue or let auto-run kick in.
3. When the task completes, view or export results as TXT, SRT, or Markdown.

<details>
<summary>中文</summary>

1. 打开 **批量转录** 并导入音频或视频文件/文件夹。
2. 确认模型与可选的翻译语言，点击开始队列或等待自动执行。
3. 任务完成后，可查看或导出 TXT、SRT、Markdown 等格式。

</details>

<details>
<summary>Français</summary>

1. Ouvrez **Batch Transcribe** et importez un fichier ou dossier audio/vidéo.
2. Validez le modèle choisi et la langue de traduction optionnelle puis lancez ou laissez l’auto-exécution démarrer.
3. À la fin, consultez ou exportez en TXT, SRT ou Markdown.

</details>

Configuration is stored at `~/.echonote/app_config.json`, and logs live in `~/.echonote/logs/`.

<details>
<summary>中文</summary>

配置保存在 `~/.echonote/app_config.json`，日志位于 `~/.echonote/logs/`。

</details>

<details>
<summary>Français</summary>

La configuration est enregistrée dans `~/.echonote/app_config.json` et les journaux résident dans `~/.echonote/logs/`.

</details>

## 3. Feature Deep Dive
### 3.1 Batch Transcription <a id="workflow-batch"></a>
- Navigate to **Batch Transcribe** and import files or folders.
- Set per-task model, output format, and translation language as needed.
- The queue supports pause/resume/cancel/retry, and history is searchable inside the same view.
- Confirmation and export dialogs honor the selected language for prompts.
- Desktop completion and failure notifications follow the selected language.

> **Quick path:** `Batch Transcribe → Import File/Folder → Pick model → Start → View/Export`

<details>
<summary>中文</summary>

- 导航栏选择「批量转录」，导入文件或文件夹。
- 可为每个任务指定模型、输出格式、翻译语言。
- 队列支持暂停、继续、取消、重试；历史记录可在同一视图检索。
- 清空确认与导出提示会随界面语言实时更新。
- 批量任务完成或失败时的系统通知会使用当前界面语言。

> **快捷路径：** `批量转录 → 导入文件/文件夹 → 选择模型 → 开始 → 查看/导出`

</details>

<details>
<summary>Français</summary>

- Dans **Batch Transcribe**, importez fichiers ou dossiers.
- Définissez modèle, format de sortie et langue de traduction par tâche.
- La file gère pause/reprise/annulation/réessai et l’historique est consultable dans la même vue.
- Les boîtes de dialogue de confirmation et d’export respectent la langue sélectionnée.
- Les notifications système de fin ou d’échec suivent la langue choisie.

> **Chemin rapide :** `Batch Transcribe → Importer fichier/dossier → Choisir modèle → Démarrer → Consulter/Exporter`

</details>

### 3.2 Real-time Recording <a id="workflow-realtime"></a>
- Choose the input device and gain level; EchoNote automatically applies voice activity detection (VAD) to filter silence. A dedicated toggle under **Settings → Real-time Recording → Voice Activity Detection** is coming soon.
- Monitor live transcripts, tap **Add Marker** to capture timestamps, and track elapsed time.
- When stopping, `stop_recording()` returns the session duration, ISO timestamps, and any markers alongside file paths. Audio
  and transcript exports are saved to `~/Documents/EchoNote/` directories; translations land in the `Translations/` folder when
  generated, and marker metadata is persisted to a JSON file whenever markers exist. When multiple exports finish within the same
  second, EchoNote automatically appends a numeric or millisecond suffix so filenames stay unique.
- When recording ends, the widget surfaces inline feedback and desktop notifications. Successful sessions summarize the elapsed
  time and primary save location, while failures highlight the error so you can retry immediately.
- The capture sample rate inherits from your selected device or an explicit override. Custom rates are applied to the microphone driver before capture; real-time engines auto-resample local models to 16 kHz and forward true rates to cloud APIs.
- The realtime settings page immediately updates export behavior—changing the recording format or toggling auto-save takes effect the next time you start recording without reopening the widget.

> **Quick path:** `Real-time Record → Select microphone → Pick model → Start → Add Marker (optional) → Stop → Export`

- Supported recording formats: WAV (built-in) and MP3. MP3 export requires a
  working FFmpeg installation; when FFmpeg is missing the recorder automatically
  saves as WAV and surfaces a warning.
- Automatic calendar event creation requires a valid database connection. When
  the database is unavailable the recorder logs the issue and skips the calendar
  step without interrupting export.

<details>
<summary>中文</summary>

- 选择音频输入设备与增益值；EchoNote 会自动应用语音活动检测 (VAD) 以减少静音。目前尚无开关，计划在「设置 → 实时录制 → 语音活动检测」中新增（即将推出）。
- 录制过程中可即时查看转录文本，点击**添加标记**记录时间点。
- 停止录制后，`stop_recording()` 会返回录制时长、开始/结束时间以及所有标记；音频与转录会写入 `~/Documents/EchoNote/` 对应目录；启用翻译时会在 `Translations/` 目录写出翻译文本，有标记时会额外生成 JSON 文件保存标记详情；若同一秒内连续导出多次，系统会自动追加序号或毫秒后缀以避免文件名冲突。
- 界面会在停止录制时通过状态提示和系统通知说明结果：成功时展示时长与保存路径，失败时会立即弹出错误提示便于重试。
- 采样率默认沿用所选输入设备，可在录制选项中显式覆盖。自定义值会先应用到麦克风驱动，本地模型自动重采样到 16 kHz，云端接口则携带真实采样率。

> **快捷路径：** `实时录制 → 选择麦克风 → 选择模型 → 开始 → （可选）添加标记 → 停止 → 导出`

- 支持的录音格式：内置 WAV，MP3 需要系统可执行的 FFmpeg。如未检测到 FFmpeg，录制会自动以
  WAV 保存并提示警告。
- 自动创建日历事件需要配置可用的数据库连接；若未配置，系统会记录说明并跳过该步骤，
  不会影响音频与文本导出。
- 「设置 → 实时录制」中的“录音格式 / 自动保存录音”会立即作用于实时录制页面，无需重启应用或重新打开页面。

</details>

<details>
<summary>Français</summary>

- Sélectionnez le périphérique d’entrée et le gain ; EchoNote applique automatiquement la détection d’activité vocale (VAD) pour filtrer les silences. Un interrupteur dédié dans **Paramètres → Enregistrement temps réel → Détection d’activité vocale** arrive bientôt.
- Surveillez la transcription en direct, cliquez sur **Ajouter un marqueur** pour fixer un horodatage, puis suivez le temps écoulé.
- À l’arrêt, `stop_recording()` renvoie la durée de session, les horodatages ISO et les marqueurs collectés. Les enregistrements
  et transcriptions sont stockés dans `~/Documents/EchoNote/`; lorsque la traduction est activée, le texte traduit est écrit dans
  `Translations/`, et si des marqueurs existent un fichier JSON récapitulatif est créé.
- L’interface affiche un message et une notification système à l’arrêt : en cas de succès la durée et l’emplacement principal sont rappelés, sinon l’erreur est signalée immédiatement pour relancer l’enregistrement.
- La fréquence d’échantillonnage suit le périphérique choisi ou une valeur forcée. Les micros sont configurés avant capture, les modèles locaux sont rééchantillonnés à 16 kHz et les API cloud reçoivent la fréquence réelle.

> **Chemin rapide :** `Real-time Record → Choisir micro → Sélectionner modèle → Démarrer → Ajouter un marqueur (optionnel) → Arrêter → Exporter`

- Formats d’enregistrement pris en charge : WAV (nativement) et MP3. L’export
  MP3 nécessite FFmpeg disponible sur le système ; en son absence, l’enregistrement
  est automatiquement conservé en WAV avec un avertissement dans l’application.

</details>

### 3.3 Calendar Hub <a id="workflow-calendar"></a>
- Add Google/Outlook OAuth credentials inside Settings to enable sync.
- Create, edit, and delete events with reminders and recurrence rules.
- Sync status is persisted in the `calendar_sync_status` table and surfaced in the UI.
- When an external calendar deletes an event, EchoNote removes that provider’s link and checks whether other services still reference the entry. The local record stays intact unless the deleted provider originally created it and no other links remain, in which case the event and its attachments are purged together.

<details>
<summary>中文</summary>

- 在设置中添加 Google/Outlook OAuth 凭据以启用同步。
- 创建、编辑、删除事件并配置提醒与重复规则。
- 同步状态写入 `calendar_sync_status` 表并在界面展示。
- 当外部日历删除事件时，系统会先移除该提供商的链接并检查是否仍有其他服务关联。若事件来源不是该提供商，或仍有其他链接存在，则保留本地记录；只有当事件来源与该提供商一致且再无其他关联时，才会连同附件一并清理。

</details>

<details>
<summary>Français</summary>

- Ajoutez les identifiants OAuth Google/Outlook dans Paramètres pour activer la synchro.
- Créez, modifiez et supprimez des événements avec rappels et récurrence.
- L’état de synchronisation est conservé dans la table `calendar_sync_status` et reflété dans l’UI.
- Lorsqu’un calendrier externe supprime un événement, EchoNote conserve l’entrée locale sauf si ce fournisseur était la source initiale et qu’aucun autre lien n’existe ; les pièces jointes ne sont supprimées qu’en cas de suppression complète de l’événement.

</details>

### 3.4 Timeline
- Jump across periods using date pickers; pagination and keyword search cover titles, descriptions, and transcripts.
- Date filters are inclusive; the selected end date covers the entire day.
- If the chosen start date is later than the end date, EchoNote automatically swaps them and notes the correction.
- When a chosen range exceeds your saved window, the timeline automatically expands its fetch span so those events remain visible.
- Timeline preferences update instantly; adjusting the saved day span or page size in Settings refreshes results without closing the view.
- Past events display linked recordings, transcripts, and notes for download or preview.
- Future events allow auto-tasks: auto-record, auto-transcribe, preset languages, and translation targets.
- Changes to the reminder lead time in Settings take effect immediately; the auto task scheduler picks up the updated window without restarting EchoNote.

<details>
<summary>中文</summary>

- 通过日期选择器切换时间段，支持分页与关键词搜索（覆盖标题、描述与转录内容）。
- 日期筛选为包含式区间，终止日期会覆盖当日全部事件。
- 如果起始日期晚于结束日期，EchoNote 会自动对调并记录校正，避免出现反向区间。
- 当选择的日期范围超过偏好设置时，时间线会自动扩大查询窗口，无需手动调整即可覆盖所选日期。
- 修改设置中的时间线天数或分页大小后会即时刷新，无需重新打开页面。
- 历史事件会列出录音、转录、笔记，可预览或下载。
- 未来事件可配置自动录音、自动转录、默认语言与翻译目标。
- 在「设置」中调整提醒提前分钟数会即时生效，自动任务调度器无需重启即可应用新的时间窗口。

</details>

<details>
<summary>Français</summary>

- Naviguez entre les périodes via les sélecteurs de dates ; la recherche par mot-clé couvre les titres, descriptions et transcriptions.
- Si la plage choisie dépasse vos préférences, la timeline agrandit automatiquement la fenêtre de recherche pour inclure ces événements.
- Les préférences de timeline se répercutent immédiatement : modifier l'étendue de jours ou la taille de page dans Paramètres recharge la vue sans la rouvrir.
- Les événements passés affichent enregistrements, transcriptions et notes associés pour prévisualisation ou téléchargement.
- Les événements futurs proposent des tâches automatiques : enregistrement, transcription, langues préconfigurées et cibles de traduction.
- La modification du délai d’alerte dans Paramètres s’applique immédiatement ; le planificateur de tâches automatiques adopte la nouvelle fenêtre sans redémarrer EchoNote.

</details>

### 3.5 Settings Panel <a id="workflow-models"></a>
- **General**: theme, language, shortcuts.
- **Transcription**: default model, concurrency, output formats, translation target.
- **Model Management**: download/verify models, inspect disk usage.
- **Calendar**: external accounts, sync cadence, conflict policies.
- **Security**: database encryption, key rotation, OAuth secrets.

> **Quick path:** `Settings → Model Management → Available Models → Download`

<details>
<summary>中文</summary>

- **通用**：主题、语言、快捷键。
- **转录**：默认模型、并发数、输出格式、翻译目标。
- **模型管理**：下载/校验模型，查看磁盘占用。
- **日历**：外部账号、同步频率、冲突策略。
- **安全**：数据库加密、密钥轮换、OAuth 机密。

> **快捷路径：** `设置 → 模型管理 → 可用模型 → 下载`

</details>

<details>
<summary>Français</summary>

- **Général** : thème, langue, raccourcis.
- **Transcription** : modèle par défaut, concurrence, formats de sortie, langue cible.
- **Gestion des modèles** : télécharger/vérifier les modèles, surveiller l’espace disque.
- **Calendrier** : comptes externes, cadence de synchronisation, politiques de conflit.
- **Sécurité** : chiffrement de la base, rotation des clés, secrets OAuth.

> **Chemin rapide :** `Settings → Model Management → Available Models → Download`

</details>

## 4. Recommended Settings <a id="recommended-settings"></a>
- **Daily use**: model `base`, concurrency 2, device Auto.
- **High quality**: model `medium`/`large`, concurrency 1, device CUDA (if available), compute type `float16`.
- **Fast turnaround**: model `tiny`, concurrency 3–5, compute type `int8`.

<details>
<summary>中文</summary>

- **日常使用**：模型 `base`，并发 2，设备自动。
- **高质量**：模型 `medium`/`large`，并发 1，设备 CUDA（若可用），计算类型 `float16`。
- **快速出稿**：模型 `tiny`，并发 3–5，计算类型 `int8`。

</details>

<details>
<summary>Français</summary>

- **Usage quotidien** : modèle `base`, concurrence 2, périphérique Auto.
- **Haute qualité** : modèle `medium`/`large`, concurrence 1, périphérique CUDA (si dispo), type de calcul `float16`.
- **Retour rapide** : modèle `tiny`, concurrence 3–5, type de calcul `int8`.

</details>

## 5. Troubleshooting Matrix <a id="troubleshooting"></a>
| Symptom | Quick Check | Resolution |
| ------- | ----------- | ---------- |
| Cannot import file | Path accessible? Format supported? | Convert to a supported format or adjust permissions |
| Model validation failed | Model fully downloaded? | Click **Redownload** in Model Management |
| Slow transcription | CPU/GPU saturated? Resource monitor warning? | Switch to a smaller model and review `utils/resource_monitor` alerts |
| Calendar conflicts | Any sync errors in logs? | Re-authorize account or inspect `calendar_sync_status` entries |

- **Transcription failed**: verify file format, ensure the model is downloaded, and confirm sufficient disk space via **Settings → Model Management → Verify model**.
- **Cannot record**: confirm microphone connection, OS permissions, and audio input selection.
- **Calendar not syncing**: remove the account under **Settings → Calendar** and add it again after resolving OAuth prompts.

<details>
<summary>中文</summary>

| 症状 | 快速检查 | 解决方案 |
| ---- | -------- | -------- |
| 无法导入文件 | 路径可访问？格式受支持？ | 转换为受支持格式或检查权限 |
| 模型校验失败 | 模型是否完整下载？ | 在模型管理中点击 **重新下载** |
| 转录速度慢 | CPU/GPU 是否满载？资源监控是否告警？ | 切换到更小的模型，并查看 `utils/resource_monitor` 提示 |
| 日历冲突 | 日志中是否有同步错误？ | 重新授权账号或检查 `calendar_sync_status` 表 |

- **转录失败**：确认文件格式、模型已下载，并通过 **设置 → 模型管理 → 校验模型** 检查磁盘空间。
- **无法录音**：确认麦克风连接、系统权限和音频输入选择。
- **日历不同步**：在 **设置 → 日历** 中移除账户，解决 OAuth 提示后重新添加。

</details>

<details>
<summary>Français</summary>

| Symptôme | Vérification rapide | Résolution |
| -------- | ------------------- | ---------- |
| Impossible d’importer | Chemin accessible ? Format supporté ? | Convertir vers un format supporté ou ajuster les droits |
| Échec validation modèle | Modèle entièrement téléchargé ? | Cliquer sur **Redownload** dans Model Management |
| Transcription lente | CPU/GPU saturé ? Alerte du moniteur de ressources ? | Passer à un modèle plus petit et consulter `utils/resource_monitor` |
| Conflits calendrier | Erreurs de synchro dans les logs ? | Réautoriser le compte ou inspecter `calendar_sync_status` |

- **Échec de transcription** : vérifier le format, confirmer le téléchargement du modèle et l’espace disque via **Settings → Model Management → Verify model**.
- **Impossible d’enregistrer** : contrôler micro, permissions système et sélection d’entrée audio.
- **Synchronisation calendrier** : supprimer le compte sous **Settings → Calendar**, résoudre les invites OAuth puis réajouter.

</details>

## 6. Productivity Tips <a id="productivity-tips"></a>
- Use keyboard shortcuts to switch modules rapidly.
- Configure recurring auto-record policies in `core/timeline/auto_task_scheduler.py` to prepare meetings ahead of time.
- Enable the notification center to receive low-resource and completion alerts.
- Validate hardware setups with the sample assets bundled under `tests/`.

<details>
<summary>中文</summary>

- 使用快捷键快速切换模块。
- 在 `core/timeline/auto_task_scheduler.py` 配置周期性自动录音策略，为会议预先做好准备。
- 启用通知中心，在资源不足或任务完成时获得提醒。
- 利用 `tests/` 中的示例资源验证硬件与环境配置。

</details>

<details>
<summary>Français</summary>

- Utilisez les raccourcis clavier pour changer de module rapidement.
- Configurez des politiques d’enregistrement automatique récurrentes dans `core/timeline/auto_task_scheduler.py` pour préparer les réunions.
- Activez le centre de notifications pour recevoir les alertes de ressources ou de fin de tâche.
- Vérifiez votre matériel à l’aide des échantillons fournis dans `tests/`.

</details>

## 7. Keyboard Shortcuts <a id="keyboard-shortcuts"></a>
| Feature | Shortcut |
| ------- | -------- |
| Batch Transcribe | Ctrl+1 (⌘+1) |
| Real-time Record | Ctrl+2 (⌘+2) |
| Calendar Hub | Ctrl+3 (⌘+3) |
| Timeline | Ctrl+4 (⌘+4) |
| Settings | Ctrl+, (⌘+,) |

<details>
<summary>中文</summary>

| 功能 | 快捷键 |
| ---- | ------- |
| 批量转录 | Ctrl+1 (⌘+1) |
| 实时录制 | Ctrl+2 (⌘+2) |
| 日历中心 | Ctrl+3 (⌘+3) |
| 时间线 | Ctrl+4 (⌘+4) |
| 设置 | Ctrl+, (⌘+,) |

</details>

<details>
<summary>Français</summary>

| Fonction | Raccourci |
| -------- | --------- |
| Transcription par lots | Ctrl+1 (⌘+1) |
| Enregistrement temps réel | Ctrl+2 (⌘+2) |
| Centre calendrier | Ctrl+3 (⌘+3) |
| Timeline | Ctrl+4 (⌘+4) |
| Paramètres | Ctrl+, (⌘+,) |

</details>

## 8. Data Locations <a id="data-locations"></a>
```text
Database: ~/.echonote/data.db
Recordings: ~/Documents/EchoNote/Recordings/
Transcripts: ~/Documents/EchoNote/Transcripts/
Logs: ~/.echonote/logs/echonote.log
```

<details>
<summary>中文</summary>

```text
数据库：~/.echonote/data.db
录音：~/Documents/EchoNote/Recordings/
转录：~/Documents/EchoNote/Transcripts/
日志：~/.echonote/logs/echonote.log
```

</details>

<details>
<summary>Français</summary>

```text
Base de données : ~/.echonote/data.db
Enregistrements : ~/Documents/EchoNote/Recordings/
Transcriptions : ~/Documents/EchoNote/Transcripts/
Journaux : ~/.echonote/logs/echonote.log
```

</details>

## 9. Getting Support <a id="support"></a>
- Review `~/.echonote/logs/echonote.log` for stack traces and diagnostics.
- Read [`../project-overview/README.md`](../project-overview/README.md) for architectural context and data flow diagrams.
- When filing issues, include OS, Python version, model choice, and whether FFmpeg/PyAudio are installed.

<details>
<summary>中文</summary>

- 查看 `~/.echonote/logs/echonote.log` 获取详细堆栈。
- 参考 [`../project-overview/README.md`](../project-overview/README.md) 了解架构与数据流。
- 如需提问，请附上系统信息（操作系统、Python 版本、模型配置及 FFmpeg/PyAudio 状态）。

</details>

<details>
<summary>Français</summary>

- Consultez `~/.echonote/logs/echonote.log` pour diagnostics et traces.
- Lisez [`../project-overview/README.md`](../project-overview/README.md) pour comprendre l’architecture et les flux de données.
- Lors d’une demande d’assistance, incluez l’OS, la version Python, le modèle utilisé et la présence de FFmpeg/PyAudio.

</details>

Enjoy capturing and organizing your conversations!
