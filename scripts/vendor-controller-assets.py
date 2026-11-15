"""Fetch the reviewed, pinned subset of AL2009man assets and record provenance.

Platform Guide marks are deliberately excluded per the upstream guidelines.
Run manually when updating vendored resources; the app never downloads assets.
"""
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src/pawz/ui/assets/controllers"
PROMPTS_REV = "552d6448ffc4a6f84d488454878357ea375a59bd"
PACK_REV = "a6d1113b0b3b2438bbbcb08a33f9a25eb2391d7c"
CONTROLLER_TYPES = "Connection Icon Pack/Controller Type/SVG/VSCView "
# Controller silhouettes from the Gamepad Asset Pack, by vendored name.
LIBRARY_ARTWORK = {
    "xbox-360": "Xbox 360 Controller", "xbox-wireless": "Xbox Wireless Controller",
    "dualshock-3": "DualShock 3 Controller", "dualshock-4": "DualShock 4 Controller",
    "dualsense": "DualSense Controller", "switch-pro": "Switch Pro Controller",
    "joycon": "Switch Joy-Con", "joycon-grip": "Switch Joy-Con Grip",
    "steam-controller": "Steam Controller", "steam-deck": "Steam Deck",
}
# Detailed drawings (shoulders and triggers visible), stored without the elements
# listed: manufacturer logos and platform marks are trademarks and are not
# redistributed. "label:" selects an Inkscape layer name, "id:" an element id;
# "show:label:..." instead makes a hidden layer visible.
PACK = "Controller Asset Pack/"
DETAILED_ARTWORK = {
    "switch-pro-detailed": (
        PACK + "Nintendo Switch Controller Images/Switch Pro Controller/Default Theme/Theme SVG/"
        "Switch Pro Controller VSCView.svg", ("label:Nintendo Switch Logo",)),
    "joycon-detailed": (
        PACK + "Nintendo Switch Controller Images/Switch Joycons/Theme SVG/VSCView Joycon Theme.svg",
        ("label:Nintendo Switch Logo",)),
    "dualshock-4-detailed": (
        PACK + "DualShock 4 Controller Images/Default Theme/Theme SVG/DS4 V2 VSC SVG.svg",
        ("label:PS Icon",)),
    "dualsense-detailed": (
        PACK + "DualSense Controller Image/Default/Theme SVG/DualSense VSCView SVG.svg",
        ("label:PS Button",)),  # the PS button is the logo itself
    "xbox-360-detailed": (
        PACK + "Xbox 360 Controller Images/Default Theme/Theme SVG/Xbox 360 VSCView - Black.svg",
        ("label:Microsoft Text", "label:Xbox 360 Text", "id:path29313")),  # path29313: the X on Guide
    "xbox-one-detailed": (
        PACK + "Xbox Wireless Controller Images/Default Theme/Theme SVG/Xbox One Color/"
        "Xbox One Controller VSCView Black.svg", ("id:path8160-9-5",)),  # the logo on Guide
    "xbox-one-s-detailed": (
        PACK + "Xbox Wireless Controller Images/Default Theme/Theme SVG/Xbox One Color/"
        "Xbox One S Controller VSCView Blue.svg", ("id:path8160-9-5",)),
    "xbox-series-detailed": (
        PACK + "Xbox Wireless Controller Images/Default Theme/Theme SVG/Xbox Series X Color/"
        "Xbox Series X Controller VSCView Black.svg", ("id:path8160-9-5",)),
    "steam-controller-detailed": (
        PACK + "Steam Controller Images/Default Theme/Theme SVG/Black/Steam Controller VSCView.svg",
        ("label:Steam Logo",)),
    "steam-deck-detailed": (
        PACK + "Steam Deck Images/Theme SVG/Black/Steam Deck VSCView Overlay.svg",
        # path8593: the STEAM wordmark on Guide; path17439: the screen's chroma-key
        # green; the triggers are drawn but hidden in the original.
        ("id:path8593", "id:path17439", "show:label:Triggers")),
}


def fetch(url):
    return urlopen(Request(url, headers={"User-Agent": "pawz-assets"}), timeout=30).read()


def remove_element(text: str, selector: str) -> str:
    """``text`` without the one element ``selector`` designates (and its content);
    everything else is kept byte for byte."""
    kind, _, value = selector.partition(":")
    attribute = {"label": "inkscape:label", "id": "id"}[kind]
    starts = [m for m in re.finditer(r"<([a-zA-Z]+)\b[^<>]*>", text)
              if re.search(r'\b' + re.escape(attribute) + r'="' + re.escape(value) + r'"', m.group(0))]
    if len(starts) != 1:
        raise SystemExit(f"Expected one element for {selector!r}, found {len(starts)}")
    start = starts[0]
    tag = start.group(1)
    begin = start.start()
    while begin > 0 and text[begin - 1] in " \t\r\n":  # with its indentation
        begin -= 1
    if start.group(0).endswith("/>"):
        return text[:begin] + text[start.end():]
    depth, position = 1, start.end()
    for match in re.finditer(r"<(/?)" + tag + r"\b[^<>]*?(/?)>", text[start.end():]):
        if match.group(1):
            depth -= 1
        elif not match.group(2):
            depth += 1
        if depth == 0:
            position = start.end() + match.end()
            return text[:begin] + text[position:]
    raise SystemExit(f"Unclosed element for {selector!r}")


def show_element(text: str, selector: str) -> str:
    """``text`` with the hidden element ``selector`` designates made visible."""
    kind, _, value = selector.partition(":")
    attribute = {"label": "inkscape:label", "id": "id"}[kind]
    starts = [m for m in re.finditer(r"<([a-zA-Z]+)\b[^<>]*>", text)
              if re.search(r'\b' + re.escape(attribute) + r'="' + re.escape(value) + r'"', m.group(0))]
    if len(starts) != 1 or "display:none" not in starts[0].group(0):
        raise SystemExit(f"Expected one hidden element for {selector!r}")
    tag = starts[0]
    return text[:tag.start()] + tag.group(0).replace("display:none", "display:inline", 1) + text[tag.end():]


def without_elements(data: bytes, selectors: tuple[str, ...]) -> bytes:
    text = data.decode("utf-8")
    for selector in selectors:
        if selector.startswith("show:"):
            text = show_element(text, selector.removeprefix("show:"))
        else:
            text = remove_element(text, selector)
    return text.encode("utf-8")


def main():
    tree = json.loads(fetch("https://api.github.com/repos/AL2009man/Gamepad-Prompt-Asset-Pack/git/trees/" + PROMPTS_REV + "?recursive=1"))
    selected = [item["path"] for item in tree["tree"] if item["path"].endswith(".svg")
                and "guide" not in item["path"].lower() and
                item["path"].split("/")[0] in ("Shared", "Nintendo", "PlayStation", "Xbox")]
    jobs = [("Gamepad-Prompt-Asset-Pack", PROMPTS_REV, name, "prompts/" + name, ()) for name in selected]
    jobs += [("Gamepad-Prompt-Asset-Pack", PROMPTS_REV, "LICENSE", "prompts/LICENSE.txt", ()),
             ("Gamepad-Prompt-Asset-Pack", PROMPTS_REV, "README.md", "prompts/UPSTREAM_README.md", ()),
             ("Gamepad-Asset-Pack", PACK_REV,
              "Connection Icon Pack/Controller Type/SVG/VSCView Generic Controller.svg", "library-generic.svg", ()),
             ("Gamepad-Asset-Pack", PACK_REV, "LICENSE", "Gamepad-Asset-Pack-LICENSE.txt", ())]
    jobs += [("Gamepad-Asset-Pack", PACK_REV, CONTROLLER_TYPES + upstream + ".svg",
              f"library/{name}.svg", ()) for name, upstream in LIBRARY_ARTWORK.items()]
    jobs += [("Gamepad-Asset-Pack", PACK_REV, source, f"library/{name}.svg", removed)
             for name, (source, removed) in DETAILED_ARTWORK.items()]

    def download(job):
        repo, revision, source, target, removed = job
        url = f"https://raw.githubusercontent.com/AL2009man/{repo}/{revision}/" + quote(source)
        data = fetch(url)
        record = {"file": target, "url": url}
        if removed:
            record["upstream_sha256"] = hashlib.sha256(data).hexdigest()
            record["removed"] = list(removed)
            data = without_elements(data, removed)
        destination = ASSETS / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return record | {"sha256": hashlib.sha256(data).hexdigest()}
    with ThreadPoolExecutor(max_workers=8) as pool:
        manifest = list(pool.map(download, jobs))
    (ASSETS / "upstream-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Vendored {len(selected)} prompt SVGs, {len(LIBRARY_ARTWORK) + len(DETAILED_ARTWORK) + 1} "
          "controller illustrations and notices.")


if __name__ == "__main__":
    main()
