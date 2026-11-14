"""Fetch the reviewed, pinned subset of AL2009man assets and record provenance.

Platform Guide marks are deliberately excluded per the upstream guidelines.
Run manually when updating vendored resources; the app never downloads assets.
"""
import hashlib
import json
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


def fetch(url):
    return urlopen(Request(url, headers={"User-Agent": "pawz-assets"}), timeout=30).read()


def main():
    tree = json.loads(fetch("https://api.github.com/repos/AL2009man/Gamepad-Prompt-Asset-Pack/git/trees/" + PROMPTS_REV + "?recursive=1"))
    selected = [item["path"] for item in tree["tree"] if item["path"].endswith(".svg")
                and "guide" not in item["path"].lower() and
                item["path"].split("/")[0] in ("Shared", "Nintendo", "PlayStation", "Xbox")]
    jobs = [("Gamepad-Prompt-Asset-Pack", PROMPTS_REV, name, "prompts/" + name) for name in selected]
    jobs += [("Gamepad-Prompt-Asset-Pack", PROMPTS_REV, "LICENSE", "prompts/LICENSE.txt"),
             ("Gamepad-Prompt-Asset-Pack", PROMPTS_REV, "README.md", "prompts/UPSTREAM_README.md"),
             ("Gamepad-Asset-Pack", PACK_REV,
              "Connection Icon Pack/Controller Type/SVG/VSCView Generic Controller.svg", "library-generic.svg"),
             ("Gamepad-Asset-Pack", PACK_REV, "LICENSE", "Gamepad-Asset-Pack-LICENSE.txt")]
    jobs += [("Gamepad-Asset-Pack", PACK_REV, CONTROLLER_TYPES + upstream + ".svg",
              f"library/{name}.svg") for name, upstream in LIBRARY_ARTWORK.items()]
    def download(job):
        repo, revision, source, target = job
        url = f"https://raw.githubusercontent.com/AL2009man/{repo}/{revision}/" + quote(source)
        data = fetch(url)
        destination = ASSETS / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return {"file": target, "url": url, "sha256": hashlib.sha256(data).hexdigest()}
    with ThreadPoolExecutor(max_workers=8) as pool:
        manifest = list(pool.map(download, jobs))
    (ASSETS / "upstream-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Vendored {len(selected)} prompt SVGs, {len(LIBRARY_ARTWORK) + 1} controller "
          "illustrations and notices.")


if __name__ == "__main__":
    main()
