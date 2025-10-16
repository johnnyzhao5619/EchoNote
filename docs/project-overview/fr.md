# Présentation du projet EchoNote

> Pour les informations les plus récentes, consultez la version anglaise [`README.md`](README.md).

## 1. Objectifs de conception
- Offrir une expérience hors-ligne pour la transcription et la gestion d’agenda.
- Garder des moteurs interchangeables afin de faire évoluer parole, traduction et calendriers indépendamment.
- Maintenir un niveau de sécurité, de maintenabilité et de performance adapté au poste de travail.

## 2. Vue d’architecture
```
┌───────────┐      ┌──────────┐      ┌───────────┐
│    UI     │ ───▶ │   Core   │ ───▶ │  Engines  │
└───────────┘      └──────────┘      └───────────┘
        │                 │                   │
        ▼                 ▼                   ▼
     utils/          data/ layer        Services externes
```
- **Couche UI** (`ui/`) : widgets PyQt6, dialogues, notifications et textes localisés.
- **Couche Core** (`core/`) : gestionnaires métier coordonnant base de données, moteurs et UI.
- **Couche Engines** (`engines/`) : implémentations pour capture audio, reconnaissance vocale, traduction et synchronisation calendrier.
- **Couche Données** (`data/`) : schéma SQLite, modèles, chiffrement, stockage et gestion des secrets.
- **Utilitaires** (`utils/`) : journalisation, gestion d’erreurs, surveillance des ressources, optimisation du démarrage, i18n.

## 3. Modules clés
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

## 4. Données & sécurité
- **Base** : `~/.echonote/data.db`, chiffrée si SQLCipher disponible ; clés gérées par `data/security`.
- **Fichiers** : enregistrements et transcriptions stockés dans `~/Documents/EchoNote/` sauf configuration contraire.
- **Secrets** : identifiants OAuth conservés via le gestionnaire sécurisé afin d’éviter toute exposition en clair.
- **Logs** : chaque sous-système écrit dans `~/.echonote/logs/echonote.log` pour un diagnostic unifié.

## 5. Gestion des dépendances
- Dépendances runtime dans `requirements.txt`, dépendances de développement dans `requirements-dev.txt`.
- Vérifications FFmpeg et surveillance des ressources implémentées dans `utils/ffmpeg_checker` et `utils/resource_monitor`.
- Les chemins de cache des modèles sont configurables via le gestionnaire de configuration.

## 6. Stratégie de tests
- **Unitaires** : configuration, modèles de données, utilitaires.
- **Intégration** : pipelines de transcription, synchronisation calendrier, planificateurs.
- **Performance** : `tests/e2e_performance_test.py` mesure le débit pour le suivi des régressions.

## 7. Bonnes pratiques de maintenance
- Suivre les règles de `docs/CODE_STANDARDS.md` pour la structure et la nomenclature.
- Préserver les interfaces existantes lors de l’ajout de nouveaux moteurs afin de stabiliser la couche core.
- Nettoyer les ressources inutilisées et les logs verbeux pour conserver un démarrage rapide et des traces lisibles.
- Faire tourner régulièrement les clés de chiffrement et vérifier la version du schéma avant publication.

## 8. Pistes d’évolution
- Ajouter de nouveaux adaptateurs de traduction avec détection de capacités homogène.
- Étendre les scripts de packaging multiplateforme pour les releases officielles.
- Fournir des tableaux de bord d’analyse afin de visualiser l’usage et les performances des modèles.

Le document sera tenu à jour au fil de l’évolution des modules. Les contributions sont les bienvenues.
