# Manettes, mappings et profils

Les paramètres proposent **GÉNÉRAL | PROFILS | MANETTES**. Les modifications de profils et de préférences de périphériques sont appliquées avec **Enregistrer** ; **Fermer** les abandonne. Les opérations explicites sur le catalogue personnalisé (dupliquer/modifier/supprimer un modèle) sont enregistrées immédiatement dans son fichier distinct.

## Profils

Les lignes **Profil** et **Afficher les boutons de** alignent leurs libellés sur **SENSIBILITÉ** et partagent le même bord gauche pour les sélecteurs. Les raccourcis affichent des SVG colorés de 21,6 px dans une colonne centrale, avec un séparateur fin entre les lignes. Le crayon et la croix n’ont ni fond ni cadre ; leurs zones de clic et infobulles sont conservées. Les boutons d’ajout d’application et de site web ont une largeur doublée.

Un profil associe des positions logiques (`SOUTH`, `EAST`, `WEST`, `NORTH`, etc.) aux actions Windows. Il conserve ses raccourcis par application et domaine, ses combinaisons et ses réglages de souris. Le profil système possède un identifiant protégé : même renommé, il ne peut pas être supprimé. Sa copie reçoit un nouvel identifiant et reste indépendante.

**Afficher les boutons de** change uniquement les libellés des SVG des raccourcis. Par exemple `SOUTH` apparaît A pour Xbox et B pour Nintendo. Les actions et entrées matérielles restent identiques. Les visuels sont passifs ; le **crayon** ouvre l’éditeur du bouton logique, de l’action, des touches clavier et de la condition application/site. Cet éditeur permet aussi de capturer une combinaison sur une manette connectée. La croix supprime le raccourci.

## Périphériques

Dans MANETTES, sélectionnez un périphérique enregistré, puis un modèle. **Utiliser ce modèle pour cette manette** mémorise ce choix. Un nom personnalisé est indépendant du nom détecté : une Battletron détectée comme Nintendo Switch Pro peut conserver ce modèle et un nom Battletron.

La détection compare les GUID documentés et les noms exacts. Les définitions livrées sont des modèles de présentation, sans GUID matériel revendiqué ni statut vérifié. SDL installé fournit le mapping matériel des manettes reconnues. Une détection par nom reste indicative ; choisissez manuellement le modèle si nécessaire.

**Ajouter un mapping…** édite une surcharge JSON propre au périphérique. Les entrées sont des noms logiques ; les valeurs désignent les sources brutes SDL : `b0` (bouton), `a1` (axe), `+a1`/`-a1` (demi-axe), `h0.1/2/4/8` (haut/droite/bas/gauche). Les indices sont ceux du matériel : utilisez la calibration, ne les déduisez pas d’une autre manette.

**Calibrer…** lit la manette réelle. Choisissez l’entrée logique, relâchez les contrôles, cliquez **Capturer cette entrée**, puis actionnez-la. Répétez pour les contrôles souhaités et enregistrez. Les actions souris/clavier sont suspendues pendant la capture. Les gâchettes restent des axes analogiques ; un seuil de 0,5 permet aussi leur utilisation comme raccourcis. Cette première calibration ne règle pas automatiquement l’inversion, les plages ou la zone morte des axes.

## Illustrations

Chaque modèle nommé du catalogue possède maintenant son illustration SVG dédiée, visible dans MANETTES et sur l’écran principal. Le tableau d’identification centré affiche fabricant, modèle, famille, GUID SDL et statut. Les correspondances centrent leurs valeurs et montrent les icônes des boutons dans « Libellé physique » ; les axes X/Y utilisent des symboles distincts. Les libellés complets restent disponibles en infobulle et pour l’accessibilité.

Les boutons des raccourcis utilisent les SVG embarqués de Gamepad Prompt Asset Pack, adaptés au modèle choisi. L’icône du modèle générique vient de Gamepad Asset Pack. Les illustrations de familles restent des dessins abstraits, sans prétendre représenter exactement les modèles commerciaux. Vous pouvez choisir un SVG livré, importer votre propre SVG valide (4 Mo maximum), ou restaurer l’illustration. Les imports sont copiés dans le répertoire utilisateur ; les préférences utilisent des références relatives `asset:`/`user:`. Dupliquer, Modifier et Supprimer utilisent des icônes avec infobulles.

La résolution suit : SVG du périphérique, SVG du modèle, famille, générique. Qt conserve transparence et proportions. Le périphérique déconnecté conserve son dessin atténué. **Oublier** retire ses réglages, son mapping et son attribution de profil.

## Sauvegarde et identité

La migration de `settings.json` v1 vers v2 crée d’abord `settings.json.v1.bak`. Elle conserve les actions et contextes existants et transforme leurs anciennes touches en identifiants logiques. Les versions inconnues sont refusées.

Un GUID identifie un type de matériel, pas un appareil physique. Chaque connexion utilise l’identifiant d’instance SDL ; plusieurs manettes identiques restent distinctes pendant la session, y compris si l’une est débranchée. Sans numéro de série accessible, retrouver avec certitude la même manette parmi plusieurs exemplaires identiques après reconnexion est impossible : les emplacements enregistrés sont réutilisés au mieux. Vérifiez alors leurs noms et profils.

8BitDo, Battletron, Switch 2 et les variantes non identifiables utilisent SDL/générique et la calibration. La présence d’un modèle dans le sélecteur ne garantit pas la prise en charge de tous ses boutons supplémentaires par pygame/SDL installé.
