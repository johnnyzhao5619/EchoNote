# EchoNote

Assistant de bureau local-first réunissant transcription, orchestration du calendrier et timeline exploitable.

## Aperçu rapide
- **Cadre** : application PyQt6 démarrée via `main.py`
- **Domaines clés** : transcription par lots/temps réel, synchronisation de calendriers, automatisation des tâches, gestion des paramètres
- **Principes** : confidentialité par défaut, persistance chiffrée, surveillance proactive des ressources

## Points forts
1. **Transcription par lots** – `core/transcription` orchestre les moteurs Faster-Whisper, gère les files redémarrables et l’export multi-format.
2. **Enregistrement temps réel** – `core/realtime` et `engines/audio` assurent la capture, le contrôle de gain, la détection d’activité vocale et la traduction optionnelle.
3. **Hub calendrier** – `core/calendar` gère les événements locaux tandis que `engines/calendar_sync` connecte Google et Outlook.
4. **Automatisation de la timeline** – `core/timeline` relie événements et enregistrements, conserve les règles d’auto-tâches et expose des requêtes historiques.
5. **Stockage sécurisé** – `data/database`, `data/security` et `data/storage` fournissent SQLite chiffré, coffre pour tokens et gestion du cycle de vie des fichiers.
6. **Santé système** – `utils/` centralise journalisation, diagnostics, surveillance des ressources et contrôles FFmpeg.

## Organisation du dépôt
```
EchoNote/
├── main.py                # Démarrage & injection des dépendances
├── config/                # Configuration par défaut et gestionnaire d’exécution
├── core/                  # Gestionnaires métiers (calendar, realtime, timeline, transcription, settings)
├── engines/               # Moteurs modulaires (capture audio, parole, traduction, synchro calendrier)
├── data/                  # Schéma/modèles SQLite, stockage chiffré, gestion de fichiers
├── ui/                    # Widgets Qt, dialogues et coque de navigation
├── utils/                 # Journalisation, i18n, diagnostics, surveillance des ressources
└── tests/                 # Tests unitaires et d’intégration
```

## Prérequis
- Python 3.10 ou supérieur
- Optionnel : PyAudio (capture micro), FFmpeg (formats média), GPU CUDA (accélération)
- Premier lancement : crée base SQLite chiffrée, journaux et paramètres dans `~/.echonote`

## Lancer depuis les sources
```bash
python -m venv .venv
source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Notes de configuration
- Les valeurs par défaut résident dans `config/default_config.json`; les personnalisations sont stockées dans `~/.echonote/app_config.json`.
- Les enregistrements et transcriptions se trouvent par défaut dans `~/Documents/EchoNote/`.
- Fournissez les identifiants OAuth dans l’interface avant d’activer la synchronisation Google ou Outlook.

## Qualité & tests
- `pytest tests/unit` – logique cœur et utilitaires
- `pytest tests/integration` – base de données, moteurs et planificateurs (dépendances locales requises)
- D’autres scénarios E2E et performances sont disponibles dans `tests/`

Installez les dépendances de développement avec `pip install -r requirements-dev.txt` pour étendre la couverture.

## Documentation
- Guide utilisateur : `docs/user-guide/fr.md`
- Démarrage rapide : `docs/quick-start/fr.md`
- Présentation du projet : `docs/project-overview/fr.md`
- Références développeur : `docs/DEVELOPER_GUIDE.md`, `docs/API_REFERENCE.md`

## Licence
Distribué sous [licence MIT](LICENSE).
