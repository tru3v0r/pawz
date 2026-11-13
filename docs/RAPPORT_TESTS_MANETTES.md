# Rapport de validation — 8 novembre 2026

## Illustrations et tableaux de MANETTES

Les 18 modèles nommés utilisent chacun une illustration SVG originale dédiée (sans logo ni image officielle de fabricant), partagée avec l’écran principal. Les personnalisations d’illustration gardent leur priorité. Le générique continue d’utiliser son SVG de bibliothèque. Le script `generate-controller-illustrations.py` régénère les dessins et quatre symboles d’axes X/Y.

Le bloc d’identification est un tableau centré de cinq lignes : fabricant, modèle, famille, GUID SDL, statut. Les valeurs proviennent des données réelles du catalogue et du périphérique, sans nouveau statut vérifié. La largeur est plafonnée et les lignes adaptent leur hauteur au texte. Dans les correspondances, toutes les cellules et en-têtes sont centrés ; « Libellé physique » affiche un SVG passif, avec le texte conservé en infobulle et dans les données d’accessibilité. Les axes ont des icônes directionnelles propres.

**141 tests réussis en 15,66 s**, y compris les comparaisons des 21 captures à 100 %, 125 % et 150 %. Les nouveaux tests couvrent les cinq valeurs d’identification, le centrage après redimensionnement, le changement d’icônes/modèle, la conservation du mapping matériel, les illustrations personnalisées et le défilement. Les 18 SVG de modèles et les icônes d’axes sont validés. Captures natives inspectées et planche des modèles : `build/controllers-tables/`. Journal du build : `build/rebuild-controllers-tables.log`. Le test du binaire vérifie désormais aussi la présence et le chargement de tous les SVG référencés par le catalogue.

Build et démarrage depuis un autre répertoire réussis pour `dist/controllers-tables/pawz/pawz.exe`. Rapport : `build/smoke-a773ddd02e2a4471bbe363e02ee98cf2/report.json`, avec `model_svgs_valid=true`. Les SVG intégrés sont des dessins stylisés originaux ; les dessins officiels/commerciaux du pack principal ne sont pas redistribués.

## Rendu haute résolution des icônes et du texte

Les icônes crayon, croix, duplication, profils, réglages et site sont désormais des SVG, avec variantes SVG désactivées pour les actions protégées. Les icônes d’en-tête sont peintes depuis leur `QIcon` original à la résolution courante. Les icônes d’applications Windows privilégient la grande image extraite du programme ; les images PNG du logo restent dans leur résolution d’origine jusqu’au rendu. Aucun bitmap de travail de 18/20 px n’est agrandi pour ces actions.

Le texte utilise `PreferVerticalHinting` et `PreferAntialias`, conservés après application du QSS. Sur Windows/DirectWrite, le premier conserve les métriques horizontales naturelles, au lieu de déformer chaque glyphe pour l’aligner sur un nombre entier de pixels. Les polices, tailles et préférences d’échelle Windows sont conservées. Ce réglage améliore la régularité ; il ne promet pas l’absence de toute variation de lissage sur chaque écran ou sur une capture ensuite redimensionnée. Référence : https://doc.qt.io/qt-6/qfont.html#HintingPreference-enum.

**136 tests réussis en 11,84 s**. Les nouvelles vérifications demandent réellement des images d’icônes à 100 %, 125 %, 150 % et 200 %, y compris en mode désactivé : elles détectent les anciens petits bitmaps incapables de fournir la résolution demandée. Les 21 captures de référence à 100 %, 125 % et 150 % ont été renouvelées et comparées ; les captures natives inspectées sont sous `build/dpi-rendering/`. Le passage réel entre plusieurs écrans physiques n’a pas été exercé.

La distribution est construite séparément sous `dist/dpi-rendering/`, journal `build/rebuild-dpi-rendering.log`. Le test de démarrage contrôle aussi que le moteur SVG du binaire produit bien une icône de 36 pixels physiques pour 18 pixels logiques à une densité de 2.

Build et lancement réussis. Le rapport `build/smoke-69c30fbcf7104d0688b8e5d08b5bd3d3/report.json` confirme `vector_icon_native_dpi=true`, ainsi que le chargement du catalogue, des SVG et des deux familles de polices embarquées.

## Ajustements de dimensions de PROFILS

Les boutons d’ajout de site et d’application utilisent deux fois leur largeur naturelle, avec hauteur et centrage conservés. Le rendu des icônes de raccourcis est réduit de 10 % supplémentaires (24 → 21,6 px), sans déplacement des colonnes ni des actions. Les deux libellés de sélection sont alignés sur « SENSIBILITÉ » ; seuls les débuts des sélecteurs se déplacent de 14 px vers la droite, leur bord droit restant fixe. Les tests de géométrie couvrent l’alignement des libellés et le doublement des boutons. Les captures natives de cette révision sont sous `build/profiles-sizing/` ; le journal du build est `build/rebuild-profiles-sizing.log`.

Les **110 tests ont réussi en 11,67 s**. L’application `dist/pawz/pawz.exe` étant ouverte, le build initial a été interrompu pendant l’analyse, avant toute modification de cette distribution. La compilation reprend vers `dist/profiles-sizing/` ; journal : `build/rebuild-profiles-sizing-final.log`.

Cette compilation a réussi. Le lancement de `dist/profiles-sizing/pawz/pawz.exe` depuis un autre répertoire a été validé par `build/smoke-c6be1259da01461cb59f1a03328133f2/report.json`, polices et SVG compris. Le test utilise désormais un port loopback éphémère pour cohabiter avec une copie déjà ouverte. L’ancienne application est restée ouverte et sa distribution n’a pas été remplacée.

## Présentation affinée de PROFILS

Les sélecteurs « Profil » et « Afficher les boutons de » sont alignés par une grille commune. Les prompts utilisent les variantes colorées lorsqu’elles existent, avec une hauteur de 24 px dans une colonne de 72 px ramenée vers le centre des lignes. Les actions de raccourcis affichent des glyphes de 14 px, sans cadre ni fond, tout en conservant une zone de clic de 24 px, les infobulles et l’édition existante. Des séparateurs de 1 px (`#31557e`) distinguent les raccourcis.

Les tests ajoutés contrôlent l’alignement et la largeur des sélecteurs, les tailles des SVG, leur position centrale et identique entre lignes après redimensionnement, le nombre et la couleur réelle des séparateurs, ainsi que l’absence de fond des actions. Les références des 21 captures ont été renouvelées ; les captures natives sont sous `build/profiles-refinement/`. Le journal du nouveau build est `build/rebuild-profiles.log`.

Le script complet a abouti : **110 tests réussis en 11,67 s**, compilation PyInstaller et démarrage du nouvel exécutable depuis un autre répertoire validés, avec les polices et SVG embarqués. Le résultat est disponible sous `dist/pawz/`.

## Corrections graphiques et intégration des SVG

Super Water est désormais embarquée et chargée depuis les ressources, avec Inter Regular et SemiBold. Les contrôles Dupliquer/Modifier/Supprimer sont des icônes avec infobulles et noms accessibles ; le mode désactivé est atténué. Les portions non remplies des pistes utilisent `#10233f`. Les titres d’application/site occupent leur largeur naturelle à côté d’une icône de 16 px.

148 SVG de Gamepad Prompt Asset Pack et l’icône générique de Gamepad Asset Pack sont embarqués. Le rendu utilise les vrais tracés SVG, y compris pour les combinaisons, sans modifier les actions. Les fichiers Guide propres aux plateformes sont exclus selon les conditions de l’auteur. Voir `ASSETS_INTEGRES.md` pour les révisions, notices et la limite concernant les dessins complets des modèles commerciaux.

Validation : **108 tests réussis**, dont les comparaisons exactes de 21 captures (sept scènes à 100 %, 125 % et 150 %). Les scènes supplémentaires contrôlent les titres VLC/site web après défilement et le bas de MANETTES. Des captures natives Windows sont disponibles sous `build/ui-corrections/`. Les tests vérifient aussi l’enregistrement des trois polices depuis les fichiers embarqués sans consulter les familles système, les icônes et leur état désactivé, la couleur réelle des pixels de piste et les SVG provenant du manifeste. Le test de lancement du build vérifie désormais aussi les familles de polices résolues et le chargement d’un prompt de la bibliothèque.

Le script complet de build a abouti avec Python 3.12.10. Journal : `build/rebuild-ui.log`. Le rapport `build/smoke-a1549ccc9a00445d8e01b441c496cb42/report.json` confirme le démarrage depuis un autre répertoire, les SVG valides, les familles résolues `Super Water` et `Inter 18pt`, et `library_prompt_valid=true`. Distribution mise à jour : `dist/pawz/`.

## Nouveau build après installation de Python 3.12.10

Le script complet `scripts/build-windows.ps1` a été relancé avec Python **3.12.10**, à la demande de l’utilisateur. Installation des dépendances, **103 tests réussis en 11,04 s**, préparation des interfaces UI Automation, compilation PyInstaller et test de lancement depuis `%TEMP%` ont abouti. La distribution mise à jour est `dist/pawz/`, avec l’exécutable `dist/pawz/pawz.exe` et les documents/extension/licence copiés par le script. Journal : `build/rebuild-windows.log`.

Rapport du test de lancement intégré : `build/smoke-052fcd92b393446abda435b2f6d8a432/report.json`. La première tentative en environnement restreint avait échoué au téléchargement des dépendances ; la relance avec accès réseau autorisé a permis l’exécution complète. Les résultats ci-dessous décrivent le build antérieur avec Python 3.12.3 et restent conservés pour traçabilité.

## Résultats exécutés

Environnement : Windows 10 build 19045, Python 3.12.3, pygame 2.6.1 / SDL 2.28.4, PySide6/Qt 6.12.0, pytest 9.2.0, pytest-qt 4.5.0.

Commande complète : `$env:PAWZ_VISUAL_TESTS='1'; .\.venv\Scripts\python -m pytest -q --tb=short`.

**103 tests réussis en 10,83 s**, sans test ignoré dans cette exécution. La suite sans variable visuelle ignore volontairement les trois comparaisons de captures dépendantes de l’environnement graphique.

Couverture exécutée : normalisation SDL2 et migration des boutons, préservation des contextes et combinaisons, identité de plusieurs manettes de même GUID, débranchement et remplacement à nombre égal de périphériques, relâchement des clics isolé par appareil, calibration sur instantanés bruts de boutons/axes/croix, validation du catalogue et protection des modèles intégrés, protection métier du profil système après renommage, duplication indépendante, migration reproductible/idempotente avec sauvegarde, persistance des préférences et mappings, trois onglets, contrôles de profils, édition via crayon, SVG passifs, changement visuel immédiat sans changement d’action, redimensionnement, défilement et comportements existants. Les données matérielles de tests unitaires sont contrôlées ; elles ne remplacent pas une validation physique.

Le test PowerShell exécute un véritable échec de commande native (code 23) dans `Invoke-Checked` et vérifie l’absence de message SUCCESS. Aucun build destructif n’est lancé par ce test.

## Captures

15 références sous `tests/visual/reference/` : GÉNÉRAL, PROFILS/Default, PROFILS/personnalisé, MANETTES et écran principal avec trois périphériques, aux facteurs Qt 1, 1,25 et 1,5. Comparaison exacte des pixels réussie sur ces trois facteurs. Les références sont inspectées dans le cadre de cette intégration ; elles ne constituent pas une approbation utilisateur de la charte.

15 captures supplémentaires ont été produites avec le moteur **Windows natif** (`QT_QPA_PLATFORM=windows`) sous `build/visual-native/`. Inspection des vues MANETTES, PROFILS et écran principal : fond sombre, contraste des informations, colonne SVG et boutons d’édition, état désactivé et atténuation des manettes déconnectées. Les premiers captures ont permis de corriger un fond blanc dans MANETTES et de restaurer l’indication de manette principale. Les derniers captures natifs incluent ces corrections. Les facteurs Qt reproduisent des échelles de rendu ; le réglage DPI système de Windows et le déplacement entre écrans physiques de DPI différents n’ont pas été modifiés/testés.

## Build et lancement

Build final exécuté avec succès :

```powershell
.\.venv\Scripts\python -m PyInstaller --noconfirm --distpath dist/controller-refactor-final --workpath build/controller-refactor pawz.spec
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test-build-windows.ps1 -Executable dist/controller-refactor-final/pawz/pawz.exe
```

Exécutable : `dist/controller-refactor-final/pawz/pawz.exe`. Conserver tout son dossier `onedir`. Documentation, exemple, extension navigateur et licence ont été ajoutés à cette distribution.

Journal : `build/build-refactor-final.log`. Rapport du lancement final : `build/smoke-352c6b37d05f49238ae9576a6e57b6a2/report.json` : `started=true`, `models=19`, `svg_valid=true`, `devices=0`. L’exécutable a démarré depuis `%TEMP%`, ouvert la vraie fenêtre, chargé le catalogue validé et le SVG embarqué, puis s’est fermé automatiquement. La configuration était isolée ; les réglages de démarrage Windows n’ont pas été modifiés.

Un build intermédiaire avait échoué lors du remplacement d’un dossier `_internal` verrouillé (WinError 32). Cet échec n’a pas été annoncé comme réussi ; un répertoire de distribution distinct a permis le build et le lancement finaux. La commande complète `build-windows.ps1` (réinstallation des dépendances et génération préalable UI Automation incluses) n’a pas été relancée de bout en bout ; ses étapes tests, PyInstaller et validation de lancement ont été exécutées séparément. Les interfaces UI Automation et l’injection d’actions n’ont pas été contrôlées manuellement dans le binaire.

## Vérifications restantes et limites

- **Aucun matériel physique connecté** : vérifier les commandes Windows réelles, les appuis longs, les gâchettes et les axes dans les applications cibles, les contextes navigateur et les reconnexions USB/Bluetooth sur chaque modèle.
- Confirmer la détection des noms SDL, les GUID, les pilotes et les boutons supplémentaires. Aucune définition ne prétend être vérifiée ; aucun GUID ni indice brut de fabricant n’a été inventé. Les 19 définitions sont des présentations, pas une certification matérielle.
- Sans numéro de série universel accessible via pygame, l’association physique entre deux modèles identiques après reconnexion est au mieux. Les instances en session restent isolées.
- Calibration initiale : capture des sources, sans assistant de mesure complète de plage/inversion/bruit. Tester particulièrement les gâchettes brutes au repos à -1 et les axes combinés.
- Vérifier le confort visuel réel aux tailles d’écran cibles et en environnement multiécran. Les comparaisons pixel nécessitent les mêmes Qt/polices/moteur que leurs références.
- Les SVG exacts Gamepad Asset Pack ne sont pas redistribués : les droits des images de fabricants restent à établir. Les quatre alternatives abstraites originales et leur provenance sont documentées dans `ASSETS.md`.
- Switch 2, Joy-Con 2, 8BitDo et Battletron sans définition fiable utilisent SDL/générique ou le choix manuel/calibration. Leur prise en charge spécifique reste à vérifier sur matériel.

L’intégration logicielle et le build ont été exercés dans l’environnement ci-dessus. La validation matérielle complète et l’intégration des visuels commerciaux exacts ne sont donc **pas déclarées terminées**.
