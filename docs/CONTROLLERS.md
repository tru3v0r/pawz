# Controllers, mappings and profiles

Settings have three tabs: **GENERAL**, **PROFILES** and **CONTROLLERS**. Profile and device changes apply with **Save** and are discarded with **Close**. Explicit operations on the custom catalogue (duplicate, edit, delete a model) are saved immediately, in their own file.

## Profiles

A profile maps logical button positions (`SOUTH`, `EAST`, `WEST`, `NORTH`, …) to actions. It holds its shortcuts per application and per domain, its combinations and layers, and its pointer, scroll and magnetism settings. The built-in profile has a protected identifier: even renamed, it cannot be deleted. A copy gets a new identifier and stays independent.

**Show buttons of** only changes how shortcuts are drawn: `SOUTH` shows as A for Xbox and B for Nintendo. Actions and hardware inputs do not change. The pencil opens the editor of a shortcut (logical buttons, action, keys, application or site condition), which can also capture a combination on a connected controller. The cross removes the shortcut.

## Devices

In **CONTROLLERS**, pick a registered device, then a model; **Use this model for this controller** remembers the choice. A custom name is independent of the detected one: a Battletron detected as a Nintendo Switch Pro can keep that model and a Battletron name.

Detection compares documented GUIDs and exact names. Bundled definitions are presentation models: they claim no hardware GUID and no verified status. The installed SDL provides the hardware mapping of recognized controllers. Name-based detection is only a hint; choose the model by hand when needed.

**Add a mapping…** edits a per-device JSON override. Keys are logical names; values are raw SDL sources: `b0` (button), `a1` (axis), `+a1` / `-a1` (half axis), `h0.1/2/4/8` (hat up/right/down/left). Indices belong to the hardware: use calibration rather than guessing them from another controller.

**Calibrate…** reads the real controller. Choose the logical input, release every control, click **Capture this input**, then actuate it. Repeat for the controls you need and save. Mouse and keyboard output is suspended during capture. Triggers stay analog axes; a 0.5 threshold also lets them act as buttons. Calibration does not yet handle axis inversion, ranges or dead zones.

## Illustrations

Each named model has its own SVG illustration, shown in **CONTROLLERS** and on the main window. The identification table shows manufacturer, model, family, SDL GUID and status. Mappings show button icons in the physical label column; X/Y axes have their own symbols. Full labels stay available as tooltips and for accessibility.

Shortcut buttons use the bundled Gamepad Prompt Asset Pack SVGs, matching the chosen model. You can pick a bundled SVG, import your own valid SVG (4 MB maximum) or restore the default. Imports are copied to the settings folder; preferences store relative `asset:` / `user:` references.

Artwork is resolved in this order: device, model, family, generic. A disconnected device keeps a dimmed drawing. **Forget** removes its settings, mapping and profile assignment.

## Saving and identity

Migrating `settings.json` from v1 to v2 first writes `settings.json.v1.bak`. Actions and contexts are kept, and old button names become logical identifiers. Unknown versions are refused.

A GUID identifies a type of hardware, not a physical device. Each connection uses its SDL instance id, so identical controllers stay distinct during a session, even when one is unplugged. Without an accessible serial number, telling apart identical controllers after reconnection cannot be guaranteed: registered slots are reused on a best-effort basis, so check their names and profiles.

8BitDo, Battletron, Switch 2 and other unidentified controllers use SDL / generic definitions and calibration. A model being listed does not guarantee that the installed pygame/SDL supports all its extra buttons.
