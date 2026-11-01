"""ADR-0047/0051 finite installed audit; use the fresh venv's python -I.

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
STATIONARY_FIELD = "stationary_wound_continuation"
STATIONARY_VALUE = "leg_spasm_stand_and_continue"
REPEATED_FIELD = "repeated_leg_spasm_continuation"
REPEATED_VALUE = "stand_once_with_journal_witnesses"


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
    parser.add_argument("--repository", "--repo", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--work-dir", "--work", type=Path, required=True)
    args = parser.parse_args()
    root, work = args.repository.resolve(), args.work_dir.resolve()
    require(sys.flags.isolated == 1, "Run the installed Python with -I")
    require(not work.exists(), "Use a fresh work directory")
    work.mkdir(parents=True)
    fixture_root = root / "docs/examples/m8"
    fixture_hashes = {path.relative_to(root).as_posix(): digest(path.read_bytes())
                      for path in fixture_root.rglob("*")
                      if path.is_file() and path.suffix in (".json", ".py", ".txt")}
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
    expected_ids = {f"urn:towr:magic-{family}:{kind}:{version}"
                    for family in ("simulation", "balance") for version in ("1", "2", "3", "4")
                    for kind in ("request", "result", "error")}
    require(set(magic_ids) == expected_ids and len(magic_ids) == 24, "Magic schema versions/IDs differ")
    require(len(documents) == 42, "Expected 42 packaged schemas")
    print(f"Bundled schema closure: {len(documents)} schemas / {ref_count} local refs / {len(magic_ids)} magic", flush=True)

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

    def invoke(route, data, *, expected=0, save_as=None):
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
        if save_as is not None:
            (work / save_as).write_bytes(module)
        return json.loads(module)

    def read(relative):
        return json.loads((root / "docs/examples" / relative).read_text(encoding="utf-8"))

    for route, path in ROUTES.items():
        data = read(path)
        invoke(route, data)
        for version in ("2", "3", "4"):
            invalid = dict(data, schema_version=version)
            error = invoke(route, invalid, expected=2)
            require(error["schema_version"] == "1", f"Nonmagic v{version} accepted: {route}")
        print(f"Legacy route: {route} success + v2/v3/v4 rejection", flush=True)

    validators = {"simulation": validate_magic_simulation_document, "balance": validate_magic_balance_document}
    cases = 0
    saved_public_results = {}
    saved_legacy_results = {}
    for family, route in (("simulation", "simulate-magic"), ("balance", "balance-magic")):
        validate = validators[family]
        legacy = None
        legacy_data = read(f"m8/json/magic-{family}-v1.request.json")
        opted_data = read(f"m8/json/magic-{family}-v2.request.json")
        policy = (opted_data["scenario"] if family == "simulation" else opted_data["reserve"]["scenario"])["miscast_continuation"]
        require(policy is not None, "Public v2 policy fixture must be opted")
        variants = [("v1", "1", False, False, False), ("v2-null", "2", False, False, False),
                    ("v2-opted", "2", True, False, False)]
        variants += [(f"v3-miscast-{int(miscast)}-stationary-{int(stationary)}", "3", miscast, stationary, False)
                     for miscast in (False, True) for stationary in (False, True)]
        variants += [(f"v4-miscast-{int(miscast)}-stationary-{int(stationary)}-repeated-{int(repeated)}",
                      "4", miscast, stationary, repeated)
                     for miscast in (False, True) for stationary, repeated in ((False, False), (True, False), (True, True))]
        for label, version, miscast, stationary, repeated in variants:
            # V1/v2 retain their public inputs; synthetic v3 variants use the
            # same authored game parameters, seeds and budgets as legacy.
            data = deepcopy(opted_data if version == "2" else legacy_data)
            data["schema_version"] = version
            scenario = data["scenario"] if family == "simulation" else data["reserve"]["scenario"]
            targets = (scenario,) if family == "simulation" else (scenario, data["generation"])
            for target in targets:
                if version in ("2", "3", "4"):
                    target["miscast_continuation"] = deepcopy(policy) if miscast else None
                if version in ("3", "4"):
                    target[STATIONARY_FIELD] = STATIONARY_VALUE if stationary else None
                if version == "4":
                    target[REPEATED_FIELD] = REPEATED_VALUE if repeated else None
            validate(data, schema_version=version)
            outputs = []
            for mode in ("sequential", "process"):
                request = deepcopy(data)
                request["execution"] = ({"mode": mode} if mode == "sequential" else
                                        {"mode": mode, "workers": 2, "batch_size": 1})
                result = invoke(route, request,
                    save_as=f"magic-{family}-{label}-{mode}.result.json")
                validate(result, "result", schema_version=version)
                require(result["request"] == request, "Full echo differs")
                require(result["schema_version"] == version, "Version downgraded")
                if label == "v2-opted" and mode == "sequential":
                    shutil.copyfile(work / f"magic-{family}-{label}-{mode}.result.json",
                                    work / f"magic-{family}-v2.result.json")
                if label in ("v1", "v2-opted") and mode == "sequential":
                    saved_path = fixture_root / f"json/magic-{family}-v{version}.result.json"
                    saved = json.loads(saved_path.read_text(encoding="utf-8"))
                    validate(saved, "result", schema_version=version)
                    require(saved["request"] == request and saved["schema_version"] == version,
                            "Saved legacy public request/version differs")
                    same_runtime = saved["runtime"] == result["runtime"]
                    actual_bytes = (work / f"magic-{family}-{label}-{mode}.result.json").read_bytes()
                    if same_runtime:
                        require(saved_path.read_bytes() == actual_bytes,
                                "Legacy saved result bytes differ on the same runtime")
                    saved_legacy_results[f"{family}:v{version}"] = {"runtime_equal": same_runtime,
                        "saved_sha256": digest(saved_path.read_bytes()), "actual_sha256": digest(actual_bytes)}
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
            elif not miscast and not stationary:
                require(numeric == legacy, f"{version} null changes legacy aggregates")
            print(f"Magic {family} {label}: sequential/process source/module/console match", flush=True)

        # Every family/version/error schema is exercised, not just loaded.
        for version in ("1", "2", "3", "4"):
            bad = read(f"m8/json/magic-{family}-v{version}.request.json")
            bad["unexpected"] = True
            error = invoke(route, bad, expected=2)
            validate(error, "error", schema_version=version)
            require(error["schema_version"] == version, "Shape error lost trusted version")
        trusted = read(f"m8/json/magic-{family}-v3.request.json")
        semantic = deepcopy(trusted)
        seed_parent = "simulation" if family == "simulation" else "evaluation"
        semantic[seed_parent]["master_seed"] = str(2**64)
        error = invoke(route, semantic, expected=2)
        validate(error, "error", schema_version="3")
        require(error["schema_version"] == "3" and error["request_id"] == trusted["request_id"]
                and error["error"]["path"] == f"/{seed_parent}/master_seed", "Semantic failure lost trusted metadata")
        # Lexical failures must never trust an earlier version/ID token.
        for raw in (b'{"schema_version":"3","request_id":"untrusted",',
                    b'{"schema_version":"3","request_id":"untrusted","request_id":"again"}',
                    b'{"schema_version":"3","request_id":"untrusted","value":1.0}',
                    b'{"schema_version":"3","request_id":"untrusted","value":1e0}',
                    b'{"schema_version":"3","request_id":"untrusted","value":NaN}',
                    b'{"schema_version":"3","request_id":"untrusted","value":"\\ud800"}',
                    b'{"schema_version":"3","request_id":"untrusted","value":"\xff"}'):
            error = invoke(route, raw, expected=2)
            validate(error, "error")
            require(error["schema_version"] == "1" and error["request_id"] is None,
                    "Incomplete strict decode trusted metadata")
        unknown = dict(trusted, schema_version="5")
        error = invoke(route, unknown, expected=2)
        validate(error, "error")
        require(error["schema_version"] == "1" and error["request_id"] == trusted["request_id"]
                and error["error"]["code"] == "unsupported_version"
                and error["error"]["path"] == "/schema_version", "Unknown version metadata differs")
        for version in (None, False, 3):
            bad = deepcopy(trusted)
            if version is None:
                del bad["schema_version"]
            else:
                bad["schema_version"] = version
            error = invoke(route, bad, expected=2)
            validate(error, "error")
            require(error["schema_version"] == "1" and error["request_id"] == trusted["request_id"]
                    and error["error"]["code"] == "invalid_input", "Non-string/missing version metadata differs")
        for version in ("1", "2"):
            for location in (("scenario",) if family == "simulation" else ("reserve", "generation")):
                old = read(f"m8/json/magic-{family}-v{version}.request.json")
                target = old["scenario"] if family == "simulation" else (
                    old["reserve"]["scenario"] if location == "reserve" else old["generation"])
                target[STATIONARY_FIELD] = None
                error = invoke(route, old, expected=2)
                validate(error, "error", schema_version=version)
                require(error["schema_version"] == version, "Old version silently accepted/downgraded stationary field")
        if family == "balance":
            mismatch = read("m8/json/magic-balance-v2.request.json")
            mismatch["generation"]["miscast_continuation"] = None
            error = invoke(route, mismatch, expected=2)
            validate(error, "error", schema_version="2")
            require(error["error"]["path"] == "/generation/miscast_continuation", "Family mismatch pointer")
            for reserve_policy, family_policy in ((None, STATIONARY_VALUE), (STATIONARY_VALUE, None)):
                mismatch = deepcopy(trusted)
                mismatch["reserve"]["scenario"][STATIONARY_FIELD] = reserve_policy
                mismatch["generation"][STATIONARY_FIELD] = family_policy
                error = invoke(route, mismatch, expected=2)
                validate(error, "error", schema_version="3")
                require(error["error"]["path"] == "/generation/" + STATIONARY_FIELD,
                        "Stationary family mismatch pointer")
        # Execute each public v3 artifact itself, separately from the parity
        # matrix based on identical legacy game parameters.
        actual = invoke(route, trusted, save_as=f"magic-{family}-v3.result.json")
        validate(actual, "result", schema_version="3")
        saved_path = fixture_root / f"json/magic-{family}-v3.result.json"
        saved = json.loads(saved_path.read_text(encoding="utf-8"))
        validate(saved, "result", schema_version="3")
        require(saved["schema_version"] == actual["schema_version"] == "3"
                and saved["request"] == actual["request"] == trusted, "Public3 artifact request/version differs")
        same_runtime = saved["runtime"] == actual["runtime"]
        if same_runtime:
            require(saved_path.read_bytes() == (work / f"magic-{family}-v3.result.json").read_bytes(),
                    "Public3 saved result differs on the same runtime")
        saved_public_results[family] = {"runtime_equal": same_runtime,
            "saved_sha256": digest(saved_path.read_bytes()),
            "actual_sha256": digest((work / f"magic-{family}-v3.result.json").read_bytes())}

        trusted4 = read(f"m8/json/magic-{family}-v4.request.json")
        actual4 = invoke(route, trusted4, save_as=f"magic-{family}-v4.result.json")
        validate(actual4, "result", schema_version="4")
        saved4 = fixture_root / f"json/magic-{family}-v4.result.json"
        saved_document4 = json.loads(saved4.read_text(encoding="utf-8"))
        validate(saved_document4, "result", schema_version="4")
        require(actual4["request"] == saved_document4["request"] == trusted4, "Public4 request differs")
        same_runtime4 = saved_document4["runtime"] == actual4["runtime"]
        if same_runtime4:
            require(saved4.read_bytes() == (work / f"magic-{family}-v4.result.json").read_bytes(),
                    "Public4 saved result differs on same runtime")
        saved_public_results[family + ":v4"] = {"runtime_equal": same_runtime4,
            "saved_sha256": digest(saved4.read_bytes()),
            "actual_sha256": digest((work / f"magic-{family}-v4.result.json").read_bytes())}
        locations = ("scenario",) if family == "simulation" else ("reserve", "generation")
        for version in ("1", "2", "3"):
            for location in locations:
                for value in (None, REPEATED_VALUE):
                    old = read(f"m8/json/magic-{family}-v{version}.request.json")
                    target = old["scenario"] if family == "simulation" else (
                        old["reserve"]["scenario"] if location == "reserve" else old["generation"])
                    target[REPEATED_FIELD] = value
                    error = invoke(route, old, expected=2)
                    validate(error, "error", schema_version=version)
                    require(error["schema_version"] == version, "Legacy accepted repeated permission key")
        for location in locations:
            wrong = deepcopy(trusted4)
            target = wrong["scenario"] if family == "simulation" else (
                wrong["reserve"]["scenario"] if location == "reserve" else wrong["generation"])
            target[STATIONARY_FIELD] = None
            error = invoke(route, wrong, expected=2)
            expected_path = "/scenario/" if family == "simulation" else (
                "/reserve/scenario/" if location == "reserve" else "/generation/")
            # A family base mismatch precedes its dependent permission, as in v3.
            expected_field = STATIONARY_FIELD if location == "generation" else REPEATED_FIELD
            require(error["schema_version"] == "4" and error["error"]["path"] == expected_path + expected_field,
                    "V4 dependency/matching priority differs")
        if family == "balance":
            for reserve, family_value in ((None, REPEATED_VALUE), (REPEATED_VALUE, None)):
                wrong = deepcopy(trusted4)
                wrong["reserve"]["scenario"][REPEATED_FIELD] = reserve
                wrong["generation"][REPEATED_FIELD] = family_value
                error = invoke(route, wrong, expected=2)
                require(error["schema_version"] == "4" and error["error"]["path"] == "/generation/" + REPEATED_FIELD,
                        "V4 repeated matching pointer differs")
        for raw in (b'{"schema_version":"4","request_id":"untrusted",',
                    b'{"schema_version":"4","request_id":"untrusted","request_id":"again"}',
                    b'{"schema_version":"4","request_id":"untrusted","x":1.0}',
                    b'{"schema_version":"4","request_id":"untrusted","x":NaN}',
                    b'{"schema_version":"4","request_id":"untrusted","x":"\\ud800"}',
                    b'{"schema_version":"4","request_id":"untrusted","x":0} {}', b'\xff'):
            error = invoke(route, raw, expected=2)
            require(error["schema_version"] == "1" and error["request_id"] is None, "V4 lexical trust leaked")

    # A complete reserve can be admitted yet its first projected subset can
    # invalidate this explicit Broken route. Exercise the actual generation
    # phase and CLI envelope rather than injecting a production exception.
    failure = read("m8/json/magic-balance-v3.request.json")
    frame = deepcopy(failure["reserve"]["scenario"]["scene_frames"][0])
    for placement in frame["key"]["placements"]:
        if placement["entity_id"] in ("E2", "E3"):
            placement["zone_id"] = "boundary"
    for pair in frame["pair_ranges"]:
        pair["target_range"] = "short" if pair["second_actor_id"] == "E1" else "long"
    for plan in frame["give_ground_plans"]:
        if plan["actor_id"] in ("E2", "E3"):
            plan.update(can_leave_zone=False, destination_zone_id=None, route=None, impossible_confirmed=True)
    frame["broken_plans"] = [{"actor_id": "ally", "kind": "free_move_recover", "free_move_zone_ids": ["shelter"],
        "free_move_route": {"path_entity_ids": [], "crosses_obstacle": False, "crosses_difficult_terrain": False},
        "run_destination_zone_id": None, "run_route": None, "fastest_route_confirmed": True}]
    failure["reserve"]["scenario"]["scene_frames"].append(frame)
    failure["generation"]["scene_frames"] = deepcopy(failure["reserve"]["scenario"]["scene_frames"])
    error = invoke("balance-magic", failure, expected=3, save_as="magic-balance-v3.generation-error.json")
    validate_magic_balance_document(error, "error", schema_version="3")
    require(error["schema_version"] == "3" and error["request_id"] == failure["request_id"]
            and error["error"]["code"] == "generation_failed" and error["error"]["path"] == "/generation"
            and error["error"]["counts"] == [1, 0] and error["error"]["candidate_id"] is not None
            and error["error"]["stage_index"] is None, "Actual generation failure lost its context")
    failure["schema_version"] = "4"
    failure["reserve"]["scenario"][REPEATED_FIELD] = REPEATED_VALUE
    failure["generation"][REPEATED_FIELD] = REPEATED_VALUE
    error4 = invoke("balance-magic", failure, expected=3, save_as="magic-balance-v4.generation-error.json")
    validate_magic_balance_document(error4, "error", schema_version="4")
    require(error4["schema_version"] == "4" and error4["error"] == error["error"],
            "V4 actual generation failure lost its classification/context")

    # Runtime evaluation failures are not gameplay fixtures. Check their real
    # native envelopes directly, without patching a runner or claiming a CLI
    # failure that this finite scenario does not trigger.
    phase_program = """
import json
from towr.adapters.magic_balance_json import encode_magic_balance_error
from towr.adapters.magic_simulation_json import encode_magic_simulation_error
from towr.application.magic_balance_errors import MagicBalanceGenerationError, MagicBalanceExecutionError
from towr.application.magic_simulation_errors import MagicSimulationExecutionError
errors = [error for version in ('3', '4') for error in (
          MagicBalanceGenerationError('own-generation', 'candidate', (1, 0), schema_version=version),
          MagicBalanceExecutionError('own-evaluation', 1, 'candidate', schema_version=version),
          MagicSimulationExecutionError('own-simulation', schema_version=version))]
outputs = []
for error in errors:
    error.__cause__ = ValueError('private cause')
    error.add_note('private note')
    encoder = encode_magic_simulation_error if isinstance(error, MagicSimulationExecutionError) else encode_magic_balance_error
    outputs.append(json.loads(encoder(error)))
print(json.dumps(outputs, sort_keys=True))
"""
    source_errors = run([source_python, "-c", phase_program], env=source_env)
    installed_errors = run([sys.executable, "-I", "-c", phase_program])
    require(source_errors == installed_errors and b"private" not in installed_errors,
            "Native phase-error envelopes differ or expose private diagnostics")
    phase_errors = json.loads(installed_errors)
    for index, error in enumerate(phase_errors):
        version = '3' if index < 3 else '4'
        (validate_magic_balance_document if index % 3 < 2 else validate_magic_simulation_document)(
            error, "error", schema_version=version)
        require(error["schema_version"] == version and error["request_id"] == (
            "own-generation", "own-evaluation", "own-simulation")[index % 3], "Native phase error lost owned metadata")
    require(phase_errors[0]["error"]["counts"] == [1, 0]
            and phase_errors[1]["error"]["stage_index"] == 1
            and phase_errors[1]["error"]["candidate_id"] == "candidate", "Native phase context differs")
    (work / "native-v3-v4-phase-errors.json").write_bytes(installed_errors)

    # Import only the independent copied bundles, never repository examples/tests.
    bundles = {
        "legacy-four": (("opt_in_transport_contract_probe", "opted_miscast"),
            ("opt_in_transport_contract_probe.py", "generation_contract_probe.py", "magic_scenario.py", "opted_miscast.py")),
        "stationary-five": (("stationary_wound_transport_contract_probe",),
            ("stationary_wound_transport_contract_probe.py", "generation_contract_probe.py", "magic_scenario.py",
             "opted_miscast.py", "stationary_wound_runner.py")),
        "repeated-six": (("repeated_leg_spasm_transport_contract_probe",),
            ("repeated_leg_spasm_transport_contract_probe.py", "generation_contract_probe.py",
             "stationary_wound_runner.py", "magic_scenario.py",
             "json/magic-simulation-v3.request.json", "json/magic-balance-v3.request.json")),
    }
    for label, (modules, names) in bundles.items():
        examples = work / label
        examples.mkdir()
        for name in names:
            (examples / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(fixture_root / name, examples / name)
        for module in modules:
            output = run([sys.executable, "-I", "-c",
                          "import sys; sys.path.insert(0, sys.argv[1]); "
                          f"import {module}; {module}.main()", examples])
            expected = (fixture_root / f"{module}.output.txt").read_text(encoding="utf-8")
            require(output.decode("utf-8").replace("\r\n", "\n") == expected, f"Copied {module} output differs")
            (examples / f"{module}.actual-output.txt").write_bytes(output)
    require(source_files == package_files(root / "src"), "Source changed during audit")
    require(fixture_hashes == {name: digest((root / name).read_bytes()) for name in fixture_hashes},
            "Repository examples changed during audit")
    evidence = {
        "python": platform.python_version(), "platform": platform.platform(),
        "installed_site": str(site), "installed_towr": str(Path(towr.__file__).resolve()),
        "interpreter": sys.executable, "isolated": sys.flags.isolated,
        "wheel": str(args.wheel.resolve()), "wheel_sha256": digest(args.wheel.read_bytes()),
        "package_files": len(source_files), "schemas": len(documents), "local_refs": ref_count,
        "magic_schemas": len(magic_ids), "magic_backend_cases": cases, "child_commands": calls,
        "copied_examples": 4, "copied_bundles": {label: len(spec[1]) for label, spec in bundles.items()},
        "public_v3_v4_results": saved_public_results, "public_legacy_results": saved_legacy_results,
        "package_file_hashes": source_files,
        "actual_generation_errors": 2, "native_phase_errors": len(phase_errors),
        "unchanged_example_hashes": fixture_hashes,
        "dependencies": {name: metadata.version(name) for name in (
            "towr-encounter-balancer", "jsonschema", "referencing", "jsonschema-specifications",
            "attrs", "rpds-py", "typing-extensions")},
    }
    (work / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2), flush=True)


if __name__ == "__main__":
    main()
