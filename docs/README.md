# EchoNote Documentation

Welcome to the EchoNote documentation! This guide will help you find the information you need.

---

## 🚀 Getting Started

**New to EchoNote?** Start here:

- **[Quick Start Guide](quick-start/README.md)** - Get up and running in minutes
- **[User Guide](user-guide/README.md)** - Complete user documentation (English, 中文, Français)
- **[Project Overview](project-overview/README.md)** - Architecture and design philosophy

---

## 📖 User Documentation

For end users and administrators:

- **[User Guide](user-guide/README.md)** - Complete feature documentation
- **[Quick Start](quick-start/README.md)** - Installation and setup
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions
- **[Google OAuth Setup](GOOGLE_OAUTH_SETUP.md)** - Calendar integration guide

---

## 🛠️ Developer Documentation

For contributors and developers:

- **[Developer Guide](DEVELOPER_GUIDE.md)** - Architecture, setup, and development workflow
- **[API Reference](API_REFERENCE.md)** - Detailed API documentation
- **[Code Standards](CODE_STANDARDS.md)** - Coding conventions and best practices
- **[Contributing Guide](CONTRIBUTING.md)** - How to contribute to the project
- **[CI/CD Guide](CI_CD_GUIDE.md)** - Continuous integration and deployment
- **[Implementation Plans](plans/)** - Active architecture and rollout plans for multi-step feature work
- Unified workspace architecture note: `core/workspace/` is now the single asset layer for imported documents, batch transcriptions, realtime recordings, summaries, and meeting briefs; the desktop entry lives in `ui/workspace/`.
- Workspace interaction note: the `ui/workspace/` page now owns the navigator-shell header actions inside `ui/workspace/library_panel.py`, an Obsidian-style single tree that switches between structure/event modes, the card-based multi-document editor, and detached document windows; the batch transcription/translation queue opens as a shell-level utility window through `ui/main_window.py` + `ui/workspace/task_window.py`, with queue content still rendered by `ui/workspace/task_panel.py`.
- Workspace red-box closure note: the latest implementation track consolidates the screenshot red-box issues into one execution plan covering navigator-shell hard switch, event-folder and batch-task-folder semantics, stable results-list rendering, and inspector transport-player redesign; use `plans/2026-03-15-workspace-redbox-closure-plan.md` as the primary handoff before touching workspace layout code.
- Workspace copy note: shell task-window title and recording-console section labels are now governed by `workspace.task_window_title` and `workspace.recording_console.*` in `resources/translations/*.json`, with `resources/translations/i18n_outline.json` as the outline SSOT.
- Workspace visual polish note: top-bar tool grouping, explorer compact shell, item meta/badges, inspector section titles, and recording-dock summary semantics are all contract-driven by `ui/constants.py`, `resources/themes/theme_outline.json`, and `resources/translations/i18n_outline.json`; theme/i18n/tests/docs are expected to land in the same change.
- Shell recording note: the primary realtime recording entry is now the persistent dock in `ui/common/realtime_recording_dock.py`, with `ui/workspace/recording_session_panel.py` providing the shared full panel and `ui/realtime_record/` reduced to floating overlay and visualization helpers.
- Model governance note: `core/models/manager.py` now governs `speech` / `translation` / `text-ai` catalogs together, with workspace defaults exposed in `ui/settings/workspace_ai_page.py`.
- Settings ownership note: translation defaults are managed in `ui/settings/translation_page.py`, realtime recording controls remain in `ui/settings/realtime_page.py`, and workspace summary/meeting preferences live in `ui/settings/workspace_ai_page.py`.
- Shared playback architecture note: reusable audio playback lives in `ui/common/audio_player.py` and is opened via `ui/common/audio_player_launcher.py`.
- Shared delete-flow note: calendar hub and timeline both use `ui/calendar_event_actions.py` so event deletion copy and workspace cleanup choices stay consistent.
- Shared routing note: timeline and calendar artifact actions now route into `MainWindow.open_workspace_item()` first, switching between structure/event workspace views before focusing transcript/translation/audio assets, so viewing prefers the unified workspace over ad-hoc modal viewers.

---

## 🧭 Active Plans

- **[Workspace Red-Box Closure Plan](plans/2026-03-15-workspace-redbox-closure-plan.md)** - Primary execution plan for the four screenshot issues: left navigator hard switch, Obsidian-aligned structure/event navigation, event-folder and batch-task-folder default placement with persistent source linkage, and inspector transport-player redesign

## ✅ Stable Regression Batches

- `pytest tests/unit/test_main_window_shell.py -v`
- `pytest tests/ui/test_workspace_widget.py -v`
- `pytest tests/unit/test_i18n_outline_contract.py -v`
- `pytest tests/unit/test_theme_outline_contract.py -v`

## 🗃️ Archived Plans

- **[Unified Workspace & Local AI Plan](plans/archive/2026-03-15-unified-workspace-and-local-ai.md)** - Historical hard-switch plan for the first unified recording/document workspace rollout and local AI architecture baseline
- **[Workspace Experience Rearchitecture Plan](plans/archive/2026-03-15-workspace-experience-rearchitecture.md)** - Historical plan for the first workspace shell rebuild; superseded by the Obsidian-alignment follow-up plan
- **[Workspace Gap Closure Plan](plans/archive/2026-03-15-workspace-gap-closure.md)** - Completed follow-up plan for closing the remaining unified workspace gaps after the hard switch
- **[Workspace Polish & Obsidian Alignment Plan](plans/archive/2026-03-15-workspace-polish-and-obsidian-alignment.md)** - Historical follow-up plan for task utility window / recording console / Obsidian-style workspace alignment; superseded by the red-box closure plan
- **[Workspace Visual Density & Layout Polish Plan](plans/archive/2026-03-15-workspace-visual-density-and-layout-polish-plan.md)** - Historical visual polish plan; superseded by the red-box closure plan
- **[Workspace Risk Closure And Polish Plan](plans/archive/2026-03-15-workspace-risk-closure-plan.md)** - Historical risk-closure plan after the first workspace hard switch; superseded by the red-box closure plan

---

## 📋 Project Management

Project status and history:

- **[Project Status](PROJECT_STATUS.md)** - Current status, metrics, and roadmap
- **[Changelog](CHANGELOG.md)** - Version history and release notes
- **[Accessibility](ACCESSIBILITY.md)** - Accessibility guidelines and compliance

---

## 🔧 Specialized Guides

Topic-specific documentation:

- **[Google OAuth Setup](GOOGLE_OAUTH_SETUP.md)** - Setting up Google Calendar integration
- **[Troubleshooting](TROUBLESHOOTING.md)** - Debugging and problem resolution
- **[Accessibility](ACCESSIBILITY.md)** - Making EchoNote accessible to all users

---

## 📚 Documentation by Audience

### For End Users

1. [Quick Start](quick-start/README.md) - Get started quickly
2. [User Guide](user-guide/README.md) - Learn all features

### For Developers

1. [Developer Guide](DEVELOPER_GUIDE.md) - Understand the architecture
2. [Contributing Guide](CONTRIBUTING.md) - Learn the contribution process
3. [Code Standards](CODE_STANDARDS.md) - Follow coding conventions
4. [API Reference](API_REFERENCE.md) - Explore the API

### For Project Managers

1. [Project Status](PROJECT_STATUS.md) - Track progress
2. [Changelog](CHANGELOG.md) - Review changes
3. [CI/CD Guide](CI_CD_GUIDE.md) - Understand deployment

---

## 🌐 Website / Landing Page

- Active implementation: [`echonote-landing/`](../echonote-landing/)
- Development guide: [`echonote-landing/README.md`](../echonote-landing/README.md)
- Deployment guide: [`echonote-landing/DEPLOYMENT.md`](../echonote-landing/DEPLOYMENT.md)
- Archived implementation: [`docs/landing/`](landing/) (historical reference only)
- Current baseline uses a single-page architecture, centralized link composition, i18n locale persistence, and GitHub Pages deployment with auto-resolved base path.

---

## 🌐 Multi-Language Support

EchoNote documentation is available in multiple languages:

- **English** - Primary documentation language
- **中文 (Chinese)** - Available in user guides
- **Français (French)** - Available in user guides

---

## 📞 Getting Help

Need assistance?

1. **Check the documentation** - Most questions are answered here
2. **Search existing issues** - Someone may have had the same problem
3. **Ask in discussions** - Community support
4. **Open an issue** - Report bugs or request features

---

## 🤝 Contributing to Documentation

Documentation improvements are always welcome!

- Found a typo? Submit a PR
- Missing information? Open an issue
- Want to translate? Check the contributing guide

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

**Last Updated**: March 15, 2026
**Version**: v2.1.0
