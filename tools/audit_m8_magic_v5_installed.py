"""Finite ADR-0058 installed-wheel audit for Magic JSON v5.

Run with the fresh installed venv's isolated Python. Building/installing the
wheel is handled by prepare_m8_transport_audit.ps1; this script only verifies.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib import resources
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def package_files(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): digest(path.read_bytes())
            for path in (root / "towr").rglob("*") if path.is_file() and path.suffix in (".py", ".json")}


def refs(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "$ref":
                yield child
            else:
                yield from refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from refs(child)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    root, work = args.repository.resolve(), args.work_dir.resolve()
    if not sys.flags.isolated or work.exists():
        raise RuntimeError("Use installed Python -I and a fresh work directory")
    work.mkdir(parents=True)
    import towr
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    installed = Path(towr.__file__).resolve().parent.parent
    if not installed.is_relative_to(Path(sys.prefix).resolve()) or installed.is_relative_to(root / "src"):
        raise AssertionError("Source/editable package leaked into installed run")
    source_files = package_files(root / "src")
    with zipfile.ZipFile(args.wheel) as wheel:
        names = wheel.namelist()
        if any(name.lower().endswith(".pdf") or name.startswith("references/") for name in names):
            raise AssertionError("Private source was included in wheel")
        wheel_files = {name: digest(wheel.read(name)) for name in names
                       if name.startswith("towr/") and Path(name).suffix in (".py", ".json")}
    if source_files != wheel_files or source_files != package_files(installed):
        raise AssertionError("Source/wheel/installed package bytes differ")

    schemas = [json.loads(path.read_text(encoding="utf-8"))
               for path in resources.files("towr.adapters.schemas").iterdir()
               if path.name.endswith(".schema.json")]
    registry = Registry().with_resources((schema["$id"], Resource.from_contents(schema)) for schema in schemas)
    refs_count = 0
    for schema in schemas:
        Draft202012Validator.check_schema(schema)
        for ref in refs(schema):
            registry.resolver(schema["$id"]).lookup(ref)
            refs_count += 1
    magic = {schema["$id"] for schema in schemas if schema["$id"].startswith("urn:towr:magic-")}
    expected = {f"urn:towr:magic-{family}:{kind}:{version}"
                for family in ("simulation", "balance") for kind in ("request", "result", "error")
                for version in ("1", "2", "3", "4", "5")}
    if magic != expected or len(schemas) != 48 or refs_count != 507:
        raise AssertionError(f"Schema closure mismatch: {len(schemas)} schemas, {len(magic)} magic, {refs_count} refs")

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    source_env = dict(env, PYTHONPATH=str(root / "src"))
    source_python = root / ".venv/Scripts/python.exe"
    console = Path(sys.executable).with_name("towr.exe")
    comparisons = 0
    for family, route in (("simulation", "simulate-magic"), ("balance", "balance-magic")):
        fixture = root / f"docs/examples/m8/json/magic-{family}-v5.request.json"
        request = json.loads(fixture.read_text(encoding="utf-8"))
        if request["schema_version"] != "5":
            raise AssertionError(f"Wrong public fixture version: {fixture}")
        for mode in ("sequential", "process"):
            data = json.loads(json.dumps(request))
            data["execution"] = ({"mode": "sequential"} if mode == "sequential" else
                                  {"mode": "process", "workers": 2, "batch_size": 1})
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            file = work / f"{family}-{mode}.request.json"
            file.write_bytes(payload)
            commands = (
                ([str(source_python), "-m", "towr", route, "-"], source_env),
                ([sys.executable, "-I", "-m", "towr", route, "-"], env),
                ([str(console), route, file.name], env),
            )
            outputs = []
            for command, command_env in commands:
                result = subprocess.run(command, input=payload if command[-1] == "-" else None,
                                        cwd=work, env=command_env, capture_output=True, timeout=120)
                if result.returncode != 0 or result.stderr:
                    raise AssertionError(f"CLI failed: {command}\n{result.stderr.decode('utf-8', 'replace')}")
                outputs.append(result.stdout)
            if not outputs[0] == outputs[1] == outputs[2]:
                raise AssertionError(f"Source/module/console output differs: {family}/{mode}")
            result = json.loads(outputs[0])
            if result["schema_version"] != "5" or result["request"] != data:
                raise AssertionError(f"Version or full request echo differs: {family}/{mode}")
            comparisons += 3
        print(f"{family} v5: sequential/process, source/module/console exact", flush=True)

    evidence = {"python": sys.version, "interpreter": sys.executable, "installed": str(installed),
                "wheel": str(args.wheel.resolve()), "wheel_sha256": digest(args.wheel.read_bytes()),
                "package_files": len(source_files), "schemas": len(schemas), "magic_schemas": len(magic),
                "local_refs": refs_count, "cli_comparisons": comparisons}
    (work / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2), flush=True)


if __name__ == "__main__":
    main()
