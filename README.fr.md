# EchoNote

Assistant de bureau local-first qui réunit transcription vocale, orchestration du calendrier et automatisation de la frise chronologique.

## Aperçu du projet
- **Cadre** : application PyQt6 démarrée via `main.py`
- **Domaines fonctionnels** : transcription lot/temps réel, synchronisation de calendriers, planification sur ligne du temps
- **Principes** : confidentialité par défaut, persistance chiffrée, surveillance préventive des ressources

### Points forts
1. **Transcription par lots** – `core/transcription` et les moteurs Faster-Whisper gèrent files audio/vidéo, chargement paresseux des modèles et reprise des tâches.
2. **Enregistrement temps réel** – `core/realtime` s'appuie sur `engines/audio` pour la capture, le contrôle de gain, la détection d'activité vocale et la traduction optionnelle.
3. **Centre calendrier** – `core/calendar` stocke les événements locaux tandis que `engines/calendar_sync` se connecte à Google et Outlook.
4. **Automatisation de la timeline** – `core/timeline` lie événements et enregistrements, pilote les tâches automatiques et alimente les requêtes temporelles.
5. **Sécurité & configuration** – `config/app_config.py` et `data/security` assurent validation, chiffrement et gestion des secrets.
6. **Santé du système** – `utils/resource_monitor` et `utils/ffmpeg_checker` préviennent la pression mémoire et l'absence de dépendances.

### Organisation du dépôt
```
EchoNote/
├── main.py                # Démarrage de l'application et injection des dépendances
├── core/                  # Gestionnaires métiers (calendar, realtime, timeline, transcription)
├── engines/               # Moteurs modulaires (audio, speech, translation, calendar_sync)
├── data/                  # Modèles, stockage et sécurité
├── ui/                    # Widgets Qt, dialogues et navigation
├── utils/                 # Journalisation, i18n, surveillance des ressources, gestion d'erreurs
└── tests/                 # Suites unitaires, intégration et performance
```

## Pré-requis
- Python 3.10 ou supérieur
- Optionnel : PyAudio (capture micro), FFmpeg (formats vidéo), GPU CUDA (accélération)
- Le premier lancement crée les paramètres, journaux et base SQLite chiffrée dans `~/.echonote`

## Lancer depuis les sources
```bash
python -m venv .venv
source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Les valeurs par défaut résident dans `config/default_config.json` et les personnalisations utilisateurs sont persistées dans `~/.echonote/app_config.json`.

## Qualité & tests
- `pytest tests/unit` – couverture unitaire des gestionnaires et utilitaires
- `pytest tests/integration` – vérifications d'intégration pour base de données, moteurs et planificateurs (dépendances locales requises)
- `pytest tests/e2e_performance_test.py` – référence optionnelle pour le débit de transcription

Installez les dépendances de développement via `pip install -r requirements-dev.txt` et préparez périphériques audio ou identifiants calendriers avant d'exécuter les scénarios d'intégration.

## Documentation
- Guide utilisateur : `docs/user-guide/fr.md`
- Démarrage rapide : `docs/quick-start/fr.md`
- Présentation du projet : `docs/project-overview/fr.md`
- Références développeur : `docs/DEVELOPER_GUIDE.md`, `docs/API_REFERENCE.md`

Consultez `docs/README.md` pour l'index complet.

## Licence
Distribué sous [licence MIT](LICENSE).
