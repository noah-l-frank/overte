#!/usr/bin/env python3
"""Export authenticated Android outputs before private build scratch is removed."""
from pathlib import Path, PurePosixPath
import ctypes
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile

REPOSITORY = 'noah-l-frank/overte'
LEAF = 'pr-ci-android-export'
SHA = re.compile('[a-f0-9]{64}')
GIT = re.compile('[a-f0-9]{40}')
OWNER = {'android-main': 'common', 'android-vr': 'common', 'android-phone': 'phone', 'android-vr-pico': 'pico'}
MAX_FILE = 2 * 1024 ** 3
MAX_TOTAL = 8 * 1024 ** 3
MAX_JSON = 16_000_000


def require(ok, message):
    if not ok:
        raise ValueError(message)


def unique(rows):
    result = {}
    for key, value in rows:
        require(key not in result, 'Duplicate artifact receipt field')
        result[key] = value
    return result


def directory(value):
    path = Path(value)
    require(path.is_absolute() and path.resolve(strict=True) == path and not path.is_symlink()
            and stat.S_ISDIR(path.lstat().st_mode), 'Artifact root must be an ordinary canonical directory')
    return path


def destination():
    temporary = directory(os.environ.get('RUNNER_TEMP', ''))
    require(temporary.stat().st_uid == os.getuid(), 'Artifact temporary root has another owner')
    expected = temporary / LEAF
    require(os.environ.get('PR_CI_ANDROID_NATIVE_EXPORT') == str(expected),
            'Selected native execution requires the fixed trusted artifact destination')
    require(not expected.exists() and not expected.is_symlink(), 'Artifact destination already exists')
    return expected


def relative(value):
    require(type(value) is str, 'Artifact path must be text')
    path = PurePosixPath(value)
    require(path.parts and not path.is_absolute() and str(path) == value
            and '..' not in path.parts and '.' not in path.parts and '\\' not in value
            and '\0' not in value, 'Unsafe artifact path')
    return path


def open_source(root, name):
    """Never follow an alias at any component, including a regular-file leaf."""
    parts = relative(name).parts
    parent = os.open(directory(root), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            os.close(parent)
            parent = child
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            info = os.fstat(descriptor)
            require(stat.S_ISREG(info.st_mode) and 0 <= info.st_size <= MAX_FILE,
                    'Artifact source is not a bounded regular file')
            return descriptor, info
        except BaseException:
            os.close(descriptor)
            raise
    finally:
        os.close(parent)


def identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mode, info.st_mtime_ns, info.st_ctime_ns


def read_source(root, name, limit=MAX_JSON):
    descriptor, before = open_source(root, name)
    try:
        require(before.st_size <= limit, 'Artifact receipt exceeds bound')
        with os.fdopen(descriptor, 'rb', closefd=False) as stream:
            raw = stream.read(limit + 1)
        require(len(raw) <= limit and identity(before) == identity(os.fstat(descriptor)), 'Artifact receipt changed while reading')
        return raw
    finally:
        os.close(descriptor)


def bound_context(context, product, candidate):
    require(OWNER.get(context.get('target')) == product and GIT.fullmatch(context.get('original_merge', ''))
            and GIT.fullmatch(context.get('tree', '')) and GIT.fullmatch(context.get('controller', '')),
            'Artifact source/product/controller binding differs')
    require(all(type(context.get(key)) is int and context[key] > 0 for key in ('run_id', 'run_attempt')),
            'Artifact run and attempt identity required')
    candidate = directory(candidate)
    require((candidate / '.git').is_dir() and not (candidate / '.git').is_symlink(), 'Artifact source requires ordinary Git metadata')
    environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    environment.update(GIT_NO_REPLACE_OBJECTS='1', GIT_NO_LAZY_FETCH='1', GIT_OPTIONAL_LOCKS='0',
                       GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null')
    observed = subprocess.check_output(['/usr/bin/git', '--no-replace-objects', '-C', str(candidate),
                                        'rev-parse', '--verify', 'HEAD'], env=environment, timeout=30).decode().strip()
    tree = subprocess.check_output(['/usr/bin/git', '--no-replace-objects', '-C', str(candidate),
                                    'rev-parse', '--verify', 'HEAD^{tree}'], env=environment, timeout=30).decode().strip()
    require(observed == context['original_merge'] and tree == context['tree'], 'Artifact candidate Git identity changed')
    return candidate


def envelope(context, product, status):
    return {'kind': 'overte-android-native-build-artifacts-v1', 'repository': REPOSITORY,
            'status': status, 'product': product, 'target': context['target'],
            'controller': context['controller'], 'run_id': context['run_id'], 'run_attempt': context['run_attempt'],
            'candidate_sha': context['original_merge'], 'candidate_tree': context['tree']}


def copy_file(root, source, stage, target, expected, entries, total):
    require(SHA.fullmatch(expected), 'Expected artifact SHA256 required')
    descriptor, before = open_source(root, source)
    try:
        require(before.st_size + total <= MAX_TOTAL, 'Android artifact export exceeds total bound')
        output = stage / str(relative(target))
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        checksum = hashlib.sha256()
        with os.fdopen(descriptor, 'rb', closefd=False) as incoming, output.open('xb') as outgoing:
            os.chmod(output, 0o600)
            while True:
                data = incoming.read(1024 ** 2)
                if not data:
                    break
                require(outgoing.tell() + len(data) <= before.st_size, 'Artifact grew during export')
                checksum.update(data)
                outgoing.write(data)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        require(output.stat().st_size == before.st_size and checksum.hexdigest() == expected
                and identity(before) == identity(os.fstat(descriptor)), 'Artifact bytes changed or differ from protected receipt')
        entries.append({'path': target, 'bytes': before.st_size, 'sha256': expected,
                        'source_mode': format(stat.S_IMODE(before.st_mode), '04o'), 'export_mode': '0600'})
        return total + before.st_size
    finally:
        os.close(descriptor)


def write_json(path, value):
    with path.open('x') as stream:
        os.chmod(path, 0o600)
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def commit(stage, target):
    """Linux no-replace directory publication; never overwrite an existing sink."""
    # Persist nested directory entries as well as file contents before the
    # no-replace publication makes the complete manifest visible.
    for path, _, _ in os.walk(stage, topdown=False, followlinks=False):
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    parent = os.open(directory(target.parent), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        library = ctypes.CDLL(None, use_errno=True)
        operation = library.renameat2
        operation.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        operation.restype = ctypes.c_int
        if operation(parent, os.fsencode(stage.name), parent, os.fsencode(target.name), 1) != 0:
            code = ctypes.get_errno()
            raise OSError(code, 'Atomic artifact publication failed')
        os.fsync(parent)
    finally:
        os.close(parent)


def stage_for(target, candidate, scratch):
    require(target == destination(), 'Artifact sink differs from trusted workflow destination')
    for root in (candidate, scratch):
        require(not (target.is_relative_to(root) or root.is_relative_to(target)), 'Artifact sink overlaps execution inputs')
    return Path(tempfile.mkdtemp(prefix='.pr-ci-android-export-staging-', dir=target.parent))


def export_success(target, candidate, scratch, config, context, result):
    product = result.get('product')
    require(SHA.fullmatch(result.get('toolchain_image_archive_sha256', '')), 'Artifact image identity required')
    candidate = bound_context(context, product, candidate)
    scratch = directory(scratch)
    config = Path(config)
    raw = read_source(scratch, 'android-native-execution.json')
    protected = json.loads(raw, object_pairs_hook=unique)
    require(result == dict(protected, toolchain_image_archive_sha256=result.get('toolchain_image_archive_sha256')),
            'Artifact result differs from protected worker bytes')
    require(protected.get('kind') == 'overte-android-offline-consumer-result-v1' and protected.get('result') == 'success'
            and protected.get('product') == product and protected.get('candidate_sha') == context['original_merge']
            and protected.get('candidate_tree') == context['tree'] and protected.get('actual_build_exit_code') == 0
            and bool(protected.get('executed_build_commands')) and protected.get('device_tested') is False
            and protected.get('apk_qualified') is (product != 'common'), 'Unverified native result cannot be exported as success')
    output_name = {'common': 'common-native-receipt.json', 'phone': 'phone-native-apk-receipt.json',
                   'pico': 'pico-unsigned-receipt.json'}[product]
    output_raw = read_source(scratch, output_name)
    output = json.loads(output_raw, object_pairs_hook=unique)
    require(hashlib.sha256(output_raw).hexdigest() == protected.get('output_receipt_sha256')
            and output == protected.get('output_receipt') and output.get('candidate_sha') == context['original_merge']
            and output.get('candidate_tree') == context['tree'], 'Owning output receipt differs from protected execution')
    config_raw = read_source(config.parent, config.name)
    configuration = json.loads(config_raw, object_pairs_hook=unique)
    require(hashlib.sha256(config_raw).hexdigest() == protected.get('config_sha256')
            and configuration.get('product') == product and configuration.get('candidate_tree') == context['tree'],
            'Artifact configuration source binding differs')
    copies = [(scratch, 'android-native-execution.json', 'receipts/execution.json', hashlib.sha256(raw).hexdigest()),
              (scratch, output_name, 'receipts/output.json', hashlib.sha256(output_raw).hexdigest()),
              (config.parent, config.name, 'receipts/consumer.json', hashlib.sha256(config_raw).hexdigest())]
    if product == 'common':
        rows = output.get('outputs')
        require(output.get('scope') == 'parent-owned-android-common-native-elf' and type(rows) is list
                and 0 < len(rows) <= 256 and len({row.get('path') for row in rows}) == len(rows), 'Missing or duplicate common native outputs')
        for row in rows:
            name = str(relative(row['path']))
            require(name.endswith('.so'), 'Common output must be a native shared library')
            copies.append((scratch / 'common-native-build', name, 'outputs/common/' + name, row['sha256']))
    else:
        require(output.get('status') == product.upper() + '_UNSIGNED_CI_APK_OUTPUT_VERIFIED'
                and output.get('unsigned') is True, 'Owning unsigned APK acceptance missing')
        owner, app = ('android/phone', 'phoneInterface') if product == 'phone' else ('android/vr/pico', 'picoInterface')
        name = owner + '/apps/' + app + '/build/outputs/apk/release/' + app + '-release-unsigned.apk'
        copies.append((candidate, name, 'outputs/' + product + '-release-unsigned.apk', output['apk_sha256']))
    # Bound actual required extra storage before creating copies; this gate only
    # adds capacity requirements and never relaxes the protected phase budgets.
    needed = 0
    for root, name, _, _ in copies:
        fd, info = open_source(root, name)
        os.close(fd)
        needed += info.st_size
    require(needed <= MAX_TOTAL, 'Artifact outputs exceed total bound')
    space = os.statvfs(target.parent)
    require(space.f_bavail * space.f_frsize >= needed + 64 * 1024 ** 2, 'Insufficient space to preserve native artifacts')
    stage = stage_for(target, candidate, scratch)
    entries, total = [], 0
    for root, name, output_path, expected in copies:
        total = copy_file(root, name, stage, output_path, expected, entries, total)
    manifest = dict(envelope(context, product, 'verified'), artifact_preservation_complete=True,
                    recovery_data_retained=False, total_bytes=total, entries=entries,
                    config_sha256=protected['config_sha256'], protected_execution_sha256=hashlib.sha256(raw).hexdigest(),
                    protected_output_sha256=protected['output_receipt_sha256'],
                    toolchain_image_archive_sha256=result['toolchain_image_archive_sha256'])
    write_json(stage / 'manifest.json', manifest)
    commit(stage, target)
    return {'path': str(target), 'manifest_sha256': hashlib.sha256((target / 'manifest.json').read_bytes()).hexdigest(),
            'total_bytes': total, 'files': len(entries)}


def export_failure(target, candidate, scratch, config, context, product, error):
    """Diagnostics are explicitly incomplete; failed sessions stay for recovery."""
    stage = stage_for(target, directory(candidate), directory(scratch))
    manifest = dict(envelope(context, product, 'failed'), artifact_preservation_complete=False,
                    recovery_data_retained=True, recovery_scratch=str(scratch), entries=[], total_bytes=0,
                    error_type=type(error).__name__, qualification_claim=False)
    if config is not None and Path(config).is_file() and not Path(config).is_symlink():
        raw = read_source(Path(config).parent, Path(config).name)
        manifest['total_bytes'] = copy_file(Path(config).parent, Path(config).name, stage,
                                           'diagnostics/consumer.json', hashlib.sha256(raw).hexdigest(), manifest['entries'], 0)
    # Only fixed, bounded textual diagnostics are copied. Complete runner stdout
    # is archived separately by the supervising runner controller. Candidate
    # log paths never become arbitrary traversal or recursive export authority.
    for name in ('CMakeCache.txt', 'CMakeFiles/CMakeConfigureLog.yaml',
                 'CMakeFiles/CMakeError.log', 'CMakeFiles/CMakeOutput.log'):
        try:
            raw = read_source(scratch, 'common-native-build/' + name, limit=8 * 1024 ** 2)
        except (OSError, ValueError):
            continue
        manifest['total_bytes'] = copy_file(scratch, 'common-native-build/' + name, stage,
            'diagnostics/common/' + name, hashlib.sha256(raw).hexdigest(),
            manifest['entries'], manifest['total_bytes'])
    write_json(stage / 'failure.json', manifest)
    write_json(stage / 'manifest.json', manifest)
    commit(stage, target)
    return target
