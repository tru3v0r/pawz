# Bundled assets and their licences

## Original artwork (project licence, GPL-3.0-or-later)

- **Logo**: a controller with four coloured buttons spelling P A W Z as the toes of a paw, drawn for pawz: `ui/assets/logo.svg` for the interface and `logo.ico` (16 to 256 px) for the executable. Both are made from `design/logo/logo.svg` by `scripts/update-logo.py`, framed square and without PowerPoint's invisible text layer. Working files (PSD, SVG, drafts) live in the git-ignored `design/` folder.
- **Controller models**: each of the 18 named models has its own stylized SVG under `controllers/models/` (Xbox 360/One/One S/Series/Elite/Adaptive, DualShock/DualSense, Switch Pro/Joy-Con, Logitech F310/F510/F710, Steam Controller/Deck), with no manufacturer image or logo. They are not a hardware certification or calibration plans. The four X/Y axis icons are under `controllers/input-icons/`. `scripts/generate-controller-illustrations.py` regenerates them and the catalogue's SVG references.
- **Action icons** (pencil, cross, duplicate, settings, profiles, website) under `ui/assets/icons/`, with vector disabled variants.

Brand names identify controller models; they imply no affiliation.

## AL2009man libraries (MIT)

- **148 button SVGs** from [Gamepad Prompt Asset Pack](https://github.com/AL2009man/Gamepad-Prompt-Asset-Pack), revision `552d6448ffc4a6f84d488454878357ea375a59bd`, under `ui/assets/controllers/prompts/`: Shared, Nintendo, PlayStation and Xbox buttons, sticks, triggers, D-pads, paddles and context keys. Platform-specific Guide buttons are excluded, following the author's redistribution exception.
- **Generic controller icon** from [Gamepad Asset Pack](https://github.com/AL2009man/Gamepad-Asset-Pack), revision `a6d1113b0b3b2438bbbcb08a33f9a25eb2391d7c`, file `Connection Icon Pack/Controller Type/SVG/VSCView Generic Controller.svg`, shipped as `library-generic.svg`.

Author: **Al. Lopez / AL2009man**. Full MIT licences: `controllers/prompts/LICENSE.txt` and `controllers/Gamepad-Asset-Pack-LICENSE.txt`; the sub-pack README is kept. Files are stored unmodified; Qt selects the "Style - Outline (Black)" layer and composes combinations in memory. Prompt glyphs are vector paths, so Open Sans (which the author cites as the source of the letters) need not be installed. Coloured `-Color.svg` variants are preferred when they exist; colours never change logical ids or actions.

`controllers/upstream-manifest.json` records the exact revision URL and SHA-256 of each file; `scripts/vendor-controller-assets.py` reproduces the download. Nothing is downloaded when the app runs.

The full commercial controller drawings of the main pack are **not** redistributed: its README says most are taken or recreated from official sources, and the global MIT licence does not establish the rights on each manufacturer image. Users can import a drawing of their choice instead.

## Fonts

- **Inter Regular / SemiBold**: `fonts/Inter-Regular.ttf` and `fonts/Inter-SemiBold.ttf`, SIL Open Font License 1.1 (`fonts/OFL.txt`). Their internal family name, `Inter 18pt`, is the one used in the stylesheet.
- **Matcha Style**: original file by Khurasan Studio, shipped as `fonts/MatchaStyle.ttf` and used for the app title. The author states "100% free for personal use & commercial use"; the archive has no separate licence. Its origin and that statement are kept in `fonts/MatchaStyle-NOTICE.txt`, without relicensing it under GPL or OFL.

Qt loads the three fonts from the bundled files with `QFontDatabase.addApplicationFont` before creating any window; installed fonts are not needed.
