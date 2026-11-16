"""Download Foundry modules into a staging folder; standard library only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
import zipfile


def fetch(url: str, target, timeout: float) -> str:
    if urlsplit(url).scheme not in ("http", "https"):
        raise ValueError("Only HTTP(S) URLs are supported")
    with urlopen(Request(url, headers={"User-Agent": "FoundryModuleDownloader/1.0"}),
                 timeout=timeout) as response:
        shutil.copyfileobj(response, target, length=1024 * 1024)
        return response.url


def module_id(manifest: dict) -> str:
    value = manifest.get("id") or manifest.get("name")
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value):
        raise ValueError("Manifest has no safe module id/name")
    if value.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)),
                         *(f"LPT{i}" for i in range(10))}:
        raise ValueError("Module id is a reserved Windows filename")
    return value


def extract(archive: Path, destination: Path, expected_id: str) -> Path:
    with zipfile.ZipFile(archive) as package:
        for entry in package.infolist():
            name = entry.filename
            parts = PurePosixPath(name).parts
            if (not parts or name.startswith("/") or "\\" in name
                    or any(p in (".", "..") or ":" in p or p.endswith((".", " ")) for p in parts)
                    or stat.S_ISLNK(entry.external_attr >> 16)):
                raise ValueError("Unsafe ZIP entry")
        package.extractall(destination)
    roots = []
    for manifest_path in destination.rglob("module.json"):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict) and module_id(data) == expected_id:
                roots.append(manifest_path.parent)
        except (ValueError, OSError):
            continue
    if len(roots) != 1:
        raise ValueError("ZIP must contain exactly one module.json with matching id")
    return roots[0]


def download(url: str, output: Path, timeout: float) -> str:
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".foundry-", dir=output) as temporary:
        work = Path(temporary)
        with (work / "manifest.json").open("wb") as stream:
            final_url = fetch(url, stream, timeout)
        manifest = json.loads((work / "manifest.json").read_text(encoding="utf-8-sig"))
        if not isinstance(manifest, dict):
            raise ValueError("Manifest must be a JSON object")
        identity = module_id(manifest)
        target = output / identity
        if target.exists():
            return f"SKIP {identity}: destination already exists"
        link = manifest.get("download")
        if not isinstance(link, str) or not link.strip():
            raise ValueError("Manifest has no download URL")
        print(f"Downloading {identity}...", flush=True)
        archive = work / "module.zip"
        with archive.open("wb") as stream:
            fetch(urljoin(final_url, link), stream, timeout)
        root = extract(archive, work / "unpacked", identity)
        # Staging and destination are on the same volume. No partially unpacked module.
        root.rename(target)
        return f"OK {identity} -> {target}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="*", help="Manifest URLs")
    parser.add_argument("--list", type=Path, help="UTF-8 file: one URL per line, # comments")
    parser.add_argument("--output", type=Path, default=Path("downloads/foundry-modules"))
    parser.add_argument("--timeout", type=float, default=120, help="Socket timeout in seconds")
    args = parser.parse_args()
    urls = list(args.urls)
    if args.list:
        urls.extend(line.strip() for line in args.list.read_text(encoding="utf-8-sig").splitlines()
                    if line.strip() and not line.lstrip().startswith("#"))
    if not urls:
        parser.error("Provide manifest URLs or --list")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    failed = 0
    for index, url in enumerate(dict.fromkeys(urls), 1):
        try:
            print(f"[{index}] {download(url, args.output.resolve(), args.timeout)}", flush=True)
        except Exception as exc:
            # URLs may contain private access tokens: do not echo HTTP error URLs.
            print(f"[{index}] ERROR ({type(exc).__name__}); check URL/access, ZIP and free space",
                  flush=True)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
