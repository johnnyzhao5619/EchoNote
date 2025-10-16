# Démarrage rapide EchoNote

Ce guide vous accompagne du premier lancement à votre première transcription en cinq minutes.

## 1. Premier lancement (≈2 minutes)
1. Double-cliquez sur l'icône EchoNote.
2. Suivez l'assistant :
   - Choisissez la langue d'interface (chinois, anglais ou français).
   - Sélectionnez un thème (clair, sombre ou suivre le système).
   - Téléchargez le modèle recommandé `base` (~145 Mo) via **Télécharger maintenant**.
3. Patientez pendant l'initialisation (5 à 10 secondes lors du premier démarrage).

## 2. Première transcription (≈3 minutes)
1. Importez un fichier audio/vidéo :
   ```text
   Transcription par lots → Importer un fichier → choisir le média
   ```
2. Une fois dans la file, cliquez sur **Démarrer** ou laissez EchoNote lancer la tâche automatiquement.
3. À la fin, sélectionnez **Afficher** ou **Exporter** pour générer des fichiers TXT, SRT ou Markdown.

## Fiches mémo
### Transcription par lots
```text
Transcription par lots → Importer fichier/dossier → Choisir un modèle → Attendre → Afficher/Exporter
```

### Enregistrement en temps réel
```text
Enregistrement temps réel → Choisir micro → Choisir un modèle → Démarrer → Arrêter → Exporter le texte
```

### Connecter Google Agenda
```text
Paramètres → Calendrier → Ajouter un compte Google → Autoriser dans le navigateur → Synchronisation automatique
```

### Télécharger d'autres modèles
```text
Paramètres → Gestion des modèles → Modèles disponibles → Télécharger → Attendre la fin
```

## Réglages recommandés
- **Usage quotidien** : modèle `base`, concurrence 2, périphérique Auto.
- **Haute qualité** : modèle `medium`/`large`, concurrence 1, périphérique CUDA (si disponible), type de calcul `float16`.
- **Rapidité** : modèle `tiny`, concurrence 3–5, type de calcul `int8`.

## Résolution rapide
- **Échec de transcription** : vérifier le format du fichier, la présence du modèle et l'espace disque → Paramètres → Gestion des modèles → Vérifier le modèle.
- **Transcription lente** : Paramètres → Paramètres de transcription → choisir un modèle plus petit.
- **Impossible d'enregistrer** : confirmer micro, permissions système et source audio.
- **Calendrier non synchronisé** : Paramètres → Calendrier → Supprimer le compte → Le reconnecter.

## Raccourcis clavier
| Fonction              | Raccourci       |
| --------------------- | --------------- |
| Transcription par lots| Ctrl+1 (⌘+1)    |
| Enregistrement direct | Ctrl+2 (⌘+2)    |
| Centre calendrier     | Ctrl+3 (⌘+3)    |
| Timeline              | Ctrl+4 (⌘+4)    |
| Paramètres            | Ctrl+, (⌘+,)    |

## Emplacements des données
```text
Base de données : ~/.echonote/data.db
Enregistrements : ~/Documents/EchoNote/Recordings/
Transcriptions : ~/Documents/EchoNote/Transcripts/
Journaux : ~/.echonote/logs/echonote.log
```

Pour plus d'informations, consultez `docs/USER_GUIDE.fr.md`.
