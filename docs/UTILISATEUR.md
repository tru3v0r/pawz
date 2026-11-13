# pawz — Guide utilisateur

## Prérequis
- Windows 10 ou 11 (64 bits), Python 3.12 pour lancer ou produire l'exécutable.
- Manette compatible **SDL GameController** connectée en USB ou Bluetooth (Nintendo Pro Controller selon le pilote et la configuration SDL).

## Installation
1. Récupérer le dépôt (`git clone`, ou `git pull` pour le mettre à jour).
2. Dans PowerShell à la racine : `powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1`.
3. Lancer `dist\pawz\pawz.exe`. Le dossier `dist\pawz` est **portable** : conservez l'ensemble des fichiers à côté de l'exécutable.
4. Le programme reste actif dans la zone de notification ; double-cliquez sur son icône pour ouvrir la configuration. Le menu « Quitter » l'arrête.
- La police Inter est incluse. Pour afficher le titre avec Super Water, cette police doit être installée dans Windows.

## Configuration
- Les emplacements affichent les manettes connectées et les manettes déjà connues mais déconnectées.
- Le bouton « Oublier » sous une manette déconnectée supprime son nom mémorisé et son attribution de profil ; une confirmation est demandée.
- Seules les manettes connectées ou déjà connues sont affichées. Si leur nombre dépasse la largeur disponible, utilisez les flèches latérales pour parcourir la liste.
- La couronne indique la manette principale (administratrice). Avec une seule manette connectée, elle devient principale automatiquement. Avec plusieurs manettes, cliquez sur « SET PRIMARY » sous celle qui doit devenir principale.
- Le niveau de batterie et le profil associé sont affichés sous chaque manette connectée. Les valeurs de batterie marquées `~` sont des estimations : SDL ne fournit qu'un niveau approximatif (faible, moyen, plein), pas un pourcentage précis.
- Le profil intégré est « Default » ; l’option « By default » et l’ancien profil intégré « Invité 1 » ne sont plus proposés. Les profils supplémentaires restent disponibles si vous en créez. Les anciennes configurations sont migrées vers « Default », avec leurs attributions réaffectées.
- « Manage profiles » ouvre l’onglet « Profils » de « Settings », où les profils peuvent être modifiés ou créés.
- Dans « Settings » → « Général », « Profil assigné par défaut » choisit le profil utilisé par les manettes sans attribution particulière. Le sélecteur d’une manette permet de choisir un profil spécifique ; choisir le profil actuellement défini par défaut efface son attribution particulière.
- Survolez la couronne pour afficher l’étiquette « Primary Controller ».
- Par défaut, les flèches du pavé directionnel de la manette envoient les flèches haut, bas, gauche et droite du clavier.
- Les boutons de face sont désignés par leur position : celui de droite fait le clic gauche, celui du bas le clic droit, celui du haut copie et celui de gauche colle. L'appui sur le stick droit effectue le clic molette.
- Dans « Profils », cliquez sur une touche affichée pour commencer la capture. Appuyez simultanément sur un ou plusieurs boutons de manette ; la combinaison est ajoutée au profil lorsque l’un des boutons est relâché, puis appliquée seulement après « Enregistrer ».
- Dans « Sensibilité », la ligne « Magnétisme » règle la force de 10 à 100 %. Le magnétisme attire le pointeur vers les bords redimensionnables des fenêtres, vers leurs boutons (réduire, agrandir, fermer) et vers les icônes du bureau. En approchant d'une cible, le pointeur est capturé et y reste : sur un bord, exactement là où l'on peut redimensionner la fenêtre ; sur un bouton ou une icône, en son centre. Pour s'en extraire, il faut pousser le stick un moment : stick à fond, environ 0,15 s à 25 %, 0,23 s à 50 % et 0,4 s à 100 %, et plus longtemps avec une poussée légère. Cet effort ne dépend pas de la vitesse de la souris. Sur un bord, le pointeur glisse librement le long du bord. Navigation spatiale : sur un bouton de titre, une poussée latérale passe directement au bouton voisin, centré, sans forcer ; en maintenant la poussée, il passe au suivant toutes les 0,3 s. De même, accroché au bord droit près du haut, une poussée vers la gauche mène au bouton le plus à droite ; accroché au bord haut près de la droite, une poussée vers le bas mène au bouton le plus proche. Les fenêtres de taille fixe ou agrandies n'ont pas de bords magnétiques.
  - « Automatique » (coché par défaut) : le magnétisme est toujours actif. Décoché, il n'agit que tant que la gâchette droite (ZR, RT ou R2 selon la manette) est enfoncée.
  - « Inclure les fenêtres en arrière-plan » : les bords et boutons des fenêtres visibles derrière la fenêtre active attirent aussi le pointeur, sauf là où elles sont recouvertes. Décoché, seule la fenêtre active compte, plus les icônes quand le bureau est actif.
  - « Vibrer à la capture et à la libération » (coché par défaut) : brève vibration de la manette, si elle a des moteurs, à chaque capture, saut entre boutons ou libération.
- Dans « Settings », « Lancer au démarrage » inscrit pawz dans le démarrage de Windows. L’option « Réduit dans la barre des tâches » démarre la fenêtre minimisée ; elle n’est activable que si le démarrage automatique est coché.
- La fenêtre « Debug » ne s'ouvre pas automatiquement par défaut. Dans « Settings » → « Général » → « Debug », cochez « Lancer la fenêtre de debug au démarrage » pour l'ouvrir avec pawz. Elle peut aussi être ouverte depuis le bouton « Debug Window ». Ses cinq boutons activent séparément les sources SetWindowsHookEx, SetWinEventHook, UIA, Raw Input et ETW. Les sources sont désactivées par défaut et n'affichent que le type d'événement (pas le contenu des frappes). Activer ETW demande une autorisation UAC. Les traces ETW temporaires sont supprimées à l'arrêt de la source.
- Les sections « Général », « Programme » et « Site web » ont des priorités croissantes.
- « Ajouter un programme » ouvre la boîte de sélection des `.exe` (y compris applications portables).
- « Ajouter un site web » demande un domaine, par exemple `youtube.com`.
- Le bouton HOME (central) court ouvre le menu Démarrer ; maintenu **0,8 seconde** par la manette principale ouvre pawz.

## Commandes initiales
| Contrôle | Action |
|---|---|
| Stick gauche | Déplacer le pointeur |
| A (droite) / B (bas) | Clic gauche / droit (maintenir A pour déplacer une fenêtre ou faire glisser) |
| X (haut) / Y (gauche) | Copier / coller (Ctrl+C / Ctrl+V) |
| Stick droit vertical | Défilement |
| Clic stick droit | Clic molette |
| L / R | Page précédente / suivante (général) |
| L / R dans Firefox, Chrome, Edge ou Brave | Onglet précédent / suivant |
| B / X / Y sur YouTube dans Firefox ou Brave | Clic droit / lecture-pause (Espace) / plein écran (`F`) |
| - / + | Volume - / + |
| HOME | Touche Windows |
| HOME maintenu | Fenêtre de configuration |
| - et + ensemble | Basculer le mode jeu |
| ZL maintenu, puis B / A / X / Y | Annuler / rétablir / couper / tout sélectionner |
| ZL maintenu, puis + / - | Enregistrer (Ctrl+S) / effacer (Retour arrière) |
| ZL maintenu, puis la croix | Sélectionner (Maj + flèche) |

Le clavier visuel Windows ne se lance pas automatiquement. Pour l'ouvrir manuellement, utilisez le raccourci Windows `Win` + `Ctrl` + `O`.

## Couche d'édition (ZL)
Maintenir ZL **puis** appuyer sur un bouton utilise la fonction de la couche d'édition (tableau ci-dessus). Sans ZL, les boutons gardent leur fonction normale et réagissent immédiatement : A maintenu tient toujours le clic pour faire glisser. Appuyer sur ZL après un bouton déjà enfoncé ne change rien à ce bouton. Ces raccourcis apparaissent dans le profil comme des combinaisons avec ZL et se modifient comme les autres.

## Mode jeu
En mode jeu, pawz n'envoie plus rien : ni pointeur, ni clics, ni raccourcis, ni ouverture de la configuration par HOME maintenu. La manette est laissée au jeu. Seule la combinaison - et + reste active, pour en sortir.
- Dans « Settings » → « Général » → « Mode jeu », « Automatique pour les applications en plein écran » (coché par défaut) active le mode jeu dès qu'une application occupe exactement tout l'écran. Une fenêtre simplement agrandie ne compte pas. Les navigateurs, VLC et le bureau n'y passent jamais, pour qu'une vidéo en plein écran reste pilotable.
- « Toujours en mode jeu » et « Jamais en mode jeu » prennent des noms d'exécutables séparés par des virgules (par exemple `eldenring.exe`), pour les jeux fenêtrés ou les applications plein écran qui ne sont pas des jeux.
- - et + ensemble bascule le mode jeu à la main pour l'application au premier plan, avec une vibration : longue en entrant, brève en sortant. Ce choix tient tant que cette application reste au premier plan.
- Un clic maintenu au moment du passage en mode jeu est relâché ; les boutons encore enfoncés n'agissent pas à leur relâchement.
- L'info-bulle de l'icône de notification indique « pawz — mode jeu ».

## Intégration YouTube
La détection du site actif nécessite l'extension fournie dans `browser-extension/`.
1. Ouvrir `%APPDATA%\pawz\settings.json`, copier la valeur `browser_token`.
2. Chrome, Edge ou Brave : page des extensions (`chrome://extensions`, `edge://extensions`, `brave://extensions`) → mode développeur → « Charger l'extension non empaquetée » → sélectionner `browser-extension`.
3. Firefox : `about:debugging#/runtime/this-firefox` → « Charger un module complémentaire temporaire » → choisir `manifest.json`. Le chargement temporaire doit être renouvelé après redémarrage ; pour une installation permanente, signer l'extension.
4. Dans les options de l'extension, coller le jeton (et le `port` s'il a été modifié) et enregistrer.
5. Conserver pawz en cours d'exécution. L'extension n'envoie l'URL active qu'au service local `127.0.0.1` (port 8765 par défaut).

**Limites connues** : la détection du domaine suit le dernier onglet actif signalé par le navigateur ; plusieurs fenêtres/profils simultanés du même navigateur peuvent provoquer un contexte erroné. Les raccourcis Espace, `F` et `C` de YouTube supposent que la page traite les raccourcis (et qu'aucun champ de saisie ne capte les touches). Le jeu de boutons et les axes dépendent du mapping SDL ; une manette non reconnue comme GameController nécessite un mapping SDL adapté. Les applications administrateur peuvent ignorer les entrées injectées par une application non élevée.
# Modèles, mappings et profils

Consultez [le guide MANETTES](MANETTES.md) pour les trois onglets, le profil système protégé, les raccourcis modifiables par le crayon, les illustrations et la calibration des périphériques inconnus.
