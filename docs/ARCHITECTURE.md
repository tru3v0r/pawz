# Architecture

## Boundaries

- `core/controller_inputs.py` defines the positional names and the explicit mapping of SDL2 buttons and axes to them. pygame 2.6.1 ships SDL 2.28.4; no SDL3 constant is assumed. SDL is told to report Nintendo face buttons by position, not by printed label (`SDL_GAMECONTROLLER_USE_BUTTON_LABELS=0`, set in `pawz/__init__.py` before SDL starts).
- `core/controller_catalog.py` loads resources through `importlib.resources`, validates the catalogue with JSON Schema, protects built-in models and writes the user catalogue atomically.
- `core/controller_services.py` resolves models, tracks connection instances, validates and reads raw mappings, and captures changes for calibration. It knows neither Qt nor Windows actions.
- `core/controllers.py` uses SDL GameController first. A model's raw mapping completes or replaces SDL; a per-device override wins over the model. Unknown joysticks are kept for calibration, with no assumed indices.
- `core/models.py` holds profiles and their protected operations.

## Threads

`InputThread` (a `QThread`) owns SDL/pygame, polls controllers at 250 Hz (20 Hz with none connected) and injects input, so pointer smoothness does not depend on the Qt event loop. It only reads a copy of the settings (`ControllerManager.config`), republished by the Qt thread every 250 ms and after each hardware change. Device discoveries come back through a queued signal and are written to `settings` by the Qt thread only. A lock serializes polling and input capture. `stop()` releases every held mouse button. Time steps use `time.perf_counter()`: `time.monotonic()` only advances in ~15.6 ms steps on Windows. Each poll also publishes `live_state` per device (held buttons, raw stick axes, touchpad contacts read from SDL's `CONTROLLERTOUCHPAD*` events) by replacing whole values, which the main window reads about 30 times a second while it is visible.

## Actions and output

`engine/actions.py` describes each action once: label, held mouse button, fixed or free key combination, or internal action (open the settings, toggle game mode). Settings validation, the profile editor, the gesture engine and execution all read this catalogue. Execution goes through an `OutputSink` (clicks, key combinations, pointer, wheel), implemented for Windows by `WindowsOutput` and replaced by a fake in tests.

`infra/windows.py` injects with `SendInput`: a key combination is sent as one batch, so it cannot interleave with other input. Each input carries `INPUT_TAG` in `dwExtraInfo`.

## Gestures and layers

`engine/gestures.py` is the per-device gesture state machine: press, release, held click, combinations, layers, long press and capture. It is pure and returns effects (`Dispatch`, `MouseDown`, `MouseUp`, `CaptureInput`, `LongPress`) that `ControllerManager` executes. Its rules are documented in the module and table-tested in `tests/test_gestures.py`:

- a button bound to a click holds the mouse button from press to release;
- an ordinary combination defers its buttons until release;
- a combination that includes a layer button (`LAYER_BUTTONS`, ZL) only fires when the layer button is already held as the other goes down, and never defers that other button used alone;
- `release_clicks()` lets go of held clicks and makes held buttons inert (used when game mode changes).

## Game mode

`engine/game_mode.py` decides: a manual toggle wins while the same application stays in front; then the always/never lists (plus browsers, video players and the desktop, never games); then, if automatic mode is on, a window covering exactly its monitor (a maximized window overflows it and does not count). `ControllerManager` checks every 250 ms; in game mode it only executes the `game_mode` action.

## Magnetism

`engine/magnet.py` is pure: approach (pull per second), capture within the snap radius, hold with an escape threshold expressed as a push duration, glide along edges, release just outside the capture zone without immediate recapture, and spatial navigation (sideways jumps between points of one group, the caption buttons of a window, and from an edge to a button within `NAV_REACH`).

`infra/window_targets.py` collects targets. Each window is hit-tested with `WM_NCHITTEST`, as Windows does to choose the cursor shape, to find the exact resize line of each edge (none for fixed-size or maximized windows) and the real centre of caption buttons, custom-drawn title bars included. Probing runs on a worker thread and is cached per window, relative to its rectangle; a window that does not answer (elevated, hung) is estimated from its style and DWM bounds. Desktop icons are read on the same worker. With background windows included, every visible window counts and each target is kept only where its window is on top (`WindowFromPoint`). `infra/windows.py` applies the decision; capture and release events trigger a rumble on the controller that moved the pointer.

## Persistence (v2)

`settings.json` keeps separate sections: `profiles`, `assignments`, `known_devices`, `controller_mappings`, `device_preferences`, `display_controller_model`, the game mode options and the display options (`language`, `theme`, `controller_style`), in a single atomic write so profile renames and assignments never get out of sync. The settings folder also holds the custom catalogue (`controllers/catalog.json`, separate from the immutable built-in one), imported illustrations (`illustrations/`), drawings renamed with Name inputs (`artwork/`, plus `asset-pack-names/` for pull requests) and, optionally, the user's Auto-detect rules (`auto-detect.json`).

`PAWZ_DATA_DIR` isolates a test configuration; otherwise the folder is `%APPDATA%/pawz`, copied from a previous app name on first launch. v1 settings are backed up before migration; migrated profile ids are deterministic and later migrations are idempotent. Legacy button names are accepted when reading, and logical names are written. The built-in profile is protected by `SYSTEM_DEFAULT_PROFILE_ID`, even after a rename; a deep copy gets a new UUID; duplicate ids and duplicate shortcuts after normalization are refused.

## Hardware identity

An in-memory table `SDL instance → registered id` tracks connected devices. A new instance reuses, when possible, a free slot with a matching GUID; otherwise it gets a UUID. Old `GUID#occurrence` keys stay readable. The GUID alone is never an input-state key. pygame exposes no universal serial number, so identical devices can be ambiguous after reconnection or restart.

## Controller artwork

`controller_assets.resolve_artwork()` picks the device's choice, the model's drawing, its family's or the generic one; a bundled drawing is replaced by its named copy when there is one (the user's in the settings folder, then `controllers/named/`). `artwork_bytes()` styles bundled drawings (`artwork_styles`, in the current theme), cached per file, style and theme. The main window finds named elements (`id` = logical input) with `QSvgRenderer.boundsOnElement` and lights pressed inputs there, painting the element again in its exact shape tinted with the accent; a d-pad named as one block lights the arm of the pressed direction; inputs it cannot place are drawn between the grips. Prompt icons in the mappings table are painted by `PromptDelegate`, not cell widgets, which Qt only places for visible rows.

`engine/auto_detect.py` turns element bounds into shapes relative to the box around all of them and applies the rules of `data/controllers/auto-detect.json`; `ui/artwork_editor.py` renames elements in the file's text, so only `id` and `inkscape:label` change.

## Catalogue and sources

19 presentation definitions ship (the generic one included), all unverified, with no invented GUID or index. Names and labels are for display; SDL decides actual compatibility. References: <https://github.com/libsdl-org/SDL/blob/SDL2/include/SDL_gamecontroller.h> and <https://github.com/mdqinc/SDL_GameControllerDB>. The database built into SDL/pygame is the mapping actually used; nothing is downloaded at startup.

## Visual tests and build check

`PAWZ_VISUAL_TESTS=1` enables exact pixel comparisons of seven scenes at three Qt scale factors (1, 1.25, 1.5). `tests/visual_scene.py` uses deterministic scene data for the captures only. Captures depend on the Qt version, renderer and fonts: they are references inspected for this environment, not a design approval. To check native rendering, run the script with `QT_QPA_PLATFORM=windows` and each `QT_SCALE_FACTOR`.

`scripts/build-windows.ps1` stops on any native error; `scripts/test-build-windows.ps1` starts the executable with isolated settings and checks the catalogue, schema, SVGs and fonts. Its report contains no token.
