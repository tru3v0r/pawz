# Controllers, mappings and profiles

Settings have five tabs: **GENERAL**, **DISPLAY**, **PROFILES**, **CONTROLLERS** and **ABOUT**. Profile and device changes apply with **Save** and are discarded with **Close**. Explicit operations on the custom catalogue (duplicate, edit, delete a model) are saved immediately, in their own file.

## Profiles

A profile maps logical button positions (`SOUTH`, `EAST`, `WEST`, `NORTH`, …) to actions. It holds its shortcuts per application and per domain, its combinations and layers, and its pointer, scroll and magnetism settings. The built-in profile has a protected identifier: even renamed, it cannot be deleted. A copy gets a new identifier and stays independent.

The **+** after the profile buttons adds a profile, copied from an existing one. **Show buttons of** only changes how shortcuts are drawn, and shows that controller beside the picker: `SOUTH` shows as A for Xbox and B for Nintendo. Actions and hardware inputs do not change. The pencil opens the editor of a shortcut (logical buttons, action, keys, application or site condition), which can also capture a combination on a connected controller. The cross removes the shortcut.

## Devices

In **CONTROLLERS**, **Known controller** picks a registered device (one pawz has already seen; the rest of the page applies to it); the pencil beside it jumps to its custom name. **Model used** picks the catalog model that describes it (identification, mappings, drawing). **Use this model for this controller** remembers the choice; when the selected model is already the one in use, it is disabled and reads "✓ This model is already used for this controller". A custom name is independent of the detected one, which shows greyed while the name is empty: a Battletron detected as a Nintendo Switch Pro can keep that model and a Battletron name.

Detection tries, in order: a model chosen by hand, a GUID listed in a definition, the USB vendor and product ids that SDL encodes in the GUID (for example `057e:2009` for a Switch Pro), the exact model name, then fragments of the SDL name (`Xbox 360`, `PS4`, `Pro Controller`, `Joy-Con`…). The USB ids and name fragments are in `src/pawz/data/controllers/identification.json`, the icons drawn for each input in `prompts.json` next to it. Controllers seen only through XInput carry no USB ids and are named `XInput Controller`: they stay generic until a model is chosen. Bundled definitions are presentation models: they claim no hardware GUID and no verified status. The installed SDL provides the hardware mapping of recognized controllers. Name-based detection is only a hint; choose the model by hand when needed.

**Add a mapping…** edits a per-device JSON override. Keys are logical names; values are raw SDL sources: `b0` (button), `a1` (axis), `+a1` / `-a1` (half axis), `h0.1/2/4/8` (hat up/right/down/left). Indices belong to the hardware: use calibration rather than guessing them from another controller.

**Calibrate…** reads the real controller. Choose the logical input, release every control, click **Capture this input**, then actuate it. Repeat for the controls you need and save. Mouse and keyboard output is suspended during capture. Triggers stay analog axes; a 0.5 threshold also lets them act as buttons. Calibration does not yet handle axis inversion, ranges or dead zones.

## Illustrations

Each named model has an illustration, from the Gamepad Asset Pack when it has the controller (see [Assets](ASSETS.md)), shown in **CONTROLLERS**, in **PROFILES** and on the main window. The identification table shows the drawing with its buttons, then manufacturer, model, family, SDL GUID (with a copy button), status and the custom name. Mappings show button icons in the physical label column; X/Y axes have their own symbols. Full labels stay available as tooltips and for accessibility.

Shortcut buttons use the bundled Gamepad Prompt Asset Pack SVGs, matching the chosen model.

Under the drawing, **Calibrate…** opens the calibration (above) and **Name inputs…** the naming window (below); **Change illustration…** lists every bundled drawing and your imported ones with a preview, and can import one too; **Import custom…** imports your own valid SVG (4 MB maximum); **Restore default** goes back to the model's drawing. Imports are copied to the settings folder; preferences store relative `asset:` / `user:` references.

## Naming inputs

The main window lights up held buttons where they are drawn when the drawing names them: an element (or Inkscape layer) whose `id` is the logical input, such as `SOUTH`, `LEFT_TRIGGER`, `LEFT_STICK` or `DPAD` (any case, `pawz-` prefix allowed). Fingers on a touchpad are drawn on `TOUCHPAD` (a click lights it up too); a controller with two pads (Steam Controller, Steam Deck) uses `LEFT_TOUCHPAD` and `RIGHT_TOUCHPAD`. Inputs it cannot place appear in a medallion at the drawing's bottom-right corner while they are held (round for one, longer for several; a touchpad contact as a small pad with its fingers): the drawing itself never changes.

**Name inputs…** shows the drawing in its own colours: click a button, stick or trigger, then pick its input. The element gets that name as its `id` and as its Inkscape layer name; only those attributes change in the file. A cross drawn as one shape can be named `DPAD`: each direction then lights up its arm, the cross being split in thirds (an arm is 36 % of its width).

- Imported drawings are renamed in place.
- Bundled drawings stay untouched: the renamed copy goes to `%APPDATA%\pawz\artwork\` and is used instead. For Gamepad Asset Pack files, a second copy goes to `%APPDATA%\pawz\asset-pack-names\` at its path in that repository (`Connection Icon Pack/Controller Type/SVG/…`), ready for a pull request.
- pawz ships named copies of eight silhouettes and of every detailed drawing, whose shoulders and triggers light up too (see [Assets](ASSETS.md)), so the live display works without naming anything. On the Xbox One and Series drawings the bumpers are part of one shared outline, so LB/RB cannot light up there.
- Detailed drawings have no asset-pack copy for pull requests: their stored files lack the upstream logos, so it would not be a names-only change.

**Auto-detect** guesses the inputs from the positions and sizes of the elements and shows a confidence percentage for each. Names you chose by hand are kept; a manual change replaces a guess.

## Auto-detect rules

The rules are data, not code: `src/pawz/data/controllers/auto-detect.json`. A copy at `%APPDATA%\pawz\auto-detect.json` is used instead when present, to experiment without touching the project. The file holds:

- `min_confidence`: guesses below this percentage are dropped;
- `body`: shapes larger than `max_size` (the body, outlines) or smaller than `min_size` (specks) are ignored;
- `rules`: run in order; each one only sees elements no earlier rule took.

Positions are fractions of the box around all shapes (`x` 0 left to 1 right, `y` 0 top to 1 bottom); sizes are fractions of its width. Each rule has an `id`, a `type`, its thresholds, the inputs it assigns (`inputs` or `input`), a `confidence` (the best it can claim, 0 to 1) and a `comment`. Its score (how well the geometry fits, 0 to 1, each criterion falling linearly to 0 at its tolerance) times its `confidence` gives the percentage.

| Type | Finds | Main parameters |
|---|---|---|
| `labels` | layers the artist named ("ZR Trigger", "L Bumper", "X Button"): the most reliable rule, so it runs first | `patterns` (input → regular expression on the whole layer name, case-insensitive; the first match names a layer); `family_patterns`, checked first, for words that mean different inputs per brand ("Share" is Back on a PlayStation pad, the capture button on an Xbox); `face_letters` per family (`nintendo`, `xbox`, `playstation`, `generic`) and `face_pattern`, since a printed letter means a different position on each family; `stop_if_named`: once that many inputs are named, only the rules in `still_run` follow, so geometry adds no wrong guesses to a well-named drawing |
| `diamond` | four shapes left/right/top/bottom around one centre: face buttons, d-pad arrows | `region`, `shape` (`round`, `not-round`, `any`), `max_size`, `size_tolerance`, `alignment_tolerance`; `mirror_of` (a rule id), `mirror_tolerance`, `mirror_y_tolerance` to require the mirror image of another group; `inputs` by `left`/`right`/`top`/`bottom` |
| `sticks` | the right stick (right half, nearest the face buttons) and the left one (left half, same size; mirror symmetry is a bonus) | `face_ratio` (size range in face-button sizes), `shape`, `size_tolerance`, `mirror_tolerance`, `inputs` by `right`/`left` |
| `mirror` | one shape where a reference would be, mirrored left-right: a one-piece d-pad | `mirror_of` (inputs or rule ids, tried in order), `region`, `face_ratio`, `tolerance`, `prefer_shape`, `input` |
| `top_pairs` | wide shapes mirrored at the top of the drawing, topmost first: triggers (behind), then bumpers; a single pair is taken for the bumpers | `region`, `min_aspect` (width / height), `tolerance`, `pairs` |
| `centre_pairs` | shapes mirrored around the centre line, widest pair first: Back/Start, Misc/Guide, and the two trackpads of a Steam Controller | `region`, `face_ratio`, `shape`, `tolerance`, `pairs` (a list of `[left, right]` inputs) |
| `centre_single` | one shape on the centre line: Guide, a touchpad | `region`, `face_ratio` or `min_width`/`max_width`, `max_aspect`, `shape`, `tolerance`, `input` |

`face_ratio` sizes are relative to the face buttons the first `diamond` rule found (the `face-buttons` rule). Name inputs passes the model's family, so the `labels` rule can read printed letters. A new kind of pattern needs a new rule type in `src/pawz/engine/auto_detect.py`; new rules of the existing types only need the JSON. `tests/test_auto_detect.py` runs the rules on the bundled silhouettes: the Switch Pro result must match the names given by hand.

Artwork is resolved in this order: the device's own choice, the model's drawing, its family's, the generic one. For a bundled drawing, a copy with named inputs is used when there is one: yours in `%APPDATA%\pawz\artwork\`, then the one shipped with pawz. A disconnected device keeps a dimmed drawing. **Forget** removes its settings, mapping and profile assignment.

## Saving and identity

Migrating `settings.json` from v1 to v2 first writes `settings.json.v1.bak`. Actions and contexts are kept, and old button names become logical identifiers. Unknown versions are refused.

A GUID identifies a type of hardware, not a physical device. Each connection uses its SDL instance id, so identical controllers stay distinct during a session, even when one is unplugged. Without an accessible serial number, telling apart identical controllers after reconnection cannot be guaranteed: registered slots are reused on a best-effort basis, so check their names and profiles.

Compatible controllers often present themselves exactly as the original: a Battletron (sold by Action) reports Nintendo's USB ids and the Bluetooth name "Pro Controller", so pawz shows it as a Switch Pro and cannot tell it apart. Give it a custom name, or duplicate the Switch Pro model, rename it, set its manufacturer and use it for that controller. Controllers SDL does not recognise use the generic definition and calibration. A model being listed does not guarantee that the installed pygame/SDL supports all its extra buttons.
