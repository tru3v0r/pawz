# Provenance des visuels

**État actuel :** voir [les SVG et polices intégrés](ASSETS_INTEGRES.md). Les 148 prompts autorisés et l’icône générique de la bibliothèque sont désormais embarqués, ainsi que Super Water. Le texte ci-dessous conserve la décision initiale, avant cette sélection ressource par ressource.

## État initial archivé

Les quatre fichiers `src/pawz/ui/assets/controllers/{generic,xbox,playstation,nintendo}.svg` sont des illustrations vectorielles abstraites originales créées pour pawz. Ils sont distribués sous la licence GPL-3.0 du projet, sans reprise d’image, logo ou police de fabricant. Les SVG de raccourcis sont construits par le code Qt à partir de libellés textuels. Les marques citées identifient les modèles ; elles n’impliquent aucune affiliation.

## Gamepad Asset Pack : examen du 8 novembre 2026

Source : https://github.com/AL2009man/Gamepad-Asset-Pack

La racine distingue `Controller Asset Pack`, `Connection Icon Pack` et le sous-module `Gamepad-Prompt-Asset-Pack`. `Controller Asset Pack` contient notamment les dossiers DualSense, DualShock 4, Generic Controller Type, Nintendo Switch, Steam Controller, Steam Deck, Xbox 360 et Xbox Wireless. Le README décrit des SVG Inkscape, PNG et XCF, ainsi que certaines variantes contenues dans un même SVG.

Le dépôt annonce MIT, mais son README indique que la majorité des illustrations sont reprises de sources officielles ou recréées, et déconseille leur utilisation pour des produits commerciaux. Il cite également des symboles de touchpad d’un contributeur tiers. Cette licence globale ne permet pas de confirmer les droits sur chaque illustration de fabricant.

**Aucune ressource de ce pack n’est redistribuée par cette intégration.** L’alternative livrée est originale et libre. L’intégration des dessins exacts reste conditionnée à une vérification ressource par ressource. Un futur ajout devra conserver la notice MIT et les attributions spécifiques, documenter la source et la preuve d’autorisation. L’import utilisateur permet d’utiliser un dessin choisi sans l’inclure dans la distribution du projet.

Sources consultées : README et LICENSE à la racine ; arborescence de `Controller Asset Pack`. Aucune affirmation de licence sur une image individuelle n’est déduite de son seul emplacement.
