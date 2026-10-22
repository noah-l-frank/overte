#!/usr/bin/env python3
"""Join protected Android runtime qualification with one offline product build."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pr_ci_android_assets as A
import pr_ci_android_boundary as B
import pr_ci_android_runtime as R
import pr_ci_android_capacity as CAP
import pr_ci_context as C

OWNER = {'android-main': 'common', 'android-vr': 'common',
         'android-phone': 'phone', 'android-vr-pico': 'pico'}


def read_bound(root, reference):
    relative = str(R.relative(reference['path']))
    path = Path(root) / relative
    C.require(path.is_file() and not path.is_symlink()
              and path.resolve(strict=True).is_relative_to(Path(root).resolve(strict=True))
              and R.digest(path) == reference['sha256'], 'Android qualification document differs from protected policy')
    data = path.read_bytes()
    C.require(len(data) <= 150_000_000, 'Android qualification document exceeds its bound')
    return json.loads(data, object_pairs_hook=R.unique)


def products(plan, target):
    selected = plan.get('android_native_products', [])
    C.require(type(selected) is list and selected in ([], [OWNER.get(target)])
              and None not in selected, 'Android native build selected an unowned product')
    return selected


def check_intent(candidate, expected, *, revision=None):
    C.require(type(expected) is dict and bool(expected), 'Missing qualified Android dependency declarations')
    for name, digest in expected.items():
        R.relative(name)
        C.require(type(digest) is str and R.SHA256.fullmatch(digest), 'Invalid Android dependency declaration identity')
        if revision is not None:
            C.sha(revision)
            arguments = ['git', '--no-replace-objects', '-C', str(candidate)]
            mode = subprocess.check_output([*arguments, 'ls-tree', revision, '--', name], timeout=60).split(b' ', 1)[0]
            blob = subprocess.check_output([*arguments, 'cat-file', 'blob', revision + ':' + name], timeout=60)
            C.require(mode in (b'100644', b'100755') and hashlib.sha256(blob).hexdigest() == digest,
                      'Selected immutable Android dependency declarations changed: ' + name)
            continue
        path = Path(candidate) / name
        C.require(path.is_file() and not path.is_symlink()
                  and path.resolve(strict=True).is_relative_to(Path(candidate).resolve(strict=True))
                  and R.digest(path) == digest,
                  'Android dependency declarations changed; qualify the owning dependency graph before PR execution: ' + name)


def prerequisites(candidate, plan, target, *, revision=None):
    """Reject unavailable production infrastructure before any hosted setup."""
    selected = products(plan, target)
    if not selected:
        return A.policy() if plan.get('android_groovy_contracts') else None
    value = A.policy()
    check_intent(candidate, value['products'][selected[0]]['dependency_intent'], revision=revision)
    return value


def validate_prepared(root, definition):
    root = Path(root).resolve(strict=True)
    for name in ('runtime', 'sdk', 'qualification', 'controller'):
        ledger = root / (name + '-inventory.json')
        identity = definition['assets'][name]['inventory']['sha256']
        # The PID-1 worker checks every runtime/SDK byte through its immutable
        # mounts before any candidate execution. Do not repeat those large
        # scans on the host; authenticate their ledgers and small controller
        # documents here. Fresh archive extraction already checks all bytes.
        if name in ('runtime', 'sdk'):
            R.read_inventory(ledger, identity)
        else:
            R.verify(root / name, ledger, identity)
    # The executing worker and its integrity implementation must match the
    # current protected controller as well as the published bundle inventory.
    for name in ('pr_ci_android_worker.py', 'pr_ci_android_runtime.py'):
        relative = 'tools/repository-checks/' + name
        C.require(R.digest(root / 'controller' / relative) == R.digest(A.ROOT / relative),
                  'Prepared Android worker differs from the current protected controller')
    return root


def load_template(root, definition, product):
    specification = definition['products'][product]
    template = read_bound(root / 'qualification', specification['template'])
    baseline = specification['baseline']
    completed = read_bound(root / 'qualification', {
        'path': baseline['receipt_path'], 'sha256': baseline['receipt_sha256']})
    C.require(completed.get('kind') == 'overte-android-offline-consumer-result-v1'
              and completed.get('result') == 'success' and completed.get('product') == product
              and completed.get('candidate_sha') == baseline['source']
              and completed.get('candidate_tree') == baseline['tree']
              and completed.get('device_tested') is False and completed.get('actual_build_exit_code') == 0
              and bool(completed.get('executed_build_commands'))
              and completed.get('apk_qualified') is (product != 'common'),
              'Android runtime lacks the actual owning baseline execution')
    C.require(template.get('product') == product, 'Android consumer template belongs to another product')
    C.require(template.get('candidate_tree') == baseline['tree']
              and completed.get('config_sha256') == specification['template']['sha256']
              and completed.get('runtime_inventory_sha256') == definition['assets']['runtime']['inventory']['sha256']
              and completed.get('sdk_inventory_sha256') == definition['assets']['sdk']['inventory']['sha256']
              and completed.get('toolchain_image_archive_sha256') == definition['assets']['image']['archive']['sha256'],
              'Android baseline qualified different source, runtime, SDK, image or controller inputs')
    C.require(template.get('dependency_intent') == specification['dependency_intent'],
              'Android consumer declaration closure differs from protected policy')
    return template


def load_image(archive, descriptor):
    C.require(A.verified_file(Path(archive), descriptor), 'Android toolchain image archive differs from protected bytes')
    with tempfile.TemporaryDirectory(prefix='overte-android-load-') as client:
        environment = {'PATH': '/usr/bin:/bin', 'HOME': client, 'DOCKER_CONFIG': client,
                       'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}
        try:
            B.image_identity(environment, client)
            return
        except ValueError:
            pass
        subprocess.run(['/usr/bin/docker', '--host=unix:///var/run/docker.sock', 'image', 'load',
                        '--input', str(archive)], env=environment, cwd=client, timeout=300, check=True)
        B.image_identity(environment, client)


def capacity_admission(definition, destination, cache, phase):
    """Check the actual workspace and daemon filesystem before costly work."""
    C.require(definition.get('status') == 'qualified' and phase in {'prepare', 'execute'},
              'Android capacity requires qualified protected policy')
    capacity = definition.get('capacity')
    C.require(type(capacity) is dict and set(capacity) == {'prepare', 'execute'},
              'Android capacity requires both measured phase budgets')
    limit = CAP.budget(capacity[phase])
    with tempfile.TemporaryDirectory(prefix='overte-android-capacity-') as client:
        environment = {'PATH': '/usr/bin:/bin', 'HOME': client, 'DOCKER_CONFIG': client,
                       'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}
        result = subprocess.run(['/usr/bin/docker', '--host=unix:///var/run/docker.sock', 'info',
                                 '--format', '{{json .DockerRootDir}}'], env=environment, cwd=client,
                                timeout=30, check=True, capture_output=True)
    C.require(len(result.stdout) <= 16_384, 'Android Docker root response exceeds its bound')
    docker_root = json.loads(result.stdout)
    C.require(type(docker_root) is str, 'Android Docker root is unavailable')
    return CAP.admit(limit, destination, cache, docker_root)


def prepare(destination, cache):
    definition = A.policy()
    capacity_admission(definition, destination, cache, 'prepare')
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    B.R._private_path(cache.resolve(strict=True), 'Android public asset cache')
    result = A.prepare(definition, destination, cache)
    validate_prepared(destination, definition)
    for product in ('common', 'phone', 'pico'):
        load_template(Path(destination), definition, product)
    load_image(result['image_archive'], definition['assets']['image']['archive'])
    return result


def prepare_groovy(destination, cache):
    """Prepare the small exact host fixture runtime, without native payloads."""
    payload = A.policy()['assets']['groovy']
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    B.R._private_path(cache.resolve(strict=True), 'Android public asset cache')
    archive = A.fetch(payload['archive'], cache)
    ledger = A.fetch(payload['inventory'], cache)
    R.extract(archive, destination, ledger, payload['inventory']['sha256'],
              payload['archive']['sha256'], payload['archive']['bytes'])
    inventory = Path(destination).with_name(Path(destination).name + '-inventory.json')
    C.require(not inventory.exists() and not inventory.is_symlink(), 'Groovy inventory destination already exists')
    shutil.copyfile(ledger, inventory)
    return {'root': str(destination), 'scope': 'selected-pico-host-groovy-contracts', 'build_qualified': False}


def groovy_classpath(root):
    root = Path(root).resolve(strict=True)
    identity = A.policy()['assets']['groovy']['inventory']['sha256']
    value = R.verify(root, root.with_name(root.name + '-inventory.json'), identity)
    jars = [root / name for name, entry in value['entries'].items()
            if name.endswith('.jar') and entry['type'] == 'file']
    C.require(0 < len(jars) <= 32 and all(':' not in str(path) for path in jars), 'Invalid prepared Groovy classpath')
    return ':'.join(str(path) for path in sorted(jars))


def execute(candidate, context, plan, prepared, *, authenticate):
    selected = products(plan, context['target'])
    C.require(len(selected) == 1, 'Unselected Android native execution')
    product = selected[0]
    authenticate()
    definition = A.policy()
    root = validate_prepared(prepared, definition)
    template = load_template(root, definition, product)
    check_intent(candidate, template['dependency_intent'])
    C.require(os.stat(candidate).st_dev == os.stat(root).st_dev,
              'Android source and scratch on separate filesystems are unsupported')
    capacity_admission(definition, root, root, 'execute')
    # Copy only already authenticated public proof data. The run-specific
    # candidate binding is separate from the immutable baseline definition.
    with tempfile.TemporaryDirectory(prefix='android-native-execution-', dir=root) as session:
        session = Path(session)
        qualification, scratch = session / 'qualification', session / 'scratch'
        shutil.copytree(root / 'qualification', qualification, symlinks=True)
        scratch.mkdir()
        configuration = dict(template, candidate_tree=context['tree'])
        config = qualification / 'consumer.json'
        C.require(not config.exists() and not config.is_symlink(), 'Qualification bundle reserves the consumer configuration name')
        config.write_bytes(R.canonical(configuration))
        for name in ('runtime', 'sdk'):
            source = root / (name + '-inventory.json')
            destination = qualification / source.name
            C.require(not destination.exists() and not destination.is_symlink(), 'Qualification bundle shadows a runtime inventory')
            shutil.copyfile(source, destination)
        command = ['python3', '-I', '-S', '-B',
                   '/ci-controller/tools/repository-checks/pr_ci_android_worker.py',
                   '--product', product, '--expected-head', context['original_merge'],
                   '--config', '/qualification/consumer.json', '--config-sha256', R.digest(config)]
        status = B.run(candidate, command, runtime=root / 'runtime', sdk=root / 'sdk', scratch=scratch,
                       controller=root / 'controller', qualification=qualification, product=product)
        C.require(status == 0, 'Selected offline Android native build or product verification failed')
        authenticate()
        receipt = scratch / 'android-native-execution.json'
        C.require(receipt.is_file() and not receipt.is_symlink() and receipt.stat().st_size <= 16_000_000,
                  'Android execution did not produce its protected completion receipt')
        result = json.loads(receipt.read_bytes(), object_pairs_hook=R.unique)
        C.require(result.get('kind') == 'overte-android-offline-consumer-result-v1'
                  and result.get('result') == 'success' and result.get('product') == product
                  and result.get('candidate_sha') == context['original_merge']
                  and result.get('candidate_tree') == context['tree'] and result.get('device_tested') is False,
                  'Android native receipt differs from the selected execution')
        C.require(result.get('config_sha256') == R.digest(config)
                  and result.get('runtime_inventory_sha256') == definition['assets']['runtime']['inventory']['sha256']
                  and result.get('sdk_inventory_sha256') == definition['assets']['sdk']['inventory']['sha256']
                  and result.get('actual_build_exit_code') == 0 and bool(result.get('executed_build_commands'))
                  and result.get('apk_qualified') is (product != 'common'),
                  'Android native receipt differs from the authenticated runtime or actual build')
        # A current same-run result is not blanket reuse authority for a later
        # PR, a different product, or changed dependency declarations.
        result['toolchain_image_archive_sha256'] = definition['assets']['image']['archive']['sha256']
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--groovy-only', action='store_true')
    mode.add_argument('--capacity-only', action='store_true')
    args = parser.parse_args()
    if args.capacity_only:
        result = capacity_admission(A.policy(), args.destination, args.cache, 'prepare')
    else:
        result = (prepare_groovy if args.groovy_only else prepare)(args.destination, args.cache)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
