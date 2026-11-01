"""ADR-0052 installed full-owner second stand and exact package provenance.

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
    from towr.domain import npc_roster_repeated_leg_spasm_models, npc_stationary_wound_models
    from towr.rules import npc_roster_repeated_leg_spasm_resolution

    site = Path(towr.__file__).resolve().parent.parent
    require(site.is_relative_to(Path(sys.prefix).resolve()), 'towr is not installed in this venv')
    require(not site.is_relative_to(root / 'src'), 'Editable/source import leaked')
    module_paths = {}
    for module in (npc_roster_repeated_leg_spasm_models, npc_roster_repeated_leg_spasm_resolution,
                   npc_stationary_wound_models):
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
    names = ('repeated_leg_spasm_stand.py', 'stationary_wound_runner.py', 'magic_scenario.py')
    expected_path = examples / 'repeated_leg_spasm_stand.output.txt'
    fixture_hashes = {name: digest((examples / name).read_bytes()) for name in (*names, expected_path.name)}
    for name in names:
        shutil.copyfile(examples / name, bundle / name)
    environment = dict(os.environ)
    environment.pop('PYTHONPATH', None)
    environment.pop('PYTHONHOME', None)
    environment['PYTHONNOUSERSITE'] = '1'
    installed = subprocess.run([sys.executable, '-I', '-c',
        'import sys; sys.path.insert(0, sys.argv[1]); '
        'import repeated_leg_spasm_stand; repeated_leg_spasm_stand.main()', str(bundle)],
        cwd=work, env=environment, capture_output=True, timeout=30)
    require(installed.returncode == 0 and not installed.stderr,
            f'Installed repeated stand failed: {installed.stderr!r}')
    expected = expected_path.read_text(encoding='utf-8')
    require(installed.stdout.decode('utf-8').replace('\r\n', '\n') == expected,
            'Installed example stdout differs from the frozen public example')
    source_env = dict(environment, PYTHONPATH=str(root / 'src'))
    source = subprocess.run([str(root / '.venv/Scripts/python.exe'), str(bundle / names[0])],
        cwd=work, env=source_env, capture_output=True, timeout=30)
    require(source.returncode == 0 and not source.stderr and source.stdout == installed.stdout,
            f'Source/installed repeated stand differs: {source.stderr!r}')
    require(source_files == package_files(root / 'src'), 'Source package changed during audit')
    require(fixture_hashes == {name: digest((examples / name).read_bytes()) for name in fixture_hashes},
            'Public bundle or expected output changed during audit')
    (work / 'repeated_leg_spasm_stand.output.txt').write_bytes(installed.stdout)
    evidence = {
        'python': platform.python_version(), 'platform': platform.platform(),
        'interpreter': sys.executable, 'isolated': sys.flags.isolated,
        'installed_site': str(site), 'installed_towr': str(Path(towr.__file__).resolve()),
        'module_paths': module_paths, 'wheel': str(wheel), 'wheel_sha256': digest(wheel.read_bytes()),
        'package_files': len(source_files), 'copied_examples': 1, 'child_commands': 2,
        'public_bundle_files': list(names), 'scripted_d10': 34,
        'source_installed_stdout_sha256': digest(installed.stdout),
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
