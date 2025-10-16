# Guide utilisateur EchoNote

Ce manuel décrit les flux quotidiens, la navigation dans l'interface et les solutions aux problèmes courants de l'application de bureau EchoNote.

## 1. Vue d'ensemble
- **Transcription par lots** : support MP3/WAV/FLAC/MP4, contrôle de la concurrence dans les Paramètres.
- **Enregistrement temps réel** : capture micro avec réglage du gain, détection d'activité vocale, transcription en direct et traduction optionnelle.
- **Centre calendrier** : gestion locale des événements, synchronisation Google/Outlook, rappels et suivi de l'état des comptes.
- **Vue timeline** : parcourir événements passés et futurs, consulter enregistrements/transcriptions, configurer des tâches automatiques.
- **Paramètres** : thèmes, langues, catalogue de modèles, emplacements de stockage, secrets de sécurité.

## 2. Première configuration <a id="first-time-setup"></a>
<a id="first-launch"></a>
### 2.1 Liste de vérification du premier lancement
1. Lancez l'application et suivez l'assistant pour choisir la langue de l'interface, le thème et télécharger un modèle vocal.
2. EchoNote vérifie les dépendances (FFmpeg, PyAudio) et affiche des instructions si une étape échoue.
3. Patientez 5 à 10 secondes lors du tout premier démarrage avant de passer à d'autres modules.

<a id="first-transcription"></a>
### 2.2 Lancer votre première transcription
1. Ouvrez **Transcription par lots** puis importez un fichier ou un dossier audio/vidéo.
2. Validez le modèle choisi et la langue de traduction éventuelle, puis démarrez la file ou laissez l'exécution automatique commencer.
3. Une fois la tâche terminée, consultez ou exportez le résultat en TXT, SRT ou Markdown.

La configuration est enregistrée dans `~/.echonote/app_config.json` et les journaux dans `~/.echonote/logs/`.

## 3. Fonctionnalités en détail
### 3.1 Transcription par lots <a id="workflow-batch"></a>
- Ouvrez **Transcription par lots** puis importez fichiers ou dossiers.
- Définissez, si besoin, modèle, format de sortie et langue de traduction par tâche.
- La file permet pause/reprise/annulation/relance ; l'historique est consultable dans la même vue.

> **Raccourci opérationnel :** `Transcription par lots → Importer fichier/dossier → Choisir modèle → Démarrer → Consulter/Exporter`

### 3.2 Enregistrement temps réel <a id="workflow-realtime"></a>
- Choisissez périphérique d'entrée et niveau de gain ; activez la VAD pour réduire les silences.
- Surveillez la transcription en direct, ajoutez des marqueurs et vérifiez la durée.
- À l'arrêt, enregistrements et transcriptions sont sauvegardés dans `~/Documents/EchoNote/`.

> **Raccourci opérationnel :** `Enregistrement temps réel → Sélectionner micro → Choisir modèle → Démarrer → Arrêter → Exporter`

### 3.3 Centre calendrier <a id="workflow-calendar"></a>
- Ajoutez des identifiants OAuth Google/Outlook dans Paramètres pour activer la synchronisation.
- Créez, modifiez, supprimez des événements avec rappels et règles de récurrence.
- L'état de synchronisation est conservé dans la table `calendar_sync_status` et visible depuis l'interface.

### 3.4 Timeline
- Naviguez via les sélecteurs de dates ; pagination et recherche par mot-clé sont disponibles.
- Les événements passés affichent enregistrements, transcriptions et notes à télécharger ou prévisualiser.
- Les événements futurs autorisent les tâches automatiques : auto-enregistrement, auto-transcription, langues et cibles de traduction prédéfinies.

### 3.5 Panneau Paramètres <a id="workflow-models"></a>
- **Général** : thème, langue, raccourcis.
- **Transcription** : modèle par défaut, concurrence, formats de sortie, langue de traduction.
- **Gestion des modèles** : télécharger/vérifier les modèles, surveiller l'espace disque.
- **Calendrier** : comptes externes, fréquence de synchronisation, résolution de conflits.
- **Sécurité** : chiffrement de la base, rotation des clés, secrets OAuth.

> **Raccourci opérationnel :** `Paramètres → Gestion des modèles → Modèles disponibles → Télécharger`

## 4. Paramètres recommandés <a id="recommended-settings"></a>
- **Usage quotidien** : modèle `base`, concurrence 2, périphérique Automatique.
- **Haute qualité** : modèle `medium`/`large`, concurrence 1, périphérique CUDA (si disponible), type de calcul `float16`.
- **Traitement rapide** : modèle `tiny`, concurrence 3–5, type de calcul `int8`.

## 5. Dépannage <a id="troubleshooting"></a>
| Symptôme | Vérification rapide | Résolution |
| -------- | ------------------- | ---------- |
| Impossible d'importer | Chemin accessible ? Format supporté ? | Convertir vers un format pris en charge ou ajuster les permissions |
| Validation de modèle échouée | Modèle entièrement téléchargé ? | Cliquer sur **Retélécharger** dans Gestion des modèles |
| Transcription lente | CPU/GPU saturés ? Alerte du moniteur de ressources ? | Choisir un modèle plus léger et consulter `utils/resource_monitor` |
| Conflits calendrier | Erreurs de synchronisation dans les journaux ? | Réautoriser le compte ou inspecter `calendar_sync_status` |

- **Transcription en échec** : vérifiez le format du fichier, la présence du modèle téléchargé et l'espace disque libre via **Paramètres → Gestion des modèles → Vérifier le modèle**.
- **Impossible d'enregistrer** : contrôlez la connexion du micro, les permissions système et la source audio sélectionnée.
- **Synchronisation bloquée** : supprimez le compte dans **Paramètres → Calendrier**, puis reconnectez-le après avoir validé l'autorisation OAuth.

## 6. Astuces productivité
- Utilisez les raccourcis clavier (voir [Raccourcis clavier](#keyboard-shortcuts)) pour changer de module rapidement.
- Préparez les enregistrements récurrents via `core/timeline/auto_task_scheduler.py`.
- Activez le centre de notifications pour recevoir alertes de ressources et fins de tâches.
- Vérifiez votre matériel avec les échantillons disponibles dans `tests/`.

## 7. Raccourcis clavier <a id="keyboard-shortcuts"></a>
| Fonction         | Raccourci       |
| ---------------- | --------------- |
| Transcription par lots | Ctrl+1 (⌘+1) |
| Enregistrement temps réel | Ctrl+2 (⌘+2) |
| Centre calendrier | Ctrl+3 (⌘+3) |
| Timeline | Ctrl+4 (⌘+4) |
| Paramètres | Ctrl+, (⌘+,) |

## 8. Emplacements des données <a id="data-locations"></a>
```text
Base de données : ~/.echonote/data.db
Enregistrements : ~/Documents/EchoNote/Recordings/
Transcriptions : ~/Documents/EchoNote/Transcripts/
Journaux : ~/.echonote/logs/echonote.log
```

## 9. Support <a id="support"></a>
- Consultez `~/.echonote/logs/echonote.log` pour diagnostics et traces.
- Lisez `../project-overview/fr.md` pour comprendre l'architecture et les flux de données.
- Lors d'une demande d'assistance, incluez l'OS, la version Python, le modèle utilisé et la présence de FFmpeg/PyAudio.

Bonne organisation de vos conversations !
