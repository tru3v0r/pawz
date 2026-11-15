# pawz — User guide

The interface is available in 30 languages: Bahasa Indonesia, Bengali, Chinese (Simplified and Traditional), English, Filipino, Finnish, French, German, Hindi, Italian, Japanese, Kabyle, Korean, Kurdish (Kurmanji and Sorani), Modern Standard Arabic, Norwegian Bokmål, Polish, Portuguese (Brazil and Portugal), Russian, Spanish (Spain and Latin America), Standard Moroccan Amazigh (Tifinagh), Swedish, Thai, Turkish, Ukrainian and Vietnamese. Arabic and Sorani Kurdish are laid out right to left. This guide quotes the English labels.

## Requirements
- Windows 10 or 11 (64-bit). Python 3.12 is only needed to run from source or build the executable.
- A controller supported by **SDL GameController**, over USB or Bluetooth. Face buttons are read by position, so a Nintendo controller behaves like the others: its right button (A) is `EAST`, its bottom button (B) is `SOUTH`.

## Installation
1. Get the repository (`git clone`, then `git pull` to update).
2. In PowerShell, at the repository root: `powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1`.
3. Run `dist\pawz\pawz.exe`. The `dist\pawz` folder is **portable**: keep every file next to the executable.
4. pawz stays in the notification area; double-click its icon to open the configuration. **Quit** in its menu stops it.

Settings are stored in `%APPDATA%\pawz\settings.json`. On first launch, settings left by squidz (the previous name of the app) are copied from `%APPDATA%\squidz`.

## Default controls
Button names below are those printed on a Nintendo controller; the position is given in brackets.

| Control | Action |
|---|---|
| Left stick | Move the pointer |
| Right stick, vertical | Scroll |
| Right stick, sideways | Free for shortcuts ("right stick left" / "right stick right"), once per push |
| Right stick click | Middle click |
| A (right) / B (bottom) | Left / right click (hold A to drag) |
| X (top) / Y (left) | Copy / paste (Ctrl+C / Ctrl+V) |
| D-pad | Arrow keys |
| L / R | Previous / next page |
| L / R in Firefox, Chrome, Edge or Brave | Previous / next tab |
| Y (left) / X (top) on YouTube and in VLC | Play-pause (Space) / full screen (`F`) |
| Left stick click on YouTube / in VLC | Subtitles (`C` on YouTube, `V` in VLC) |
| Right stick pushed left / right on YouTube and in VLC | Jump back / forward (← / →), once per push |
| − / + | Volume down / up |
| HOME | Windows key |
| HOME held 0.8 s (primary controller) | Open pawz |
| − and + together | Toggle game mode |
| ZL held, then B / A / X / Y | Undo / redo / cut / select all |
| ZL held, then + / − | Save (Ctrl+S) / Backspace |
| ZL held, then the D-pad | Select (Shift + arrow) |

The Windows on-screen keyboard does not open automatically: use `Win` + `Ctrl` + `O`.

## Main window
- Slots show connected controllers and known, disconnected ones. Use the side arrows when they do not all fit.
- The crown, standing on top of the drawing, marks the primary controller, the one allowed to open pawz. With a single controller it becomes primary automatically; otherwise click **SET PRIMARY**.
- Battery level and assigned profile appear under each connected controller. Values marked `~` are estimates: SDL only reports a coarse level (low, medium, full).
- While the window is open, each connected controller shows its held buttons, moved sticks and fingers on its touchpad (DualShock 4, DualSense, and others SDL reports touchpads for). When its drawing names its inputs (an element or layer with the logical name as its id, such as `SOUTH`, `LEFT_TRIGGER` or `LEFT_STICK`), they light up where they are drawn; those the drawing does not show appear in a small medallion at its bottom-right corner while they are held.
- **Forget**, under a disconnected controller, removes its name, mapping and profile assignment after confirmation.
- **Manage profiles** opens the profiles tab of **Settings**.

## Settings
Settings have five tabs: **GENERAL**, **DISPLAY**, **PROFILES**, **CONTROLLERS** and **ABOUT**. Changes apply with **Save**; **Close** discards them.

### General
- **Launch at startup** registers pawz at logon; **Minimized to the taskbar** starts it minimized.
- **Default assigned profile** is used by controllers without a specific assignment.
- **Game mode**: see below.
- **Debug**: the debug window lists input events from five independent sources (SetWindowsHookEx, SetWinEventHook, UI Automation, Raw Input, ETW). Sources are off by default and show event types only, never keystroke contents. ETW asks for UAC elevation; its temporary traces are deleted when the source stops.

### Display
- **Interface language**: **Automatic (Windows language)** uses the Windows display language when pawz has a translation for it, and English otherwise. Regional varieties follow the Windows region: Spanish from Spain or Latin America, Portuguese from Brazil or Portugal, Simplified or Traditional Chinese, and Kurdish in Sorani for Iraq and Iran (Kurmanji otherwise). Apart from French, the translations are machine translations no native speaker has reviewed yet: the list shows each one's estimated quality (Excellent, Very good, Good, Fair or Fragile), and choosing a language says how its translation is rated, with a link to the GitHub repository for speakers who can improve it.
- **Color scheme**: **Comfy Turquoise** (default), **Danger Red**, **Juicy Orange** and **Cheeky Green** (bright red, orange and green), **Squishy Purple** (dark, with bright purple outlines) or **Corporate Blue**, the original dark blue look.
- **Controller style**, how controllers are drawn, in the theme's colours: **Eye Candy** (default: dark body, buttons in the button colour, outlined), **Dark**, **Light**, or **Original** (the artwork's own black and white). It applies at once, in the settings too.
- The color scheme list shows a sample of each scheme's main colours next to its name.
- The color scheme and controller style apply at once while you browse them; **Close** without saving goes back to the previous ones. The language applies when pawz restarts: after saving a change, pawz offers to restart right away.

### Profiles
- The **+** after the profile buttons adds a profile; the other buttons duplicate, rename and delete the selected one.
- **Show buttons of** draws shortcuts with another controller's buttons, shown beside it.
- Shortcuts are grouped by priority: **General**, then per application, then per website; the most specific wins.
- **Add an application...** picks an `.exe`, portable ones included; VLC gets the video shortcuts above. Adding a website asks for a domain such as `youtube.com`; website shortcuts need the browser extension (below), as the **Websites** section reminds.
- Click a shortcut's controller buttons to capture new ones: press one or several buttons at once; the combination is recorded when one is released.
- The pencil edits a shortcut (buttons, action, keys, context); the cross removes it.

#### Sensitivity
- **Mouse**: pointer speed. **Scroll wheel**: scroll speed. **Dead zone**: stick dead zone.
- **Magnetism**, 10 to 100 %: see below.

### Controllers
Controller models, mappings, calibration, illustrations, naming inputs and Auto-detect: see [Controllers, mappings and profiles](CONTROLLERS.md).

### About
The version, the licence and the credits: the controller drawings and button icons come from the Gamepad Asset Pack and Gamepad Prompt Asset Pack by Al. Lopez (AL2009man).

## Magnetism
Magnetism draws the pointer to resizable window edges, to window caption buttons (minimize, maximize, close) and to desktop icons.

- **Capture.** Approaching a target captures the pointer. On an edge it stops exactly where the window can be resized; on a button or icon, at its centre. Fixed-size and maximized windows have no magnetic edges.
- **Escape.** Push the stick for a moment to leave: at full deflection about 0.15 s at 25 %, 0.23 s at 50 % and 0.4 s at 100 %, longer with a light push. The effort does not depend on the pointer speed. The pointer then lands just outside the target's reach.
- **Gliding.** On an edge, movement along the edge stays free.
- **Spatial navigation.** On a caption button, a sideways push jumps straight to the neighbouring button, centred, without effort; holding the push moves on every 0.3 s. Held on the right edge near the top, pushing left jumps to the rightmost button; held on the top edge near the right, pushing down jumps to the closest button.

Options:
- **Automatic** (on by default): magnetism is always active. Off, it only works while the right trigger (ZR, RT or R2) is held.
- **Include background windows**: edges and buttons of visible windows behind the active one attract too, except where they are covered. Off, only the active window counts, plus desktop icons when the desktop is active.
- **Vibrate on capture and release** (on by default): a short, light rumble on each capture, jump and release, on controllers with motors.

## Editing layer (ZL)
Hold ZL **then** press a button to use its editing function (see the table above). Without ZL, buttons keep their normal function and react immediately: holding A still drags. Pressing ZL after a button changes nothing for that button. These shortcuts appear in the profile as combinations with ZL and can be edited like any other.

## Game mode
In game mode pawz sends nothing: no pointer, clicks, shortcuts, nor HOME long press. The controller is left to the game; only − and + together stay active, to leave it.

- **Automatic for full-screen applications** (on by default) enters game mode when an application covers exactly the whole screen. A merely maximized window does not count. Browsers, video players and the desktop never do, so full-screen videos stay controllable.
- **Always in game mode** and **Never in game mode** take executable names separated by commas, such as `eldenring.exe`: windowed games, or full-screen applications that are not games.
- − and + together toggle game mode by hand for the application in front, with a rumble: long when entering, short when leaving. The choice holds while that application stays in front.
- A click held when the mode changes is released; buttons still held do nothing when released.
- The notification icon's tooltip reads **pawz — game mode**.

## Browser extension (per-website shortcuts)
Per-website shortcuts need the extension in `browser-extension/`.

1. Open `%APPDATA%\pawz\settings.json` and copy the `browser_token` value.
2. Chrome, Edge or Brave: open the extensions page (`chrome://extensions`, `edge://extensions`, `brave://extensions`), enable developer mode, **Load unpacked** and select `browser-extension`.
3. Firefox: `about:debugging#/runtime/this-firefox` → **Load Temporary Add-on** → choose `manifest.json`. A temporary add-on must be loaded again after a restart; a permanent install needs a signed extension.
4. In the extension options, paste the token (and the port if you changed it) and save.
5. Keep pawz running. The extension only sends the active tab's address to `127.0.0.1` (port 8765 by default); only the domain is used.

The extension's options page follows the browser's language. It is translated into every language of pawz that browsers support, all of them but Amazigh, Kabyle and Kurdish, which show it in English.

After the rename from squidz, the extension must be loaded again and the token pasted again: its identifier and its header changed.

## Known limitations
- The active domain follows the last active tab the browser reported; several windows or profiles of the same browser at once can give a wrong context.
- YouTube shortcuts (Space, `F`, `C`) need the page to handle them, with no text field focused.
- Buttons and axes depend on the SDL mapping; a controller SDL does not recognize needs a mapping or calibration (see [Controllers](CONTROLLERS.md)).
- Windows ignores input sent to administrator windows by a non-elevated app, and pawz does not work on the logon screen or UAC prompts.
- In game mode pawz stops sending input, but does not prevent Windows or Steam from reading the controller.
