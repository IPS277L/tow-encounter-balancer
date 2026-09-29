"""Historical comparison probe: run from the repo root after applying the rejected patch.

Requires the exact before/candidate source hashes; uses only git show, never checkout.
Creates disposable copies under build and leaves them available for inspection.
"""
import gc
import json
import os
from pathlib import Path
import shutil
from statistics import median
import subprocess
import sys
from tempfile import mkdtemp
from time import perf_counter

ROOT = Path.cwd()
if len(sys.argv) > 1:
    sys.path.insert(0, str(ROOT))
    from tools.profile_m7 import benchmark_request, run_batch, trial_digest
    from towr.domain import npc_round_models
    print(json.dumps({"loaded": npc_round_models.__file__}), flush=True)
    for line in sys.stdin:
        case = tuple(json.loads(line))
        request = benchmark_request(case, trials=100, master_seed=20260929, round_budget=5)
        gc.collect()
        start = perf_counter()
        result, summary = run_batch(request)
        elapsed = perf_counter() - start
        print(json.dumps({"time": elapsed, "digest": trial_digest(result),
            "counts": [summary.outcome_counts.objective_achieved, summary.outcome_counts.side_defeated,
                       summary.outcome_counts.round_limit, summary.outcome_counts.unsupported_path],
            "attacks": result.total_attack_count, "rounds": result.total_visited_round_count}), flush=True)
    sys.exit()

sys.path.insert(0, str(ROOT))
from tools.profile_m7 import source_digest, CASES
assert source_digest(ROOT) == "7ec759973c51dea9f4ff1c06758f5fd07486636a1c6348e8c627a074f7576519"
(ROOT / "build").mkdir(exist_ok=True)
baseline = Path(mkdtemp(prefix="m7-round-baseline-", dir=ROOT / "build"))
assert baseline.resolve().is_relative_to((ROOT / "build").resolve())
shutil.copytree(ROOT / "src", baseline / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
(baseline / "tools").mkdir()
shutil.copyfile(ROOT / "tools/profile_m7.py", baseline / "tools/profile_m7.py")
original = subprocess.run(["git", "show", "4db7a22879671cbb1de4ec4581b20f8641a60557:src/towr/domain/npc_round_models.py"],
    capture_output=True, check=True).stdout
# Preserve working-tree line endings for the hash used by the original benchmark.
(baseline / "src/towr/domain/npc_round_models.py").write_bytes(original.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
assert source_digest(baseline) == "529d908bbfa1885419038f94845dfcf3718db6d663e807d8252e669ed6f5ff43"
changed_hash = source_digest(ROOT)
workers = {}
lines = ["M7 alternating comparison: 100 trials, seed=20260929, budget=5",
         "Baseline source/harness: " + source_digest(baseline), "Cached source/harness: " + changed_hash,
         "Separate persistent Python workers; alternating order per repetition; five pairs per case.",
         "One full warm-up per worker/case. Fixture creation, GC, digest/encoding/IPC/startup outside timing.",
         "Memory/profile measured separately by profile_m7.py; this comparison measures only wall time."]
try:
    for name, directory in (("before", baseline / "src"), ("cached", ROOT / "src")):
        env = dict(os.environ, PYTHONPATH=str(directory))
        worker = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "worker"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
        workers[name] = worker
        loaded = json.loads(worker.stdout.readline())["loaded"]
        assert Path(loaded).resolve().is_relative_to(directory.resolve())
        lines.append(name + " module: " + loaded)
    def run(name, case):
        worker = workers[name]
        worker.stdin.write(json.dumps(case) + "\n")
        worker.stdin.flush()
        return json.loads(worker.stdout.readline())
    for case in CASES:
        reference = run("before", case)
        assert {k:v for k,v in run("cached",case).items() if k != "time"} == {k:v for k,v in reference.items() if k != "time"}
        times = {name: [] for name in workers}
        for i in range(5):
            order = ("before", "cached") if i % 2 == 0 else ("cached", "before")
            for name in order:
                value = run(name, case)
                assert {k:v for k,v in value.items() if k != "time"} == {k:v for k,v in reference.items() if k != "time"}
                times[name].append(value["time"])
        lines.append(json.dumps({"case": case, "times": times,
            "medians": {name: median(values) for name, values in times.items()},
            "digest": reference["digest"], "counts": reference["counts"]}))
    assert source_digest(baseline) == "529d908bbfa1885419038f94845dfcf3718db6d663e807d8252e669ed6f5ff43"
    assert source_digest(ROOT) == changed_hash
finally:
    for worker in workers.values():
        worker.stdin.close()
        worker.wait(timeout=30)
        assert worker.returncode == 0
print("\n".join(lines))
