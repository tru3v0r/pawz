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
# What to fetch, from where, and how each drawing is changed.
SOURCES = json.loads((Path(__file__).with_suffix(".json")).read_text(encoding="utf-8"))


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


def jobs(prompt_files: list[str]) -> list[tuple[str, str, str, str, tuple[str, ...]]]:
    """(repository, revision, source path, target under ASSETS, changes) to download,
    from vendor-controller-assets.json; ``prompt_files`` lists the prompt pack's files."""
    revision = SOURCES["repositories"]
    prompts = SOURCES["prompts"]
    selected = [path for path in prompt_files if path.endswith(".svg")
                and not any(word in path.lower() for word in prompts["excluded_words"])
                and path.split("/")[0] in prompts["folders"]]
    result = [(prompts["repository"], revision[prompts["repository"]], name, prompts["target"] + name, ())
              for name in selected]
    result += [(item["repository"], revision[item["repository"]], item["source"], item["target"], ())
               for item in SOURCES["files"]]
    silhouettes, detailed = SOURCES["silhouettes"], SOURCES["detailed"]
    result += [(silhouettes["repository"], revision[silhouettes["repository"]],
                silhouettes["folder"] + upstream + ".svg", f"library/{name}.svg", ())
               for name, upstream in silhouettes["drawings"].items()]
    result += [(detailed["repository"], revision[detailed["repository"]], detailed["folder"] + drawing["source"],
                f"library/{name}.svg", tuple(drawing["changes"]))
               for name, drawing in detailed["drawings"].items()]
    return result


def main():
    repository = SOURCES["prompts"]["repository"]
    tree = json.loads(fetch(f"https://api.github.com/repos/AL2009man/{repository}/git/trees/"
                            + SOURCES["repositories"][repository] + "?recursive=1"))
    to_fetch = jobs([item["path"] for item in tree["tree"]])

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
        manifest = list(pool.map(download, to_fetch))
    (ASSETS / "upstream-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Vendored {len(to_fetch)} files: prompts, controller illustrations and notices.")


if __name__ == "__main__":
    main()
