#!/usr/bin/env python3
"""Verify a paused source backup, or restore a selected path into a new directory."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent


def safe_relative(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or any(x in ('', '.', '..') for x in value.split('/')):
        raise ValueError('Unsafe relative path')
    return path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_objects(manifest):
    expected = {row['name']: row for row in manifest['objects']}
    result = {}
    for archive in manifest['archives']:
        safe_relative(archive['path'])
        path = HERE / archive['path']
        if sha(path.read_bytes()) != archive['sha256']:
            raise ValueError('Archive hash mismatch: ' + archive['path'])
        with tarfile.open(path, 'r:gz') as stream:
            for member in stream:
                if not member.isfile() or member.name not in expected or member.name in result:
                    raise ValueError('Unexpected or duplicate archive member')
                data = stream.extractfile(member).read()
                row = expected[member.name]
                if len(data) != row['size'] or sha(data) != row['sha256']:
                    raise ValueError('Object integrity failure')
                result[member.name] = data
    if result.keys() != expected.keys():
        raise ValueError('Missing source object')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['verify', 'restore'])
    parser.add_argument('--prefix', help='Original relative path prefix; stripped on restore')
    parser.add_argument('--destination', type=Path, help='New, nonexistent restore directory')
    args = parser.parse_args()
    if args.action == 'restore' and (not args.prefix or args.destination is None):
        parser.error('restore requires --prefix and --destination')
    manifest = json.loads((HERE / 'manifest.json').read_text())
    if manifest['format'] != 1:
        raise ValueError('Unsupported format')
    objects = load_objects(manifest)
    index_data = (HERE / 'paths.jsonl.gz').read_bytes()
    if sha(index_data) != manifest['indexSha256']:
        raise ValueError('Path index hash mismatch')
    entries = []
    base_cache = {}
    names = set()
    with gzip.open(io.BytesIO(index_data), 'rt') as stream:
        for line in stream:
            row = json.loads(line)
            safe_relative(row['path'])
            if row['path'] in names:
                raise ValueError('Duplicate original path')
            names.add(row['path'])
            if 'basePath' in row:
                safe_relative(row['basePath'])
                key = row['basePath']
                if key not in base_cache:
                    base_cache[key] = subprocess.check_output(
                        ['git', 'show', manifest['baseCommit'] + ':' + key], cwd=HERE)
                data = base_cache[key]
            else:
                data = objects[row['object']]
            if len(data) != row['size'] or sha(data) != row['sha256']:
                raise ValueError('Original source integrity failure: ' + row['path'])
            entries.append((row, data))
    if len(entries) != manifest['retainedPaths']:
        raise ValueError('Path count mismatch')
    if args.action == 'restore':
        prefix = str(safe_relative(args.prefix)).rstrip('/') + '/'
        selected = [(row, data) for row, data in entries if row['path'].startswith(prefix)]
        if not selected:
            raise ValueError('Prefix has no preserved files')
        if args.destination.exists() or args.destination.is_symlink():
            raise ValueError('Restore destination must not exist')
        args.destination.mkdir(parents=True)
        for row, data in selected:
            relative = safe_relative(row['path'][len(prefix):])
            target = args.destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as output:
                output.write(data)
            target.chmod(0o755 if row['mode'] & 0o111 else 0o644)
        print('Restored', len(selected), 'files into', args.destination)
    print('Verified', len(entries), 'original paths and', len(objects), 'unique stored objects')


if __name__ == '__main__':
    main()
