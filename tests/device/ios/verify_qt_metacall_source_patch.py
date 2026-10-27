"""Check the optional QtCore patch on private copies; never compile or execute Qt."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import hashlib
import json
import re
import stat
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[3]
OWNED = REPO / '.ios-host-tmp'
MANIFEST = REPO / 'tests/device/ios/qt-metacall-source-patch.json'
EXPECTED_NAMES = {'qtbase/src/corelib/kernel/qobject_p.h',
                  'qtbase/src/corelib/kernel/qobject.cpp',
                  'qtbase/src/corelib/kernel/qmetaobject.cpp'}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def original(path):
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and not path.is_symlink()
            and before.st_size <= 262144, 'Unreviewed reference file')
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink',
              'st_size', 'st_mtime_ns', 'st_ctime_ns')
    pin = lambda item: tuple(getattr(item, field) for field in fields)
    data = path.read_bytes()
    require(pin(before) == pin(path.lstat()), 'Reference changed while read')
    return data, pin(before)


def verify(source_root, scratch_parent):
    manifest = json.loads(MANIFEST.read_text())
    require(set(manifest) == {'qtVersion', 'apiVersion', 'patch', 'sourceSha256'}
            and manifest['qtVersion'] == '6.11.1' and type(manifest['apiVersion']) is int
            and manifest['apiVersion'] == 1, 'Unreviewed Qt/API version')
    expected = manifest['sourceSha256']
    require(type(expected) is dict and set(expected) == EXPECTED_NAMES
            and all(type(value) is str and re.fullmatch('[0-9a-f]{64}', value)
                    for value in expected.values()), 'Unreviewed source inventory')
    require(manifest['patch'] == 'qtbase-overte-e2e-metacall-receipts.patch',
            'Unreviewed patch path')
    patch_path = REPO / 'ios/patches' / manifest['patch']
    source_root = Path(source_root).resolve(strict=True)
    scratch_parent = Path(scratch_parent).resolve(strict=True)
    owned = OWNED.resolve(strict=True)
    require(scratch_parent == owned or owned in scratch_parent.parents,
            'Scratch writes must remain within this worktree .ios-host-tmp')
    require(patch_path.resolve(strict=True) == patch_path, 'Noncanonical patch path')
    patch, patch_pins = original(patch_path)
    names = re.findall(rb'^--- a/([^\n]+)\n\+\+\+ b/([^\n]+)$', patch, re.M)
    require(len(names) == 3 and all(a == b for a, b in names)
            and {a.decode() for a, _ in names} == set(expected), 'Unexpected patch inventory')
    inputs = {}
    for name, digest in expected.items():
        path = source_root / name
        require(path.resolve(strict=True) == path, 'Noncanonical reference path')
        inputs[name] = original(path)
        require(sha(inputs[name][0]) == digest, 'Unknown Qt source: ' + name)
    # No result creation or git call occurs until every immutable source is accepted.
    target = Path(tempfile.mkdtemp(prefix='metacall-private-check-', dir=scratch_parent))
    target.chmod(0o700)
    for name, (data, _) in inputs.items():
        output = target / name
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        output.write_bytes(data)
        output.chmod(0o600)
    command = ['git', 'apply', '--whitespace=error-all',
               '--directory=' + str(target.relative_to(REPO))]
    for options in (['--check'], [], ['--reverse', '--check'], ['--reverse']):
        result = subprocess.run(command + options + [str(patch_path)], cwd=REPO,
                                capture_output=True, text=True, timeout=10)
        require(result.returncode == 0, 'Private apply/reverse failed: ' + result.stderr)
    for name, (data, pins) in inputs.items():
        require((target / name).read_bytes() == data, 'Reverse did not restore exact original')
        require(original(source_root / name) == (data, pins), 'Read-only original changed')
    require(original(patch_path) == (patch, patch_pins), 'Private patch changed during check')
    report = dict(qtMetaCallSourcePatchCheckVersion=1, qtVersion='6.11.1', apiVersion=1,
                  patchSha256=sha(patch), originalSha256=expected,
                  privateApplicationChecked=True, reverseApplicationChecked=True,
                  exactReverseBytesRestored=True, sourceOriginalsUnchanged=True,
                  nativeCompilationVerified=False, runtimeApiVerified=False,
                  deviceQualified=False, queuedProvenanceVerified=False,
                  argumentDestructionVerified=False, storageRetirementVerified=False)
    path = target / 'source-patch-check.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    path.chmod(0o600)
    return path


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--scratch-parent', required=True, type=Path)
    args = parser.parse_args()
    try:
        report = verify(args.source_root, args.scratch_parent)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, str(error) + '\n')
    print('PASS: private source apply/reverse only; no compilation, runtime or lifetime qualification')
    print(report)


if __name__ == '__main__':
    main()
