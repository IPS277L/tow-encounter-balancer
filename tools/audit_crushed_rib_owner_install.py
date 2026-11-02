"""ADR-0056 offline package and actual-consumer audit; run fresh Python -I.

Does not build/install or modify fixtures. --work-dir must be new.
"""
import argparse
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


def require(value, message):
    if not value:
        raise AssertionError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def package_files(root):
    return {p.relative_to(root).as_posix(): digest(p.read_bytes())
            for p in (root / 'towr').rglob('*') if p.is_file() and p.suffix in ('.py', '.json')}


def references(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == '$ref':
                yield item
            else:
                yield from references(item)
    elif isinstance(value, list):
        for item in value:
            yield from references(item)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', '--repo', required=True, type=Path)
    parser.add_argument('--wheel', required=True, type=Path)
    parser.add_argument('--work-dir', '--work', required=True, type=Path)
    args = parser.parse_args()
    root, work, wheel_path = args.repository.resolve(), args.work_dir.resolve(), args.wheel.resolve()
    require(sys.flags.isolated == 1, 'Run the installed Python with -I')
    require(not work.exists(), 'Use a fresh evidence directory')
    import towr
    import towr.domain as domain
    from towr.domain import npc_crushed_rib_models
    from towr.rules import npc_roster_shooting_preparation
    site = Path(towr.__file__).resolve().parent.parent
    require(site.is_relative_to(Path(sys.prefix).resolve()), 'Package is outside this venv')
    require(not site.is_relative_to(root / 'src'), 'Source/editable package leaked')
    module_paths = {m.__name__: str(Path(m.__file__).resolve())
                    for m in (npc_crushed_rib_models, npc_roster_shooting_preparation)}
    require(all(Path(p).is_relative_to(site) for p in module_paths.values()), 'Consumer is not installed')
    names = ('NpcCrushedRibContext', 'NpcCrushedRibConsumptionWitness')
    require(all(n in domain.__all__ and getattr(domain, n) is getattr(npc_crushed_rib_models, n)
                for n in names), 'Public domain exports differ')

    source = package_files(root / 'src')
    with zipfile.ZipFile(wheel_path) as archive:
        require(not any(n.lower().endswith('.pdf') or n.startswith('references/') for n in archive.namelist()),
                'Private book sources packaged')
        packaged = {n: digest(archive.read(n)) for n in archive.namelist()
                    if n.startswith('towr/') and Path(n).suffix in ('.py', '.json')}
    require(source == packaged == package_files(site), 'Source/wheel/installed paths or bytes differ')

    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    documents = [json.loads(p.read_text(encoding='utf-8'))
                 for p in resources.files('towr.adapters.schemas').iterdir() if p.name.endswith('.schema.json')]
    registry = Registry().with_resources((d['$id'], Resource.from_contents(d)) for d in documents)
    refs = 0
    for document in documents:
        Draft202012Validator.check_schema(document)
        for ref in references(document):
            registry.resolver(document['$id']).lookup(ref)
            refs += 1
    require(len(documents) == 42 and refs == 444, 'Unexpected wire/schema expansion')

    work.mkdir(parents=True)
    bundle = work / 'examples'
    bundle.mkdir()
    examples = root / 'docs/examples/m8'
    files = ('crushed_rib_owner.py', 'crushed_rib_owner_contract_probe.py',
             'crushed_rib_test.py', 'crushed_rib_test_contract_probe.py',
             'stationary_wound_runner.py', 'generation_contract_probe.py', 'magic_scenario.py')
    hashes = {n: digest((examples / n).read_bytes()) for n in (
        *files, 'crushed_rib_owner.output.txt', 'crushed_rib_owner_contract_probe.output.txt',
        'crushed_rib_test.output.txt', 'crushed_rib_test_contract_probe.output.txt')}
    for name in files:
        shutil.copyfile(examples / name, bundle / name)
    environment = dict(os.environ)
    environment.pop('PYTHONPATH', None)
    environment.pop('PYTHONHOME', None)
    environment['PYTHONNOUSERSITE'] = '1'
    stdout_hashes = {}
    for module in ('crushed_rib_owner', 'crushed_rib_owner_contract_probe',
                   'crushed_rib_test', 'crushed_rib_test_contract_probe'):
        installed = subprocess.run([sys.executable, '-I', '-c',
            f'import sys; sys.path.insert(0, sys.argv[1]); import {module}; {module}.main()', str(bundle)],
            cwd=work, env=environment, capture_output=True, timeout=60)
        require(installed.returncode == 0 and not installed.stderr,
                f'Installed {module} failed: {installed.stderr!r}')
        source_run = subprocess.run([str(root / '.venv/Scripts/python.exe'), str(bundle / (module + '.py'))],
            cwd=work, env=dict(environment, PYTHONPATH=str(root / 'src')), capture_output=True, timeout=60)
        require(source_run.returncode == 0 and not source_run.stderr and source_run.stdout == installed.stdout,
                f'Source/installed {module} differs: {source_run.stderr!r}')
        require(installed.stdout.decode('utf-8').replace('\r\n', '\n') ==
                (examples / (module + '.output.txt')).read_text(encoding='utf-8'), 'Saved stdout differs')
        stdout_hashes[module] = digest(installed.stdout)
        (work / (module + '.actual-output.txt')).write_bytes(installed.stdout)
    require(source == package_files(root / 'src'), 'Package changed during audit')
    require(hashes == {n: digest((examples / n).read_bytes()) for n in hashes}, 'Examples changed during audit')
    require(all(digest((bundle / n).read_bytes()) == hashes[n] for n in files), 'Copied source was mutated')
    evidence = dict(python=platform.python_version(), platform=platform.platform(), interpreter=sys.executable,
        isolated=sys.flags.isolated, installed_site=str(site), module_paths=module_paths,
        wheel=str(wheel_path), wheel_sha256=digest(wheel_path.read_bytes()), package_files=len(source),
        package_file_hashes=source, schemas=len(documents), local_refs=refs, child_commands=8,
        copied_bundle_files=files, example_hashes=hashes, source_installed_stdout_sha256=stdout_hashes,
        scripted_d10=dict(actual_owner=63, owner_contract_probe=25, actual_k1=33, k1_contract_probe=40),
        dependencies={n: metadata.version(n) for n in ('towr-encounter-balancer', 'jsonschema',
            'referencing', 'jsonschema-specifications', 'attrs', 'rpds-py', 'typing-extensions')})
    (work / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in evidence.items() if k not in (
        'package_file_hashes', 'example_hashes')}, indent=2))


if __name__ == '__main__':
    main()
