"""ADR-0047 finite installed audit; run with the fresh venv's python -I.

Does not build/install packages or edit repository fixtures. Generated evidence
is written only to --work-dir. Each child has a timeout and captured diagnostics.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
from importlib import metadata, resources
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile


ROUTES = {
    "simulate": "m4/ranged-v1.request.json",
    "balance": "m5/json/balance-v1.request.json",
    "simulate-melee": "m6/json/melee-simulation-v1.request.json",
    "balance-melee": "m6/json/melee-balance-v1.request.json",
    "simulate-mixed": "m7/json/mixed-simulation-v1.request.json",
    "balance-mixed": "m7/json/mixed-balance-v1.request.json",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def package_files(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): digest(path.read_bytes())
            for path in (root / "towr").rglob("*")
            if path.is_file() and path.suffix in (".py", ".json")}


def references(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "$ref":
                yield child
            else:
                yield from references(child)
    elif isinstance(value, list):
        for child in value:
            yield from references(child)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    root, work = args.repository.resolve(), args.work_dir.resolve()
    require(sys.flags.isolated == 1, "Run the installed Python with -I")
    require(not work.exists(), "Use a fresh work directory")
    work.mkdir(parents=True)
    import towr
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from towr.adapters.magic_json_schema import (
        validate_magic_balance_document, validate_magic_simulation_document,
    )

    site = Path(towr.__file__).resolve().parent.parent
    require(site.is_relative_to(Path(sys.prefix).resolve()), "towr is not installed in this venv")
    require(not site.is_relative_to(root / "src"), "Editable/source import leaked")
    source_files = package_files(root / "src")
    with zipfile.ZipFile(args.wheel) as wheel:
        require(not any(name.lower().endswith(".pdf") or name.startswith("references/")
                        for name in wheel.namelist()), "Private source packaged")
        wheel_files = {name: digest(wheel.read(name)) for name in wheel.namelist()
                       if name.startswith("towr/") and Path(name).suffix in (".py", ".json")}
    require(source_files == wheel_files == package_files(site), "Source/wheel/installed bytes differ")
    print(f"Exact source/wheel/installed parity: {len(source_files)} files", flush=True)

    documents = [json.loads(path.read_text(encoding="utf-8"))
                 for path in resources.files("towr.adapters.schemas").iterdir()
                 if path.name.endswith(".schema.json")]
    registry = Registry().with_resources((doc["$id"], Resource.from_contents(doc)) for doc in documents)
    ref_count = 0
    for doc in documents:
        Draft202012Validator.check_schema(doc)
        for ref in references(doc):
            registry.resolver(doc["$id"]).lookup(ref)
            ref_count += 1
    magic_ids = [doc["$id"] for doc in documents if doc["$id"].startswith("urn:towr:magic-")]
    require(len(magic_ids) == 12, "Expected twelve magic schemas")
    print(f"Bundled schema closure: {len(documents)} schemas / {ref_count} local refs / 12 magic", flush=True)

    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONNOUSERSITE"] = "1"
    source_env = dict(environment, PYTHONPATH=str(root / "src"))
    source_python = root / ".venv/Scripts/python.exe"
    console = Path(sys.executable).with_name("towr.exe")
    calls = 0

    def run(command, *, env=environment, payload=None, expected=0):
        nonlocal calls
        calls += 1
        result = subprocess.run([str(part) for part in command], input=payload, cwd=work,
                                env=env, capture_output=True, timeout=120)
        require(result.returncode == expected,
                f"exit {result.returncode}, expected {expected}: {command}\n{result.stderr.decode('utf-8', 'replace')}")
        if expected == 0:
            require(not result.stderr, f"Unexpected stderr: {result.stderr!r}")
        return result.stdout

    def invoke(route, data, *, expected=0):
        payload = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode("utf-8")
        # Module uses stdin; console also exercises a copied UTF-8 file in an external cwd.
        input_path = work / "вход.json"
        input_path.write_bytes(payload)
        baseline = run([source_python, "-m", "towr", route, "-"], env=source_env,
                       payload=payload, expected=expected)
        module = run([sys.executable, "-I", "-m", "towr", route, "-"],
                     payload=payload, expected=expected)
        executable = run([console, route, input_path.name], expected=expected)
        require(baseline == module == executable, f"Source/module/console differ: {route}")
        return json.loads(module)

    def read(relative):
        return json.loads((root / "docs/examples" / relative).read_text(encoding="utf-8"))

    for route, path in ROUTES.items():
        data = read(path)
        invoke(route, data)
        invalid = dict(data, schema_version="2")
        error = invoke(route, invalid, expected=2)
        require(error["schema_version"] == "1", f"Nonmagic v2 accepted: {route}")
        print(f"Legacy route: {route} success + v2 rejection", flush=True)

    validators = {"simulation": validate_magic_simulation_document, "balance": validate_magic_balance_document}
    cases = 0
    for family, route in (("simulation", "simulate-magic"), ("balance", "balance-magic")):
        validate = validators[family]
        legacy = None
        for label, version in (("v1", "1"), ("v2-null", "2"), ("v2-opted", "2")):
            data = read(f"m8/json/magic-{family}-v{version}.request.json")
            if label == "v2-null":
                scenario = data["scenario"] if family == "simulation" else data["reserve"]["scenario"]
                scenario["miscast_continuation"] = None
                if family == "balance":
                    data["generation"]["miscast_continuation"] = None
            validate(data, schema_version=version)
            outputs = []
            for mode in ("sequential", "process"):
                request = deepcopy(data)
                request["execution"] = ({"mode": mode} if mode == "sequential" else
                                        {"mode": mode, "workers": 2, "batch_size": 1})
                result = invoke(route, request)
                validate(result, "result", schema_version=version)
                require(result["request"] == request, "Full echo differs")
                require(result["schema_version"] == version, "Version downgraded")
                if label == "v2-opted" and mode == "sequential":
                    (work / f"magic-{family}-v2.result.json").write_text(
                        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                comparable = deepcopy(result)
                comparable["request"].pop("execution")
                outputs.append(comparable)
                cases += 1
            require(outputs[0] == outputs[1], "Sequential/process results differ")
            numeric = deepcopy(outputs[0])
            numeric.pop("schema_version")
            numeric.pop("request")
            if label == "v1":
                legacy = numeric
            elif label == "v2-null":
                require(numeric == legacy, "V2 null changes legacy aggregates")
            print(f"Magic {family} {label}: sequential/process source/module/console match", flush=True)

        # Every family/version/error schema is exercised, not just loaded.
        for version in ("1", "2"):
            bad = read(f"m8/json/magic-{family}-v{version}.request.json")
            bad["unexpected"] = True
            error = invoke(route, bad, expected=2)
            validate(error, "error", schema_version=version)
            require(error["schema_version"] == version, "Shape error lost trusted version")
        error = invoke(route, b'{"schema_version":"2","request_id":"untrusted",', expected=2)
        validate(error, "error")
        require(error["schema_version"] == "1" and error["request_id"] is None,
                "Incomplete decode trusted metadata")
        if family == "balance":
            mismatch = read("m8/json/magic-balance-v2.request.json")
            mismatch["generation"]["miscast_continuation"] = None
            error = invoke(route, mismatch, expected=2)
            validate(error, "error", schema_version="2")
            require(error["error"]["path"] == "/generation/miscast_continuation", "Family mismatch pointer")

    # Import only a copied four-file bundle, never repository examples/tests.
    examples = work / "examples"
    examples.mkdir()
    for name in ("opt_in_transport_contract_probe.py", "generation_contract_probe.py",
                 "magic_scenario.py", "opted_miscast.py"):
        shutil.copyfile(root / "docs/examples/m8" / name, examples / name)
    for module in ("opt_in_transport_contract_probe", "opted_miscast"):
        output = run([sys.executable, "-I", "-c",
                      "import sys; sys.path.insert(0, sys.argv[1]); "
                      f"import {module}; {module}.main()", examples])
        expected = (root / f"docs/examples/m8/{module}.output.txt").read_text(encoding="utf-8")
        require(output.decode("utf-8").replace("\r\n", "\n") == expected, f"Copied {module} output differs")
    require(source_files == package_files(root / "src"), "Source changed during audit")
    evidence = {
        "python": platform.python_version(), "platform": platform.platform(),
        "installed_site": str(site), "wheel_sha256": digest(args.wheel.read_bytes()),
        "package_files": len(source_files), "schemas": len(documents), "local_refs": ref_count,
        "magic_schemas": len(magic_ids), "magic_backend_cases": cases, "child_commands": calls,
        "copied_examples": 2,
        "dependencies": {name: metadata.version(name) for name in (
            "towr-encounter-balancer", "jsonschema", "referencing", "jsonschema-specifications",
            "attrs", "rpds-py", "typing-extensions")},
    }
    (work / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2), flush=True)


if __name__ == "__main__":
    main()
