# Guide utilisateur EchoNote

Ce manuel décrit les flux quotidiens, la navigation dans l'interface et les solutions aux problèmes courants de l'application de bureau EchoNote.

## 1. Vue d'ensemble
- **Transcription par lots** : support MP3/WAV/FLAC/MP4, contrôle de la concurrence dans les Paramètres.
- **Enregistrement temps réel** : capture micro avec réglage du gain, détection d'activité vocale, transcription en direct et traduction optionnelle.
- **Centre calendrier** : gestion locale des événements, synchronisation Google/Outlook, rappels et suivi de l'état des comptes.
- **Vue timeline** : parcourir événements passés et futurs, consulter enregistrements/transcriptions, configurer des tâches automatiques.
- **Paramètres** : thèmes, langues, catalogue de modèles, emplacements de stockage, secrets de sécurité.

## 2. Première configuration
1. Lancez l'application, choisissez la langue, le thème et téléchargez un modèle vocal via l'assistant.
2. EchoNote vérifie les dépendances (FFmpeg, PyAudio) et affiche des instructions si elles manquent.
3. La configuration est enregistrée dans `~/.echonote/app_config.json` et les journaux dans `~/.echonote/logs/`.

## 3. Fonctionnalités en détail
### 3.1 Transcription par lots
- Ouvrez **Transcription par lots** puis importez fichiers ou dossiers.
- Définissez, si besoin, modèle, format de sortie et langue de traduction par tâche.
- La file permet pause/reprise/annulation/relance ; l'historique est consultable dans la même vue.

### 3.2 Enregistrement temps réel
- Choisissez périphérique d'entrée et niveau de gain ; activez la VAD pour réduire les silences.
- Surveillez la transcription en direct, ajoutez des marqueurs et vérifiez la durée.
- À l'arrêt, enregistrements et transcriptions sont sauvegardés dans `~/Documents/EchoNote/`.

### 3.3 Centre calendrier
- Ajoutez des identifiants OAuth Google/Outlook dans Paramètres pour activer la synchronisation.
- Créez, modifiez, supprimez des événements avec rappels et règles de récurrence.
- L'état de synchronisation est conservé dans la table `calendar_sync_status` et visible depuis l'interface.

### 3.4 Timeline
- Naviguez via les sélecteurs de dates ; pagination et recherche par mot-clé sont disponibles.
- Les événements passés affichent enregistrements, transcriptions et notes à télécharger ou prévisualiser.
- Les événements futurs autorisent les tâches automatiques : auto-enregistrement, auto-transcription, langues et cibles de traduction prédéfinies.

### 3.5 Panneau Paramètres
- **Général** : thème, langue, raccourcis.
- **Transcription** : modèle par défaut, concurrence, formats de sortie, langue de traduction.
- **Gestion des modèles** : télécharger/vérifier les modèles, surveiller l'espace disque.
- **Calendrier** : comptes externes, fréquence de synchronisation, résolution de conflits.
- **Sécurité** : chiffrement de la base, rotation des clés, secrets OAuth.

## 4. Dépannage
| Symptôme | Vérification rapide | Résolution |
| -------- | ------------------- | ---------- |
| Impossible d'importer | Chemin accessible ? Format supporté ? | Convertir vers un format pris en charge ou ajuster les permissions |
| Validation de modèle échouée | Modèle entièrement téléchargé ? | Cliquer sur **Retélécharger** dans Gestion des modèles |
| Transcription lente | CPU/GPU saturés ? Alerte du moniteur de ressources ? | Choisir un modèle plus léger et consulter `utils/resource_monitor` |
| Conflits calendrier | Erreurs de synchronisation dans les journaux ? | Réautoriser le compte ou inspecter `calendar_sync_status` |

## 5. Astuces productivité
- Utilisez les raccourcis clavier (voir Démarrage rapide) pour changer de module rapidement.
- Préparez les enregistrements récurrents via `core/timeline/auto_task_scheduler.py`.
- Activez le centre de notifications pour recevoir alertes de ressources et fins de tâches.
- Vérifiez votre matériel avec les échantillons disponibles dans `tests/`.

## 6. Support
- Consultez `~/.echonote/logs/echonote.log` pour diagnostics et traces.
- Lisez `../project-overview/fr.md` pour comprendre l'architecture et les flux de données.
- Lors d'une demande d'assistance, incluez l'OS, la version Python, le modèle utilisé et la présence de FFmpeg/PyAudio.

Bonne organisation de vos conversations !
