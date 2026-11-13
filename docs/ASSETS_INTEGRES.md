# SVG et polices intégrés

## Illustrations dédiées aux modèles

Les 18 modèles nommés du catalogue utilisent désormais chacun un SVG original sous `controllers/models/` : Xbox 360/One/One S/Series/Elite/Adaptive, DualShock/DualSense, Switch Pro/Joy-Con, Logitech F310/F510/F710 et Steam Controller/Deck. Ils remplacent les anciennes silhouettes identiques par famille. Ces dessins stylisés sont créés pour pawz, sous GPL-3.0, sans reprise d’image ou de logo officiel de fabricant. Ils ne constituent pas une certification matérielle ni des plans de calibration. Les quatre SVG originaux d’axes X/Y sont sous `controllers/input-icons/`. Le script `scripts/generate-controller-illustrations.py` permet de régénérer ces ressources et les références SVG du catalogue.

Les dessins complets commerciaux du pack principal AL2009man ne sont toujours pas redistribués. Les paragraphes ci-dessous concernant ce pack restent applicables aux ressources effectivement importées.

Le logo provisoire de pawz (deux empreintes de patte, dans l’esprit de l’émoji 🐾) est un dessin original : `ui/assets/paws.svg`, rendu en `paws.png` pour l’interface et en `paws.ico` (16 à 256 px) pour l’exécutable. Il ne reprend pas le dessin de l’émoji de Windows, qui appartient à Microsoft.

Les icônes d’action de pawz sont des SVG originaux sous `ui/assets/icons/` (crayon, croix, duplication, réglages, profils et icône de site). Leurs variantes désactivées restent vectorielles. Les en-têtes rendent leur `QIcon` à la résolution courante, sans bitmap intermédiaire de 16 ou 20 px. Ces dessins reprennent les primitives déjà utilisées dans le code de pawz, sous la licence du projet.

## Bibliothèque AL2009man

Le rendu des raccourcis privilégie les fichiers `-Color.svg` lorsqu’ils existent (lettres et symboles de façade). Les autres entrées conservent le SVG neutre de la bibliothèque. Le choix des couleurs est visuel et ne change jamais les identifiants logiques ou actions.

**148 SVG de boutons** issus de [Gamepad Prompt Asset Pack](https://github.com/AL2009man/Gamepad-Prompt-Asset-Pack), révision `552d6448ffc4a6f84d488454878357ea375a59bd`, sont embarqués sous `ui/assets/controllers/prompts/`. Les groupes retenus sont Shared, Nintendo, PlayStation et Xbox : boutons, sticks, gâchettes, croix, palettes et touches de contexte. Les boutons Guide propres aux plateformes sont exclus, conformément à l’exception de redistribution indiquée par l’auteur.

L’icône générique autonome vient de [Gamepad Asset Pack](https://github.com/AL2009man/Gamepad-Asset-Pack), révision `a6d1113b0b3b2438bbbcb08a33f9a25eb2391d7c`, fichier `Connection Icon Pack/Controller Type/SVG/VSCView Generic Controller.svg`. Elle est livrée sous `library-generic.svg` et utilisée par le modèle générique.

Auteur : **Al. Lopez / AL2009man**. Licences MIT intégrales : `controllers/prompts/LICENSE.txt` et `controllers/Gamepad-Asset-Pack-LICENSE.txt`. Le README du sous-pack est conservé. Les fichiers sont stockés sans modification ; Qt sélectionne le calque « Style - Outline (Black) » et compose les combinaisons en mémoire, sans conversion PNG. Les glyphes des prompts sont des tracés vectoriels ; aucune installation d’Open Sans n’est requise. L’auteur mentionne Open Sans de Steve Matteson comme source des lettres.

`controllers/upstream-manifest.json` conserve l’URL exacte de révision et le SHA-256 de chaque ressource. `scripts/vendor-controller-assets.py` reproduit le téléchargement. Aucun téléchargement n’est effectué au lancement de l’application.

Les dessins complets commerciaux du pack principal restent exclus de l’intégration automatique : son README signale des images officielles reprises ou recréées. Les droits de tiers ne sont pas déduits de la seule licence MIT globale. Les modèles utilisent les illustrations stylisées originales de pawz décrites plus haut ; un autre dessin peut être importé par l’utilisateur. Cette sélection ne constitue donc pas l’intégration de tous les dessins commerciaux du pack.

## Polices embarquées

- **Inter Regular / SemiBold** : `fonts/Inter-Regular.ttf` et `fonts/Inter-SemiBold.ttf`, licence SIL Open Font License 1.1 conservée dans `fonts/OFL.txt`. Le nom interne de ces fichiers est `Inter 18pt`, utilisé dans le QSS.
- **Super Water** : fichier original distribué par fsuarez913 / All Super Font sur [DaFont](https://www.dafont.com/super-water.font), emballé sous `fonts/SuperWater.ttf`. L’auteur indique « Free for personal use & commercial use ». Le ZIP n’a pas de licence distincte ; l’origine et cette déclaration sont conservées dans `fonts/SuperWater-NOTICE.txt`, sans relabelliser la police sous GPL ou OFL.

Qt charge systématiquement les trois fichiers par `QFontDatabase.addApplicationFont`, avant la création de la fenêtre. Aucun accès au répertoire des polices installées n’est requis. Les fichiers et notices sont inclus dans PyInstaller et dans les données du paquet Python. Le symbole Guide et les entrées sans SVG autorisé utilisent un libellé générique rendu avec Inter.
