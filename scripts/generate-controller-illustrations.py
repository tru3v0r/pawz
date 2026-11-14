"""Rebuild original, logo-free controller illustrations and axis symbols.

Only models without a Gamepad Asset Pack silhouette (``library/`` in the catalogue)
get a drawing: the Xbox Adaptive Controller and the Logitech F310/F510/F710.

These are stylized drawings for pawz, not manufacturer artwork or evidence of
hardware verification. They never contain raw input mappings or device GUIDs.
"""
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src/pawz/ui/assets/controllers"
CATALOG = ROOT / "src/pawz/data/controllers/catalog.json"


def text(x, y, value, size=15, color="#edf4fc"):
    return (f'<text x="{x}" y="{y}" text-anchor="middle" font-family="Inter 18pt" '
            f'font-size="{size}" font-weight="600" fill="{color}">{escape(value)}</text>')


def stick(x, y, r=21):
    return (f'<circle cx="{x}" cy="{y}" r="{r+5}" fill="#101923" stroke="#788a9f" stroke-width="1.5"/>'
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="#283441" stroke="#0b131d" stroke-width="3"/>'
            f'<circle cx="{x}" cy="{y}" r="{r-5}" fill="#202b37" stroke="#526479" stroke-width="1"/>')


def dpad(x, y, size=1):
    return (f'<g transform="translate({x} {y}) scale({size})">'
            '<path d="M-8-23h16v15h15V8H8v15H-8V8h-15V-8h15z" '
            'fill="#263441" stroke="#0c1520" stroke-width="3" stroke-linejoin="round"/>'
            '<path d="m0-17-4 5h8zm17 17-5-4v8zM0 17l4-5h-8zM-17 0l5 4v-8z" fill="#91a1b3"/></g>')


def faces(x, y, family, scale=1):
    labels = ("B", "A", "Y", "X") if family == "nintendo" else ("A", "B", "X", "Y")
    colors = ("#53d587", "#f48087", "#55c3ff", "#f0d668")
    parts = [f'<g transform="translate({x} {y}) scale({scale})">']
    for index, (dx, dy) in enumerate(((0, 24), (24, 0), (-24, 0), (0, -24))):
        color = "#e3ecf4" if family == "nintendo" else colors[index]
        parts.append(f'<circle cx="{dx}" cy="{dy}" r="14" fill="#182430" stroke="#748598" stroke-width="1.3"/>')
        if family == "playstation":
            color = ("#81a5f5", "#ed9ca1", "#e3a2d4", "#70d3bc")[index]
            if index == 0:
                path = f'<path d="m{dx-5} {dy-5} 10 10m0-10-10 10"/>'
            elif index == 1:
                path = f'<circle cx="{dx}" cy="{dy}" r="6"/>'
            elif index == 2:
                path = f'<rect x="{dx-5}" y="{dy-5}" width="10" height="10"/>'
            else:
                path = f'<path d="m{dx} {dy-7} 7 12h-14z"/>'
            parts.append(f'<g fill="none" stroke="{color}" stroke-width="1.7" stroke-linejoin="round">{path}</g>')
        else:
            parts.append(text(dx, dy+5, labels[index], 14, color))
    return "".join(parts) + "</g>"


def menu(x, y):
    return (f'<circle cx="{x-21}" cy="{y}" r="6" fill="#394c60"/>'
            f'<circle cx="{x+21}" cy="{y}" r="6" fill="#394c60"/>'
            f'<circle cx="{x}" cy="{y+17}" r="9" fill="#445b73" stroke="#92a7bf" stroke-width="1"/>')


def shoulders(color="#253747"):
    return (f'<path d="M78 58q20-20 66-9l-3 18H77zM276 49q46-11 66 9l1 9h-64z" '
            f'fill="{color}" stroke="#8291a1" stroke-width="2"/>')


def gamepad(model):
    mid, family = model["id"], model["family"]
    sony = family == "playstation"
    dualsense = "dualsense" in mid
    is_360 = mid == "microsoft.xbox-360"
    light = is_360 or mid == "microsoft.xbox-one-s" or dualsense or mid == "logitech.f710"
    body = "#e1e7ed" if light else "#334556" if mid.startswith("logitech") else "#283744"
    if mid == "logitech.f310":
        body = "#23719a"
    if mid == "microsoft.elite-1":
        body = "#39424a"
    elif mid == "microsoft.elite-2":
        body = "#1c2c39"
    elif mid == "nintendo.switch-pro":
        body = "#49545d"
    shape = ("M82 60Q60 54 49 80L25 185Q20 215 43 221Q61 227 82 204L129 169"
             "Q147 156 172 159H248Q273 156 291 169L338 204Q359 227 377 221Q400 215 395 185"
             "L371 80Q360 54 338 60Q286 45 260 56H160Q134 45 82 60Z")
    if sony and not dualsense:
        shape = ("M78 62Q54 60 48 87L27 185Q23 214 43 219Q61 224 79 205L120 161"
                 "H300L341 205Q359 224 377 219Q397 214 393 185L372 87Q366 60 342 62"
                 "L282 53H138Z")
    if is_360:
        shape = ("M88 55Q62 50 51 82L24 180Q13 215 37 224Q60 233 83 205L132 164"
                 "Q153 155 178 161H242Q267 155 288 164L337 205Q360 233 383 224"
                 "Q407 215 396 180L369 82Q358 50 332 55Q278 36 252 57H168Q142 36 88 55Z")
    elif mid == "nintendo.switch-pro":
        shape = ("M87 51Q59 43 48 78L25 182Q20 215 43 225Q61 232 83 211L134 162"
                 "H286L337 211Q359 232 377 225Q400 215 395 182L372 78Q361 43 333 51"
                 "Q288 44 259 55H161Q132 44 87 51Z")
    parts = [shoulders(), f'<path d="{shape}" fill="{body}" stroke="#92a6b8" stroke-width="2.5"/>']
    if mid == "nintendo.switch-pro":
        parts.append('<path d="m53 130-16 59q-3 18 10 22m320-81 16 59q3 18-10 22" '
                     'fill="none" stroke="#253541" stroke-width="13" stroke-linecap="round"/>')
    if dualsense:
        parts.append('<path d="M120 142q30-24 59-14h62q29-10 59 14l53 69q-16-9-28-26l-35-28H130l-35 28q-12 17-28 26z" fill="#17232e"/>')
    if sony and mid != "sony.dualshock-3":
        parts.append('<rect x="155" y="65" width="110" height="53" rx="9" fill="#142333" stroke="#5b7b99" stroke-width="2"/>')
        if dualsense:
            parts.append('<path d="M151 73v35m118-35v35" stroke="#52a8f9" stroke-width="2"/>')
    else:
        parts.append(menu(210, 87))
    if sony or mid.startswith("logitech"):
        parts.extend((dpad(108, 110), stick(163, 164), stick(257, 164)))
    else:
        parts.extend((stick(109, 108), dpad(160, 165, .9), stick(255, 164)))
    parts.append(faces(310, 105, family))
    if mid.startswith("logitech"):
        parts.append(text(210, 130, "MODE", 9, "#98b2c9"))
    if "elite" in mid or mid == "sony.dualsense-edge":
        parts.append('<g fill="#92a4b3" stroke="#4b657e" stroke-width="1.5"><path d="m151 192 12 17 7-21zM269 192l-12 17-7-21z"/></g>')
        if "elite" in mid:
            parts.append('<path d="m172 196 11 15 5-17m60 2-11 15-5-17" fill="#607b92"/>')
    if is_360:
        parts.append('<circle cx="210" cy="104" r="9" fill="none" stroke="#70be72" stroke-width="2"/>')
    if mid == "microsoft.xbox-series":
        parts.append('<circle cx="160" cy="165" r="28" fill="none" stroke="#688299" stroke-width="2"/>')
    return "".join(parts)


def joycon():
    return ('<rect x="84" y="21" width="100" height="218" rx="35" fill="#48bdd2" stroke="#badce7" stroke-width="2"/>'
            '<rect x="236" y="21" width="100" height="218" rx="35" fill="#e8747c" stroke="#ebbec2" stroke-width="2"/>'
            '<path d="M174 31v198M246 31v198" stroke="#1b2a3b" stroke-width="5"/>'
            + stick(134, 79, 20) + dpad(134, 152, .85) + stick(286, 165, 20)
            + faces(286, 87, "nintendo", .72)
            + '<path d="M144 40h13m107 0h13m-6-6v12" stroke="#203344" stroke-width="3"/>'
            '<rect x="143" y="198" width="11" height="11" rx="2" fill="#25394b"/>'
            '<circle cx="266" cy="211" r="6" fill="#25394b"/>')


def adaptive():
    return ('<rect x="28" y="50" width="364" height="170" rx="17" fill="#e2e7ec" stroke="#9caebc" stroke-width="3"/>'
            '<path d="M41 56h338" stroke="#94a5b5" stroke-width="3"/>'
            '<circle cx="180" cy="143" r="57" fill="#17242d" stroke="#627585" stroke-width="3"/>'
            '<circle cx="180" cy="143" r="48" fill="#202f3c"/>'
            '<circle cx="315" cy="143" r="57" fill="#17242d" stroke="#627585" stroke-width="3"/>'
            '<circle cx="315" cy="143" r="48" fill="#202f3c"/>' + dpad(73, 160, .8) + menu(76, 80))


def steam(deck=False):
    if deck:
        return ('<rect x="10" y="32" width="400" height="196" rx="40" fill="#263544" stroke="#8a9fb3" stroke-width="3"/>'
                '<rect x="91" y="48" width="238" height="160" rx="5" fill="#0d1c2b" stroke="#40566e" stroke-width="2"/>'
                '<path d="M113 180h194M113 188h135" stroke="#244c6c" stroke-width="2"/>'
                + stick(53, 77, 14) + stick(367, 77, 14) + dpad(48, 133, .55) + faces(372, 133, "xbox", .53)
                + '<rect x="37" y="166" width="35" height="35" rx="5" fill="#162431" stroke="#5a7185"/>'
                '<rect x="348" y="166" width="35" height="35" rx="5" fill="#162431" stroke="#5a7185"/>')
    return ('<path d="M86 54Q54 48 40 89L18 177Q9 213 34 226Q62 238 91 202L132 170H288L329 202Q358 238 386 226Q411 213 402 177L380 89Q366 48 334 54Q285 37 251 58H169Q135 37 86 54Z" '
            'fill="#263544" stroke="#8a9fb3" stroke-width="3"/>'
            '<circle cx="105" cy="105" r="42" fill="#152534" stroke="#6a8398" stroke-width="2"/>'
            '<circle cx="315" cy="105" r="42" fill="#152534" stroke="#6a8398" stroke-width="2"/>'
            + dpad(105, 105, .8) + stick(157, 175, 17) + faces(267, 175, "xbox", .63) + menu(210, 89))


def main():
    models_dir = ASSETS / "models"
    models_dir.mkdir(exist_ok=True)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    generated = 0
    for model in catalog["models"]:
        # The generic model and models drawn by the Gamepad Asset Pack keep that artwork.
        if model["id"].startswith("generic.") or model.get("svg", "").startswith("library/"):
            continue
        mid = model["id"]
        art = (joycon() if mid == "nintendo.joycon" else adaptive() if mid == "microsoft.adaptive"
               else steam(mid == "valve.steam-deck") if mid.startswith("valve.") else gamepad(model))
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="420" height="260" viewBox="0 0 420 260">'
               f'<title>{escape(model["model"])}</title><desc>Original stylized illustration for pawz; no manufacturer logos.</desc>'
               '<ellipse cx="210" cy="234" rx="165" ry="9" fill="#0c1b2e" opacity="0.3"/>' + art + '</svg>\n')
        filename = mid + ".svg"
        (models_dir / filename).write_text(svg, encoding="utf-8")
        model["svg"] = "models/" + filename
        generated += 1
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    inputs_dir = ASSETS / "input-icons"
    inputs_dir.mkdir(exist_ok=True)
    for stick_name in ("left", "right"):
        for axis in ("x", "y"):
            arrow = ('<path d="M5 34h26m-22-4-4 4 4 4m18-8 4 4-4 4"/>' if axis == "x" else
                     '<path d="M34 5v26m-4-22 4-4 4 4m-8 18 4 4 4-4"/>')
            svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 42 42">'
                   '<circle cx="17" cy="17" r="12" fill="#17345e" stroke="#d8e7f5" stroke-width="1.6"/>'
                   + text(17, 21, stick_name[0].upper(), 12)
                   + '<g fill="none" stroke="#65baff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
                   + arrow + '</g></svg>\n')
            (inputs_dir / f"{stick_name}-{axis}.svg").write_text(svg, encoding="utf-8")
    print(f"Generated {generated} model illustrations and 4 axis icons.")


if __name__ == "__main__":
    main()
