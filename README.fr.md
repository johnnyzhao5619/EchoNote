# EchoNote

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-2563EB.svg" alt="Apache 2.0 License badge"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-4B5563.svg" alt="Python 3.10+ badge">
  <img src="https://img.shields.io/badge/Desktop-Local%20First-0EA5E9.svg" alt="Desktop local-first badge">
</p>

<p align="center">
  <strong>Application de bureau axée sur la confidentialité pour la transcription vocale intelligente et la gestion de calendrier</strong>
</p>

<p align="center">
  <a href="README.md">English</a> •
  <a href="README.zh-CN.md">中文</a> •
  <a href="README.fr.md">Français</a>
</p>

## 🚀 Démarrage rapide

### Installation et configuration

```bash
# 1. Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Lancer l'application
python main.py
```

### Configuration du premier lancement

1. **Configuration du stockage** : Choisir les chemins pour les enregistrements et transcriptions
2. **Téléchargement de modèle** : Télécharger un modèle Faster-Whisper
   - `tiny` : Le plus rapide, précision faible (~75MB)
   - `base` : Équilibre vitesse/précision (~142MB) - **Recommandé pour la plupart des utilisateurs**
   - `small` : Plus lent, haute précision (~462MB)
   - `medium/large` : Le plus lent, précision maximale (1.5-3GB)
3. **Vérification FFmpeg** : Vérifier l'installation FFmpeg pour le support des formats média
4. **Optionnel** : Configurer la synchronisation calendrier (OAuth Google/Outlook)

## 🎯 Fonctionnalités principales

### 🎙️ Transcription vocale

- **Transcription par lots** : Traiter des fichiers audio/vidéo, support de multiples formats
- **Enregistrement en temps réel** : Transcription vocale en direct avec détection d'activité vocale
- **Export multi-formats** : TXT, SRT, Markdown et autres formats
- **Gestion de modèles** : Modèles Faster-Whisper locaux avec accélération GPU

### 📅 Gestion de calendrier

- **Synchronisation multi-plateformes** : Intégration Google Calendar et Outlook
- **Événements locaux** : Créer et gérer des événements de calendrier locaux
- **Sécurité OAuth** : Connexion sécurisée aux comptes tiers
- **Synchronisation automatique** : Synchronisation périodique en arrière-plan

### ⏰ Intelligence de timeline

- **Corrélation d'événements** : Association automatique des enregistrements avec les événements de calendrier
- **Tâches automatiques** : Enregistrement automatique basé sur les événements de calendrier
- **Requêtes historiques** : Recherche puissante d'événements et d'enregistrements
- **Système de rappels** : Rappels et notifications intelligents

### 🔒 Confidentialité et sécurité

- **Local d'abord** : Toutes les données stockées localement
- **Stockage chiffré** : Chiffrement au niveau application de la base SQLite
- **Jetons sécurisés** : Gestion sécurisée des jetons OAuth
- **Aucune dépendance cloud** : Utilisation entièrement hors ligne possible

## 📋 Exigences système

- **Python** : 3.10 ou plus récent
- **Système d'exploitation** : macOS, Linux, Windows
- **Dépendances optionnelles** :
  - PyAudio (capture microphone)
  - FFmpeg (support formats média)
  - GPU CUDA (accélération Faster-Whisper)

## 🏗️ Architecture du projet

```
EchoNote/
├── main.py                # Point d'entrée de l'application
├── config/                # Gestion de configuration et contrôle de version
│   ├── __version__.py     # Définition de version (source unique)
│   ├── app_config.py      # Gestionnaire de configuration
│   └── default_config.json # Configuration par défaut
├── core/                  # Logique métier principale
│   ├── transcription/     # Gestion de transcription
│   ├── realtime/          # Enregistrement en temps réel
│   ├── calendar/          # Gestion de calendrier
│   ├── timeline/          # Intelligence de timeline
│   ├── settings/          # Gestion des paramètres
│   └── models/            # Gestion de modèles
├── engines/               # Intégrations de services externes
│   ├── speech/            # Moteurs de reconnaissance vocale
│   ├── audio/             # Capture audio
│   ├── translation/       # Services de traduction
│   └── calendar_sync/     # Synchronisation de calendrier
├── data/                  # Couche de données
│   ├── database/          # Modèles de base de données
│   ├── security/          # Sécurité et chiffrement
│   └── storage/           # Gestion de fichiers
├── ui/                    # Interface utilisateur PySide6
│   ├── main_window.py     # Fenêtre principale
│   ├── sidebar.py         # Barre latérale
│   ├── batch_transcribe/  # Interface de transcription par lots
│   ├── realtime_record/   # Interface d'enregistrement en temps réel
│   ├── calendar_hub/      # Interface du centre de calendrier
│   ├── timeline/          # Interface de timeline
│   ├── settings/          # Interface des paramètres
│   └── common/            # Composants communs
├── utils/                 # Outils et utilitaires
│   ├── logger.py          # Système de journalisation
│   ├── i18n.py            # Internationalisation
│   ├── error_handler.py   # Gestion d'erreurs
│   └── qt_async.py        # Pont Qt asynchrone
├── scripts/               # Outils de script
│   ├── sync_version.py    # Synchronisation de version
│   └── bump_version.py    # Mise à jour de version
└── tests/                 # Suite de tests
    ├── unit/              # Tests unitaires
    ├── integration/       # Tests d'intégration
    └── fixtures/          # Données de test
```

## 📚 Ressources de documentation

| Audience                  | Ressource                 | Emplacement                                                |
| ------------------------- | ------------------------- | ---------------------------------------------------------- |
| **Nouveaux utilisateurs** | Guide de démarrage rapide | [`docs/quick-start/README.md`](docs/quick-start/README.md) |
| **Utilisateurs finaux**   | Manuel utilisateur        | [`docs/user-guide/README.md`](docs/user-guide/README.md)   |
| **Développeurs**          | Guide développeur         | [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md)       |
| **Développeurs**          | Référence API             | [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md)           |
| **Contributeurs**         | Standards de codage       | [`docs/CODE_STANDARDS.md`](docs/CODE_STANDARDS.md)         |
| **Contributeurs**         | Guide de contribution     | [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md)             |
| **Mainteneurs**           | Gestion des versions      | [`docs/VERSION_MANAGEMENT.md`](docs/VERSION_MANAGEMENT.md) |
| **Tous**                  | Statut du projet          | [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)         |

## 🧪 Développement et tests

### Configuration de l'environnement de développement

```bash
# Installer les dépendances de développement
pip install -r requirements-dev.txt

# Installer les hooks de pré-commit
pre-commit install
```

### Exécution des tests

```bash
# Tests unitaires
pytest tests/unit

# Tests d'intégration
pytest tests/integration

# Tests de performance
pytest tests/e2e_performance_test.py

# Couverture de tests
pytest --cov=core --cov=engines --cov=data --cov=ui --cov=utils --cov-report=term-missing
```

### Vérifications de qualité du code

```bash
# Vérification de cohérence des versions
python scripts/sync_version.py

# Formatage du code
black .
isort .

# Vérification du code
flake8
mypy

# Vérification de sécurité
bandit -c pyproject.toml

# Exécuter toutes les vérifications de pré-commit
pre-commit run --all-files
```

### Gestion des versions

```bash
# Vérifier la version actuelle
python -c "from config import get_version; print(get_version())"

# Mettre à jour la version (aperçu)
python scripts/bump_version.py patch --dry-run

# Mettre à jour la version (réel)
python scripts/bump_version.py patch
```

## 🔧 Explication de la configuration

### Emplacements des fichiers de configuration

- **Configuration par défaut** : `config/default_config.json`
- **Configuration utilisateur** : `~/.echonote/app_config.json`
- **Données utilisateur** : `~/.echonote/`

### Éléments de configuration principaux

```json
{
  "transcription": {
    "default_engine": "faster-whisper",
    "default_output_format": "txt",
    "max_concurrent_tasks": 2
  },
  "realtime": {
    "auto_save": true,
    "vad_threshold": 0.5
  },
  "calendar": {
    "sync_interval_minutes": 15
  },
  "ui": {
    "theme": "light",
    "language": "fr_FR"
  }
}
```

## 🌍 Support d'internationalisation

EchoNote prend en charge les interfaces multilingues :

- **Français** : `fr_FR`
- **Anglais** : `en_US`
- **Chinois (Simplifié)** : `zh_CN`

Les fichiers de langue se trouvent dans le répertoire `resources/translations/`.

## 🚨 Dépannage

### Problèmes courants

1. **Échec du téléchargement de modèle**

   - Vérifier la connexion réseau
   - S'assurer d'avoir suffisamment d'espace disque
   - Consulter les fichiers de log : `~/.echonote/logs/`

2. **Problèmes de capture audio**

   - Installer PyAudio : `pip install PyAudio`
   - Vérifier les permissions du microphone
   - Valider les périphériques audio

3. **Problèmes liés à FFmpeg**

   - Installer FFmpeg : visiter https://ffmpeg.org/
   - S'assurer que FFmpeg est dans le PATH système
   - Vérifier l'installation : `ffmpeg -version`

4. **Problèmes de synchronisation de calendrier**
   - Vérifier la configuration OAuth
   - Valider la connexion réseau
   - Consulter les logs de synchronisation

### Journalisation et débogage

```bash
# Activer les logs de débogage
ECHO_NOTE_LOG_LEVEL=DEBUG python main.py

# Emplacement des fichiers de log
~/.echonote/logs/app.log
```

## 📄 Licence

Ce projet est publié sous la [Licence Apache 2.0](LICENSE).

### Licences tierces

- **PySide6** (LGPL v3) : Framework UI, utilisé via liaison dynamique, entièrement compatible avec Apache 2.0
- **Faster-Whisper** (MIT) : Moteur de reconnaissance vocale
- **Autres dépendances** : Voir [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)

## 🤝 Contribution

Nous accueillons les contributions ! Veuillez consulter notre [Guide de contribution](docs/CONTRIBUTING.md) pour les détails sur :

- Standards de code et guide de style
- Flux de travail de développement
- Exigences de test
- Directives de documentation

## 📞 Support

- **Documentation** : Répertoire [`docs/`](docs/)
- **Signalement de problèmes** : [GitHub Issues](https://github.com/your-org/echonote/issues)
- **Discussions** : [GitHub Discussions](https://github.com/your-org/echonote/discussions)

## 📊 Statut du projet

- **Version** : v1.2.0 (Dernière version de maintenance)
- **Couverture de tests** : 607 tests, 100% de réussite
- **Qualité du code** : Excellente (conforme PEP 8, annotations de type complètes)
- **Documentation** : Complète et restructurée
- **Licence** : Apache 2.0 (entièrement conforme)

---

<p align="center">
  Fait avec ❤️ par l'équipe EchoNote
</p>
