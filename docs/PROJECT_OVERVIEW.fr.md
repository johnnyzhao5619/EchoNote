# Présentation du projet EchoNote

## 1. Objectifs de conception
- Offrir une expérience hors ligne pour la transcription et la gestion d'agenda.
- Garder les moteurs modulaires afin de faire évoluer indépendamment reconnaissance, traduction et synchronisation calendrier.
- Garantir sécurité, maintenabilité et performance stables sur desktop.

## 2. Architecture
```
┌───────────┐      ┌──────────┐      ┌───────────┐
│   Interface│ ───▶ │  Noyau  │ ───▶ │  Moteurs  │
└───────────┘      └──────────┘      └───────────┘
        │                 │                   │
        ▼                 ▼                   ▼
    utils/ outils    couche data/       Services externes
```
- **Interface** (`ui/`) : widgets PyQt6, dialogues, notifications et ressources de localisation.
- **Noyau** (`core/`) : gestionnaires métiers orchestrant base de données, moteurs et événements UI.
- **Moteurs** (`engines/`) : implémentations pour capture audio, reconnaissance vocale, traduction et synchronisation calendrier.
- **Données** (`data/`) : modèles SQLite, stockage, chiffrement et accès système de fichiers.
- **Outils** (`utils/`) : journalisation, gestion d'erreurs, surveillance ressources, optimisation du démarrage, i18n.

## 3. Modules clés
| Module | Chemin | Rôle |
| ------ | ------ | ---- |
| Gestionnaire de configuration | `config/app_config.py` | Charger les valeurs par défaut, valider le schéma, persister les préférences |
| Connexion base | `data/database/connection.py` | Accès SQLite chiffré, initialisation du schéma, gestion de version |
| Gestionnaire de modèles | `core/models/manager.py` | Télécharger, vérifier et valider les modèles de voix |
| Gestionnaire de transcription | `core/transcription/manager.py` | Maintenir la file de tâches, piloter le moteur vocal, générer les sorties |
| Enregistreur temps réel | `core/realtime/recorder.py` | Orchestrer capture audio, moteur vocal et traduction |
| Synchronisation calendrier | `core/calendar/manager.py` & `engines/calendar_sync/*` | CRUD local + intégration fournisseurs externes |
| Planificateur auto | `core/timeline/auto_task_scheduler.py` | Programmer en arrière-plan enregistrements/transcriptions selon les événements |

## 4. Données & sécurité
- **Base** : `~/.echonote/data.db` chiffrée par défaut ; clés gérées dans `data/security`.
- **Stockage** : enregistrements et transcriptions dans `~/Documents/EchoNote/`.
- **Secrets** : identifiants OAuth protégés par le gestionnaire de secrets.
- **Logs** : toutes les sous-systèmes écrivent dans `~/.echonote/logs/echonote.log`.

## 5. Gestion des dépendances
- Dépendances runtime : `requirements.txt` ; développement : `requirements-dev.txt`.
- Vérifications FFmpeg et ressources système : `utils/ffmpeg_checker`, `utils/resource_monitor`.
- Les répertoires de cache modèle sont configurables via le gestionnaire de configuration.

## 6. Tests
- **Unitaires** : configuration, modèles base, utilitaires.
- **Intégration** : pipeline de transcription, synchronisation calendrier, planificateurs.
- **Performance** : `tests/e2e_performance_test.py` pour mesurer le débit de transcription.

## 7. Recommandations de maintenance
- Suivre `docs/CODE_STANDARDS.md` pour la structure et les conventions.
- Préserver les interfaces lors de l'ajout de nouveaux moteurs afin d'éviter les régressions côté noyau.
- Nettoyer régulièrement les ressources inutilisées et réduire le bruit des journaux.
- Planifier la rotation des clés de chiffrement et vérifier le schéma avant publication.

## 8. Pistes futures
- Ajouter des adaptateurs de traduction supplémentaires avec détection de capacités.
- Étendre les scripts de packaging multi-plateformes pour des releases officielles.
- Concevoir un tableau de bord analytique pour visualiser l'usage et la performance des modèles.

Merci de contribuer au maintien d'une architecture claire et durable.
