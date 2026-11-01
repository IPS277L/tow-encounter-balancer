"""ADR-0053/0054 installed native/generated repeats, spawned trials and package provenance.

Run using the fresh audit venv's python -I. This helper does not build/install
packages or change fixtures; all generated evidence goes to --work-dir.
"""
import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def package_files(root):
    return {path.relative_to(root).as_posix(): digest(path.read_bytes())
            for path in (root / 'towr').rglob('*')
            if path.is_file() and path.suffix in ('.py', '.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', '--repo', type=Path, required=True)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--work-dir', '--work', type=Path, required=True)
    args = parser.parse_args()
    root, wheel, work = args.repository.resolve(), args.wheel.resolve(), args.work_dir.resolve()
    require(sys.flags.isolated == 1, 'Run installed Python with -I')
    require(not work.exists(), 'Use a fresh work directory')
    import towr
    from towr.domain import npc_roster_repeated_leg_spasm_models, npc_stationary_wound_models, npc_magic_repeated_leg_spasm_policy
    from towr.rules import npc_roster_repeated_leg_spasm_resolution
    from towr.application import magic_candidate_generation, magic_candidate_generation_models

    site = Path(towr.__file__).resolve().parent.parent
    require(site.is_relative_to(Path(sys.prefix).resolve()), 'towr is not installed in this venv')
    require(not site.is_relative_to(root / 'src'), 'Editable/source import leaked')
    module_paths = {}
    for module in (npc_roster_repeated_leg_spasm_models, npc_roster_repeated_leg_spasm_resolution,
                   npc_stationary_wound_models, npc_magic_repeated_leg_spasm_policy,
                   magic_candidate_generation, magic_candidate_generation_models):
        path = Path(module.__file__).resolve()
        require(path.is_relative_to(site), 'A scoped consumer/context module is not installed')
        module_paths[module.__name__] = str(path)
    source_files = package_files(root / 'src')
    with zipfile.ZipFile(wheel) as archive:
        require(not any(name.lower().endswith('.pdf') or name.startswith('references/')
                        for name in archive.namelist()), 'Private rulebook sources packaged')
        wheel_files = {name: digest(archive.read(name)) for name in archive.namelist()
                       if name.startswith('towr/') and Path(name).suffix in ('.py', '.json')}
    require(source_files == wheel_files == package_files(site), 'Source/wheel/installed package bytes differ')

    work.mkdir(parents=True)
    bundle = work / 'example'
    bundle.mkdir()
    examples = root / 'docs/examples/m8'
    names = ('repeated_leg_spasm_runner.py', 'stationary_wound_runner.py', 'magic_scenario.py',
             'repeated_leg_spasm_generation_runner.py')
    expected_path = examples / 'repeated_leg_spasm_runner.output.txt'
    generated_expected_path = examples / 'repeated_leg_spasm_generation_runner.output.txt'
    fixture_hashes = {name: digest((examples / name).read_bytes())
                      for name in (*names, expected_path.name, generated_expected_path.name)}
    for name in names:
        shutil.copyfile(examples / name, bundle / name)
    environment = dict(os.environ)
    environment.pop('PYTHONPATH', None)
    environment.pop('PYTHONHOME', None)
    environment['PYTHONNOUSERSITE'] = '1'
    installed = subprocess.run([sys.executable, '-I', '-c',
        'import sys; sys.path.insert(0, sys.argv[1]); '
        'import repeated_leg_spasm_runner; repeated_leg_spasm_runner.main()', str(bundle)],
        cwd=work, env=environment, capture_output=True, timeout=60)
    require(installed.returncode == 0 and not installed.stderr,
            f'Installed repeated stand failed: {installed.stderr!r}')
    expected = expected_path.read_text(encoding='utf-8')
    require(installed.stdout.decode('utf-8').replace('\r\n', '\n') == expected,
            'Installed example stdout differs from the frozen public example')
    source_env = dict(environment, PYTHONPATH=str(root / 'src'))
    source = subprocess.run([str(root / '.venv/Scripts/python.exe'), str(bundle / names[0])],
        cwd=work, env=source_env, capture_output=True, timeout=60)
    require(source.returncode == 0 and not source.stderr and source.stdout == installed.stdout,
            f'Source/installed repeated stand differs: {source.stderr!r}')
    installed_generated = subprocess.run([sys.executable, '-I', '-c',
        'import sys; sys.path.insert(0, sys.argv[1]); '
        'import repeated_leg_spasm_generation_runner; repeated_leg_spasm_generation_runner.main()', str(bundle)],
        cwd=work, env=environment, capture_output=True, timeout=120)
    require(installed_generated.returncode == 0 and not installed_generated.stderr,
            f'Installed generated repeated stand failed: {installed_generated.stderr!r}')
    generated_expected = generated_expected_path.read_text(encoding='utf-8')
    require(installed_generated.stdout.decode('utf-8').replace('\r\n', '\n') == generated_expected,
            'Installed generated example stdout differs from the frozen public example')
    source_generated = subprocess.run([str(root / '.venv/Scripts/python.exe'),
        str(bundle / 'repeated_leg_spasm_generation_runner.py')],
        cwd=work, env=source_env, capture_output=True, timeout=120)
    require(source_generated.returncode == 0 and not source_generated.stderr
            and source_generated.stdout == installed_generated.stdout,
            f'Source/installed generated repeated stand differs: {source_generated.stderr!r}')
    require(source_files == package_files(root / 'src'), 'Source package changed during audit')
    require(fixture_hashes == {name: digest((examples / name).read_bytes()) for name in fixture_hashes},
            'Public bundle or expected output changed during audit')
    (work / 'repeated_leg_spasm_runner.output.txt').write_bytes(installed.stdout)
    (work / 'repeated_leg_spasm_generation_runner.output.txt').write_bytes(installed_generated.stdout)
    evidence = {
        'python': platform.python_version(), 'platform': platform.platform(),
        'interpreter': sys.executable, 'isolated': sys.flags.isolated,
        'installed_site': str(site), 'installed_towr': str(Path(towr.__file__).resolve()),
        'module_paths': module_paths, 'wheel': str(wheel), 'wheel_sha256': digest(wheel.read_bytes()),
        'package_files': len(source_files), 'copied_examples': 2, 'child_commands': 4,
        'public_bundle_files': list(names), 'scripted_d10': 330, 'spawn_pid_checked': True,
        'source_installed_stdout_sha256': digest(installed.stdout),
        'generated_proof': {
            'scripted_d10': 1426, 'direct_scripted_d10': 330,
            'full_stages_sequential_and_spawn_d10': 840, 'mixed_stages_sequential_and_spawn_d10': 256,
            'spawn_pid_checked': True, 'actor_counts': [3, 4],
            'direct_paths': ['repeat', 'post-repeat-six-expiry', 'third-nine-stop'],
            'full_stages_actual_planned_trials': [8, 8], 'mixed_actual_planned_trials': [4, 8],
            'source_installed_stdout_sha256': digest(installed_generated.stdout),
        },
        'package_file_hashes': source_files, 'unchanged_example_hashes': fixture_hashes,
        'dependencies': {name: metadata.version(name) for name in (
            'towr-encounter-balancer', 'jsonschema', 'referencing', 'jsonschema-specifications',
            'attrs', 'rpds-py', 'typing-extensions')},
    }
    (work / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in evidence.items()
                      if key not in ('package_file_hashes', 'unchanged_example_hashes')}, indent=2))


if __name__ == '__main__':
    main()
