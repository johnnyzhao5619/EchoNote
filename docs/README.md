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
- Settings architecture note: translation defaults are managed in `ui/settings/translation_page.py`, while realtime recording controls remain in `ui/settings/realtime_page.py`.
- Shared playback architecture note: reusable audio playback lives in `ui/common/audio_player.py` and is opened via `ui/common/audio_player_launcher.py`.

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

**Last Updated**: February 17, 2026  
**Version**: v1.4.7
