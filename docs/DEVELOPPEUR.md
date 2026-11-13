# pawz — Documentation développeur

## Architecture
- `core/models.py` : modèle typé, validation, priorité global → application → domaine le plus spécifique.
- `core/controllers.py` : découverte SDL GameController, lecture sur un thread dédié à 250 Hz (20 Hz sans manette), exécution des effets du moteur de gestes, déplacement et défilement.
- `engine/gestures.py` : règles des gestes (clic maintenu, combinaisons, appui long, capture), pures et testées en table.
- `infra/windows.py` : couche Windows (injection clavier/souris, magnétisme des zones d'interaction, processus actif).
- `engine/actions.py` : catalogue des actions (identifiant, libellé, effet) et interface `OutputSink` ; ajouter une action se fait en une seule entrée. `infra/windows.py` fournit `WindowsOutput`, la sortie réelle ; le `ControllerManager` la reçoit en paramètre, les tests lui passent une sortie factice.
- `infra/window_targets.py` : cibles magnétiques lues dans Windows (lignes de redimensionnement et boutons de titre par hit-test, icônes du bureau), sondées sur un fil secondaire.
- `infra/browser.py` : serveur HTTP loopback authentifié par jeton, état URL avec expiration de 5 s.
- `infra/storage.py` : persistance JSON atomique, `%APPDATA%\pawz\settings.json`.
- `infra/startup.py` : inscription/suppression de l’application dans la clé de démarrage Windows de l’utilisateur.
- `ui/windows.py` : fenêtres Qt, édition de profils, sélecteurs de manettes, icône de notification.
- `main.py` : composition des composants et cycle de vie.
- `browser-extension/` : extension MV3 Brave / Firefox (chargement temporaire sur Firefox).

## Démarrage développement
`powershell -ExecutionPolicy Bypass -File scripts\run-windows.ps1`

## Tests
`python -m pip install -e '.[test]'` puis `python -m pytest`.

## Build
`powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1`

Le build PyInstaller doit être exécuté **sur Windows**, car PyInstaller ne produit pas de binaire Windows depuis Linux. Il construit `dist\pawz\pawz.exe` et copie documentation, exemples et extension. La distribution est de type `onedir` (ne déplacez pas uniquement le `.exe`).

## Configuration
Schéma `schema_version=2`, avec sauvegarde et migration depuis v1. `profiles` associe un nom à ses règles ; `assignments` associe un identifiant enregistré de périphérique au nom du profil. Les anciennes clés `GUID#occurrence` restent lisibles. `known_devices` mémorise les manettes découvertes. `browser_token` est généré au premier lancement. Ne pas publier le fichier utilisateur contenant ce jeton.

## Sécurité / limites techniques
- Aucune commande shell arbitraire depuis un raccourci ; `key_combo` n'accepte que les touches autorisées.
- API HTTP accessible uniquement sur `127.0.0.1`, protégée par jeton, taille de requête limitée.
- L'extension reçoit l'URL complète de l'onglet actif, envoyée localement ; seul le domaine est utilisé pour le routage. Les URL ne sont pas persistées.
- Identité des manettes : instance SDL pendant la connexion et identifiant enregistré distinct. Sans numéro de série accessible, deux appareils identiques restent ambigus après reconnexion. Voir les garanties et limites dans `CONTROLLER_ARCHITECTURE.md`.
- Le clavier virtuel dépend de UI Automation ; la détection de texte web n'est pas exhaustive.
- Les mappings SDL varient selon le contrôleur et le pilote. Les axes utilisés sont `LEFTX`, `LEFTY`, `RIGHTY` (indices 0,1,3).
- L'application n'est pas un service Windows et ne fonctionne pas sur l'écran de connexion ou les fenêtres sécurisées UAC.

## Évolutions recommandées
Introduire un adaptateur d'identité matériel stable, un navigateur de processus Windows basé sur les applications installées, un pont navigateur par fenêtre, un moteur de règles avec modificateurs/chords et une CI Windows qui publie les artefacts signés.
# Architecture des contrôleurs et validation

La [documentation de l’intégration des contrôleurs](CONTROLLER_ARCHITECTURE.md) décrit les entrées SDL2, les modèles de présentation, la persistance v2, les migrations et les tests visuels. Les [attributions des ressources](ASSETS.md) précisent les choix de redistribution.

## Diagnostiquer le magnétisme
Définir `PAWZ_MAGNET_TRACE` avec un chemin de fichier avant de lancer pawz (par exemple `$env:PAWZ_MAGNET_TRACE = "$env:TEMP\pawz-magnet.jsonl"` puis `scripts\run-windows.ps1`). Chaque déplacement magnétisé y est écrit en JSON, une ligne par tick : position, mouvement demandé, cibles vues et retenues, saut éventuel et position relue après le saut, pas réellement envoyé. La première ligne décrit l'environnement (mode DPI du fil, vitesse et accélération du pointeur). Le fichier est limité à 20 000 lignes et ne contient aucune frappe clavier. Sans la variable, rien n'est écrit.
