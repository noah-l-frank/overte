#!/usr/bin/env python3
"""Verify the unapplied Qt source patch on private copies; never build Qt."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile


REPO = Path(__file__).resolve().parents[3]
MANIFEST = REPO / 'tests/device/ios/qt-qml-source-patch.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def original(path):
    before = path.lstat()
    require(path.is_file() and not path.is_symlink(), 'Reference must be a regular file')
    require(before.st_size <= 262144, 'Reference exceeds the reviewed size bound')
    data = path.read_bytes()
    after = path.lstat()
    def pins(value):
        return tuple(getattr(value, field) for field in ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid',
            'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))
    require(pins(before) == pins(after), 'Reference changed during inspection')
    return data, pins(after)


def verify(source_root, scratch_parent):
    manifest = json.loads(MANIFEST.read_text())
    require(set(manifest) == {'qtVersion', 'apiVersion', 'patch', 'sourceSha256', 'referenceSha256'}
        and manifest['qtVersion'] == '6.11.1' and type(manifest['apiVersion']) is int
        and manifest['apiVersion'] == 1, 'Unreviewed patch manifest')
    changed = manifest['sourceSha256']
    refs = manifest['referenceSha256']
    require(type(changed) is dict and len(changed) == 5 and type(refs) is dict and len(refs) == 3
        and not changed.keys() & refs.keys(), 'Unreviewed reference inventory')
    require(type(manifest['patch']) is str and Path(manifest['patch']).name == manifest['patch'],
        'Unreviewed patch filename')
    source_root = Path(source_root).resolve(strict=True)
    scratch_parent = Path(scratch_parent).resolve(strict=True)
    owned = (REPO / '.ios-host-tmp').resolve(strict=True)
    require(REPO in owned.parents and (scratch_parent == owned or owned in scratch_parent.parents),
        'Scratch writes must stay inside this worktree private host area')
    patch = REPO / 'ios/patches' / manifest['patch']
    require(patch.parent == REPO / 'ios/patches' and patch.suffix == '.patch', 'Unreviewed patch path')
    patch_data = patch.read_bytes()
    names = re.findall(rb'^--- a/([^\n]+)\n\+\+\+ b/([^\n]+)$', patch_data, re.M)
    require(len(names) == 5 and all(left == right for left, right in names)
        and {left.decode() for left, _ in names} == set(changed), 'Patch escapes its reviewed file inventory')
    inputs = {}
    for name, expected in (changed | refs).items():
        require(type(name) is str and name.startswith('qtdeclarative/src/qml/')
            and '..' not in Path(name).parts and type(expected) is str
            and re.fullmatch('[0-9a-f]{64}', expected), 'Unreviewed source pin')
        path = source_root / name
        require(path.resolve(strict=True) == path, 'Reference path must be canonical')
        data, pins = original(path)
        require(sha(data) == expected, 'Qt source differs from its reviewed SHA-256: ' + name)
        inputs[name] = (data, pins)
    # Preflight is read-only; unknown source cannot create a scratch result.
    target = Path(tempfile.mkdtemp(prefix='qt-qml-patch-check-', dir=scratch_parent))
    target.chmod(0o700)
    for name, (data, _pins) in inputs.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(data)
        path.chmod(0o600)
    directory = str(target.relative_to(REPO))
    command = ['git', 'apply', '--whitespace=error-all', '--directory=' + directory]
    for options in (['--check'], []):
        result = subprocess.run(command + options + [str(patch)], cwd=REPO, capture_output=True, text=True)
        require(result.returncode == 0, 'Private source patch application failed: ' + result.stderr.strip())
    # A real reverse check additionally verifies the resulting patch boundary.
    result = subprocess.run(command + ['--reverse', '--check', str(patch)], cwd=REPO,
        capture_output=True, text=True)
    require(result.returncode == 0, 'Private source reverse check failed: ' + result.stderr.strip())
    outputs = {name: sha((target / name).read_bytes()) for name in inputs}
    require(all(outputs[name] != changed[name] for name in changed)
        and all(outputs[name] == refs[name] for name in refs), 'Unexpected private output membership')
    for name, (data, pins) in inputs.items():
        require(original(source_root / name) == (data, pins), 'Read-only Qt reference changed')
    report = dict(qtSourcePatchCheckVersion=1, expectedQtVersion=manifest['qtVersion'],
        declaredApiVersion=manifest['apiVersion'], patchSha256=sha(patch_data),
        originalSha256=changed | refs, appliedSha256=outputs, sourceOriginalsUnchanged=True,
        privateApplicationChecked=True, reverseApplicationChecked=True,
        runtimeApiVerified=False, nativeCompilationVerified=False, deviceQualified=False)
    path = target / 'source-patch-check.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    path.chmod(0o600)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path,
        help='Read-only source root containing the exact reviewed qtdeclarative files')
    parser.add_argument('--scratch-parent', required=True, type=Path,
        help='Existing private directory beneath this worktree .ios-host-tmp')
    arguments = parser.parse_args()
    try:
        report = verify(arguments.source_root, arguments.scratch_parent)
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + '\n')
    print('PASS: patch/reverse verified only on private source copies; no compilation or runtime check')
    print(report)


if __name__ == '__main__':
    main()
