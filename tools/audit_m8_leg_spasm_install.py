"""ADR-0048 source/wheel/installed parity and copied public example.

Run with the fresh audit environment's python -I. Evidence goes to --work-dir;
repository fixtures and installed packages are read-only during this check.
"""
import argparse
import hashlib
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
    return {p.relative_to(root).as_posix(): digest(p.read_bytes())
            for p in (root / 'towr').rglob('*')
            if p.is_file() and p.suffix in ('.py', '.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--example', choices=('leg_spasm_stand', 'stationary_wound_continuation', 'stationary_wound_runner'),
                        default='leg_spasm_stand')
    args = parser.parse_args()
    root, wheel, work = args.repository.resolve(), args.wheel.resolve(), args.work_dir.resolve()
    require(sys.flags.isolated == 1, 'Run installed Python with -I')
    require(not work.exists(), 'Use a fresh work directory')
    import towr
    from towr.domain import npc_roster_leg_spasm_models
    from towr.rules import npc_roster_leg_spasm_resolution

    site = Path(towr.__file__).resolve().parent.parent
    require(site.is_relative_to(Path(sys.prefix).resolve()), 'towr is not in this venv')
    require(not site.is_relative_to(root / 'src'), 'Editable/source import leaked')
    for module in (npc_roster_leg_spasm_models, npc_roster_leg_spasm_resolution):
        require(Path(module.__file__).resolve().is_relative_to(site), 'New module not installed')
    source_files = package_files(root / 'src')
    with zipfile.ZipFile(wheel) as archive:
        require(not any(n.lower().endswith('.pdf') or n.startswith('references/')
                        for n in archive.namelist()), 'Private rulebook sources packaged')
        wheel_files = {n: digest(archive.read(n)) for n in archive.namelist()
                       if n.startswith('towr/') and Path(n).suffix in ('.py', '.json')}
    require(source_files == wheel_files == package_files(site), 'Package bytes differ')
    work.mkdir(parents=True)
    bundle = work / 'example'
    bundle.mkdir()
    names = ('leg_spasm_stand.py', 'magic_scenario.py')
    if args.example in ('stationary_wound_continuation', 'stationary_wound_runner'):
        from towr.domain import npc_stationary_wound_models
        require(Path(npc_stationary_wound_models.__file__).resolve().is_relative_to(site),
                'Stationary context is not installed')
        names = (('stationary_wound_continuation.py', *names)
                 if args.example == 'stationary_wound_continuation'
                 else ('stationary_wound_runner.py', 'magic_scenario.py'))
    for name in names:
        shutil.copyfile(root / 'docs/examples/m8' / name, bundle / name)
    environment = dict(os.environ)
    environment.pop('PYTHONPATH', None)
    environment.pop('PYTHONHOME', None)
    environment['PYTHONNOUSERSITE'] = '1'
    command = [sys.executable, '-I', '-c',
               'import sys; sys.path.insert(0, sys.argv[1]); '
               f'import {args.example}; {args.example}.main()', str(bundle)]
    installed = subprocess.run(command, cwd=work, env=environment,
                               capture_output=True, timeout=30)
    require(installed.returncode == 0 and not installed.stderr,
            f'Installed example failed: {installed.stderr!r}')
    expected = (root / f'docs/examples/m8/{args.example}.output.txt').read_text(encoding='utf-8')
    actual = installed.stdout.decode('utf-8').replace('\r\n', '\n')
    require(actual == expected, 'Installed example stdout differs')
    source_env = dict(environment, PYTHONPATH=str(root / 'src'))
    source = subprocess.run([str(root / '.venv/Scripts/python.exe'), str(bundle / f'{args.example}.py')],
                            cwd=work, env=source_env, capture_output=True, timeout=30)
    require(source.returncode == 0 and not source.stderr and source.stdout == installed.stdout,
            f'Source/installed example differs: {source.stderr!r}')
    require(source_files == package_files(root / 'src'), 'Source changed during audit')
    (work / f'{args.example}.output.txt').write_text(actual, encoding='utf-8')
    evidence = dict(python=platform.python_version(), platform=platform.platform(),
                    installed_site=str(site), wheel_sha256=digest(wheel.read_bytes()),
                    package_files=len(source_files), copied_examples=1, child_commands=2,
                    public_bundle_files=sorted(p.name for p in bundle.glob('*.py')), example=args.example)
    (work / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
