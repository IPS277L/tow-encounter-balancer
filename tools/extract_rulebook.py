"""Extract a private PDF rulebook into page files and a structural manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pypdf import PdfReader


def flatten_outline(reader: PdfReader, items: list[Any], depth: int = 0) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, list):
            result.extend(flatten_outline(reader, item, depth + 1))
            continue
        try:
            page = reader.get_destination_page_number(item) + 1
        except Exception:
            page = None
        result.append(
            {
                "title": getattr(item, "title", str(item)),
                "page": page,
                "depth": depth,
            }
        )
    return result


def extract(source: Path, output: Path) -> None:
    reader = PdfReader(source)
    pages_directory = output / "pages"
    pages_directory.mkdir(parents=True, exist_ok=True)

    page_manifest: list[dict[str, Any]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        page_path = pages_directory / f"{page_number:04}.txt"
        page_path.write_text(text, encoding="utf-8")
        page_manifest.append(
            {
                "page": page_number,
                "characters": len(text),
                "has_text": bool(text.strip()),
                "file": page_path.relative_to(output).as_posix(),
            }
        )

    manifest = {
        "source_file": source.name,
        "page_count": len(reader.pages),
        "encrypted": reader.is_encrypted,
        "metadata": {str(key): str(value) for key, value in (reader.metadata or {}).items()},
        "outline": flatten_outline(reader, reader.outline),
        "pages": page_manifest,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    extract(arguments.source, arguments.output)


if __name__ == "__main__":
    main()
