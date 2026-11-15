# pawz — Developer guide

## Layout
- `pawz/__init__.py`: the application's identity (`APP_NAME`, `APP_ID`, previous names, `PAWZ_` environment prefix). Renaming the app means changing these constants, the package folder and the docs.
- `core/models.py`: typed settings model and validation; shortcut priority global → application → most specific domain.
- `core/controllers.py`: SDL GameController discovery, polling on a dedicated thread at 250 Hz (20 Hz without a controller), execution of gesture effects, pointer and wheel, game mode, haptics; publishes `live_state` (held buttons, raw sticks) for the main window.
- `core/controller_services.py`: model resolution (chosen model, known GUID, USB ids in the SDL GUID, exact name, name fragments), device identity, raw mappings and calibration.
- `engine/` (pure: no Qt, SDL or Windows, enforced by a test):
  - `actions.py`: action catalogue (id, label, behaviour) and the `OutputSink` interface; adding an action is a single entry.
  - `gestures.py`: gesture rules (held clicks, combinations, layers, long press, capture), table-tested.
  - `magnet.py`: sticky magnetism and spatial navigation.
  - `game_mode.py`: when pawz steps aside for a game.
  - `auto_detect.py`: guesses the inputs of a drawing from its layer names and geometry. Rule types (`labels`, `diamond`, `sticks`, `mirror`, `top_pairs`, `centre_pairs`, `centre_single`) are implemented here; the rules themselves, their order, thresholds and confidences are data in `data/controllers/auto-detect.json`.
- `infra/windows.py`: Windows layer (SendInput keyboard/mouse injection, `WindowsOutput`, foreground process and full-screen detection).
- `infra/window_targets.py`: magnetic targets read from Windows (resize lines and caption buttons by hit-testing, desktop icons), probed on a worker thread.
- `infra/browser.py`: token-protected loopback HTTP server receiving the active tab.
- `infra/storage.py`: atomic JSON persistence in `%APPDATA%\pawz\settings.json`, migration from a previous app name.
- `infra/startup.py`: logon registration in the user's Run key.
- `ui/`: Qt windows and widgets.
  - `windows.py`: main window (controller slots, crown, live inputs), settings dialog, profile editor, stylesheet, notification icon.
  - `controllers_page.py`, `controller_tables.py`: the Controllers tab, its identification table and the illustration picker.
  - `controller_assets.py`: illustration and prompt SVGs (resolution, named copies, styling, the table delegate).
  - `artwork_editor.py`: the Name inputs window and Auto-detect.
  - `artwork_styles.py`, `themes.py`: controller styles and colour themes (below).
  - `rendering.py`: native-DPI icons and text rendering.
- `data/controllers/`: the built-in catalogue (`catalog.json`), its JSON Schema and the Auto-detect rules (`auto-detect.json`, see [Controllers](CONTROLLERS.md#auto-detect-rules)).
- `i18n.py` and `data/i18n/`: interface language (see Translations below).
- `main.py`: wiring and lifecycle.
- `browser-extension/`: Manifest V3 extension for Chrome, Edge, Brave and Firefox; its texts are in `_locales/<language>/messages.json`.

See [Architecture](ARCHITECTURE.md) for threading, gestures, magnetism and persistence.

## Running and testing
- Run: `powershell -ExecutionPolicy Bypass -File scripts\run-windows.ps1`.
- Tests: `python -m pytest -q`. With `PAWZ_VISUAL_TESTS=1`, pixel comparisons of the settings and main windows run too (see Architecture). `tests/conftest.py` resets the theme and controller style before each test and hides the named drawings saved in the user's settings folder, so a developer's own settings never change the results.
- Lint and types: `python -m ruff check .`, `pyright src`.

## Translations
Interface strings are written in English in the code and wrapped in `tr()` from `pawz.i18n`. Strings defined at import time (action labels, table headings, error messages raised by the model) are marked with `QT_TR_NOOP()` and translated where they are displayed. Text with variables uses named placeholders, `tr("Forget “{name}”…").format(name=...)`, never an f-string, so that `pyside6-lupdate` can extract it and translators can move the variable.

Translations are Qt Linguist files in `src/pawz/data/i18n/`: `pawz_<language>.ts` (the source, edited with Qt Linguist or a text editor) and `pawz_<language>.qm` (compiled, loaded at startup). After changing interface text:

1. `python scripts/update-translations.py` adds new strings to every `.ts` file as unfinished and drops removed ones.
2. Translate the unfinished entries.
3. Run the script again to compile the `.qm` files.

A test fails while a `.ts` file is out of date with the code, while an entry is untranslated, or when a translation loses a `{placeholder}`.

To add a language: `python scripts/update-translations.py --new de`, translate `pawz_de.ts`, run the script again, then add the code and the language's own name to `LANGUAGES` in `src/pawz/i18n.py` (and to `RIGHT_TO_LEFT` for a right-to-left script), with its estimated quality in `QUALITY`: Settings shows it in the language list and under it, inviting speakers to improve any translation below Excellent. Raise a language's level there once native speakers have reviewed it. The language is chosen in Settings (`language` in the settings file: `auto` follows Windows); `i18n.match()` maps a Windows language tag to an offered variety (`es-MX` → `es_419`, `zh-HK` → `zh_TW`, `ku-IQ` → `ckb`, `no` → `nb`…). Qt's own translations of standard dialogs are loaded alongside; for languages Qt does not translate, `data/i18n/qt_buttons.json` gives the OK, Cancel, Yes, No and Save buttons (a test checks every language has them). Add the language's `qtbase_` prefix to `QT_LANGUAGES` in `pawz.spec` when Qt ships one. For the browser extension, add `browser-extension/_locales/<language>/messages.json` with a code Chrome supports (Spanish from Spain is `es`, Norwegian Bokmål `no`).

## Themes
The stylesheet (`CSS` in `ui/windows.py`), inline styles and icons are written in Corporate Blue colours. A theme in `ui/themes.py` maps each of them: Comfy Turquoise fills buttons with its accent `#00a8b0` and keeps the luminance ratios between colours: every blue's relative luminance is multiplied by the same factor (accent / button fill, about 4, capped at white) and its hue turned to the accent's. The application name takes the accent too. Danger Red fills buttons with a dark red, `#9b1c1c`, close to the original fill's luminance, so the theme stays as dark as Corporate Blue; button outlines and the application name take a bright red, `#ff2d2d`. It gives every colour the accent's exact hue (`keep_hue_offsets=False`): near red, the small hue differences between the original blues drift into brown and orange. Cheeky Green, Juicy Orange and Squishy Purple are built the same way: a fill with the original fill's luminance and exactly the hue of their outlines and application name (`#005d00` / `#00ff00`, `#7b4000` / `#ff8c00`, `#6d329a` / `#b026ff`). Neutral and status colours are left alone. Write new colours in Corporate Blue and pass inline styles through `themed()` (the application stylesheet is `stylesheet()`; icons from `vector_icon()` are themed already). A new theme is one `Theme` entry: an accent, the source colour it replaces (`anchor`), and overrides for colours that should not simply follow the ratio. The theme, like the language, is applied at startup; saving a change offers to restart (the new instance waits for the old one to exit, since it holds the browser bridge port).

## Controller styles
`ui/artwork_styles.py` redraws the bundled controller artwork (`controllers/library/`, `controllers/models/`, `library-generic.svg` and their named copies; never prompts or the user's imported SVGs) in the setting `controller_style`. Dark and Light map each colour to a mix of a body and a detail colour according to its lightness; Eye Candy fills dark areas with the body colour and light ones with the button fill, and outlines every visible, opaque shape in the button outline colour, compensating each shape's transform so outlines look even; shapes smaller than `GLYPH_SIZE` of the drawing (letters, arrows) stay light and unoutlined. The palettes are Corporate Blue colours passed through the current theme. `controller_assets.artwork_bytes()` applies the style, cached per file, style and theme; the style changes live, without a restart.

## Scripts
- `run-windows.ps1`, `build-windows.ps1`, `test-build-windows.ps1`: run from source, build, check a build (below).
- `update-translations.py`: extract and compile translations (above).
- `update-logo.py`: rebuilds `src/pawz/ui/assets/logo.svg` (framed square, PowerPoint's invisible text layer removed) and `logo.ico` from `design/logo/logo.svg`; `design/` (git-ignored) holds the working files.
- `vendor-controller-assets.py`: downloads the pinned Gamepad Prompt Asset Pack and Gamepad Asset Pack files and rewrites `upstream-manifest.json`; `DETAILED_ARTWORK` lists the detailed drawings and what changes in them, by Inkscape label or element id: elements removed (logos, a chroma-key screen) and hidden layers shown (`show:`), recorded in the manifest. Never run by the app.
- `generate-controller-illustrations.py`: redraws the four pawz controller drawings and the axis icons.

## Build
`powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1`

PyInstaller must run **on Windows**. The build is a `onedir` distribution in `dist\pawz` (do not move the `.exe` alone), with the docs, the example settings, the extension and the licence copied next to it. `pawz.spec` only ships what pawz uses: Qt Core/Gui/Widgets/Svg, the controller part of pygame and Qt's own translations for the target languages. `scripts/test-build-windows.ps1` then starts the executable from `%TEMP%` with isolated settings and checks the catalogue, schema, SVGs and fonts; it catches a library removed by mistake. If the build cannot empty `dist\pawz` ("being used by another process"), close pawz, Explorer windows on that folder and any sync client watching it, or rename the folder aside.

## Settings file
`schema_version` 2, with a backup and migration from v1. `profiles` maps names to rules; `assignments` maps a registered device id to a profile name (old `GUID#occurrence` keys stay readable). `known_devices` remembers discovered controllers. `game_mode_auto`, `games` and `non_games` drive game mode. `language` is `auto` or a language code; `theme` is `comfy_turquoise`, `danger_red` or `midnight_blue`; `controller_style` is `eye_candy`, `dark`, `light` or `original`. `browser_token` is generated on first launch: never publish a settings file containing it. `config/example-settings.json` shows the defaults.

## Environment variables
- `PAWZ_DATA_DIR`: settings folder (isolates a test configuration).
- `PAWZ_VENV_DIR`: Python environment used by the scripts.
- `PAWZ_MAGNET_TRACE`: path of a magnetism trace (below).
- `PAWZ_SMOKE_REPORT`: used by the build check; starts, writes a report and quits. Do not set it otherwise.
- `PAWZ_VISUAL_TESTS=1`: enables the pixel comparisons.

## Diagnosing magnetism
Set `PAWZ_MAGNET_TRACE` to a file path before starting pawz, for example `$env:PAWZ_MAGNET_TRACE = "$env:TEMP\pawz-magnet.jsonl"` then `scripts\run-windows.ps1`. Every magnetized move is written as one JSON line per tick: position, requested move, targets seen and kept, any warp, and the step actually sent. The first line describes the environment (thread DPI awareness, pointer speed and acceleration). The file is capped at 20,000 lines and never contains keystrokes.

## Security and technical limits
- No arbitrary shell command can be bound; `key_combo` only accepts known keys.
- The HTTP API only listens on `127.0.0.1`, requires the token and limits request size.
- The extension sends the full active tab address locally; only the domain is used, and addresses are not stored.
- Injected input carries a tag (`INPUT_TAG`, "PAWZ") in `dwExtraInfo`, so hooks can recognize it.
- Windows drops input sent to elevated windows by a non-elevated process (UIPI). pawz is not a service and does not work on the logon screen or UAC prompts.

## Validation still to do on hardware
- Real Windows commands, long presses, triggers and axes in target applications, browser contexts, and USB/Bluetooth reconnections, on each controller model.
- SDL names, GUIDs, drivers and extra buttons: no definition claims to be verified, and no GUID or raw index was invented.
- Calibration captures sources only; check raw triggers resting at −1 and combined axes in particular.
- Visual comfort at target screen sizes and with several monitors of different DPI.
