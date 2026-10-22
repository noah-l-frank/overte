"""Read original native SNAP files from the selected debug app's private root.

The owning adapter supplies its verified candidate/process continuity check.
This observer never discovers/installs a target, starts a capture, chooses its
format or manufactures a file. Artifacts are published only after actual OS
digests match their transferred bytes and nonempty originals remain unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import shlex
import stat

from adb_transport import AdbTransport
from contracts import validate_operation_arguments
from snapshot_observation import MAX_BYTES


class SnapshotFileError(RuntimeError):
    """Closed errors never contain device selectors, filenames or app data."""


# QStandardPaths::AppDataLocation on Android is the application's files root;
# the actual SnapshotStorage.h appends Snapshots. No configurable directory grant.
ROOT = 'files/Snapshots'
LIST_HEADER = 'OVT_SNAPSHOT_FILES_V1'
LIST_FOOTER = 'OVT_SNAPSHOT_FILES_END_V1'
BYTES_HEADER = b'OVT_SNAPSHOT_BYTES_V1\n'
BYTES_FOOTER = b'\nOVT_SNAPSHOT_BYTES_END_V1\n'
LIST_SCRIPT = r'''
printf 'OVT_SNAPSHOT_FILES_V1\n'
snapshot_root=files/Snapshots
[ -d files ] && [ ! -L files ] || exit 1
if [ ! -e "$snapshot_root" ]; then printf 'OVT_SNAPSHOT_FILES_END_V1\n'; exit 0; fi
[ -d "$snapshot_root" ] && [ ! -L "$snapshot_root" ] || exit 1
snapshot_count=0
for snapshot_path in "$snapshot_root"/"$1"-*; do
    [ -e "$snapshot_path" ] || continue
    case "$snapshot_path" in *.png|*.jpg|*.gif) ;; *) continue ;; esac
    [ -f "$snapshot_path" ] && [ ! -L "$snapshot_path" ] || exit 1
    [ "$(stat -c %h "$snapshot_path")" = 1 ] || exit 1
    snapshot_before=$(stat -c '%d %i %f %u %h %s %y %z' "$snapshot_path") || exit 1
    snapshot_count=$((snapshot_count + 1))
    [ "$snapshot_count" -le 8 ] || exit 1
    snapshot_size=$(stat -c %s "$snapshot_path") || exit 1
    [ "$snapshot_size" -ge 0 ] && [ "$snapshot_size" -le "$2" ] || exit 1
    snapshot_hash=$(sha256sum "$snapshot_path") || exit 1
    snapshot_hash=${snapshot_hash%% *}
    snapshot_absolute=$(readlink -f "$snapshot_path") || exit 1
    snapshot_path_hash=$(printf '%s\000%s' "$3" "$snapshot_absolute" | sha256sum) || exit 1
    snapshot_path_hash=${snapshot_path_hash%% *}
    [ ! -L "$snapshot_path" ] && [ "$snapshot_before" = "$(stat -c '%d %i %f %u %h %s %y %z' "$snapshot_path")" ] || exit 1
    snapshot_name=${snapshot_path##*/}
    printf '%s\t%s\t%s\t%s\t%s\n' "$snapshot_name" "$snapshot_size" "$snapshot_hash" "$snapshot_before" "$snapshot_path_hash"
done
printf 'OVT_SNAPSHOT_FILES_END_V1\n'
'''.strip()
READ_SCRIPT = r'''
snapshot_root=files/Snapshots
snapshot_path="$snapshot_root/$1"
[ ! -L files ] && [ -d "$snapshot_root" ] && [ ! -L "$snapshot_root" ] || exit 1
[ -f "$snapshot_path" ] && [ ! -L "$snapshot_path" ] || exit 1
[ "$(stat -c %h "$snapshot_path")" = 1 ] || exit 1
printf 'OVT_SNAPSHOT_BYTES_V1\n'
head -c "$2" "$snapshot_path" || exit 1
printf '\nOVT_SNAPSHOT_BYTES_END_V1\n'
'''.strip()


def original_stat(value,size):
    return (type(value) is str and type(size) is int and size>=0 and re.fullmatch(
        r'[0-9]+ [0-9]+ [0-9a-fA-F]+ [0-9]+ 1 '+str(size)
        +r' \d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{9} [+-]\d{4}'
        +r' \d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{9} [+-]\d{4}',value) is not None)


class AndroidSnapshotFiles:
    def __init__(self, adb, selector, package, context, check_continuity, artifact_directory):
        AdbTransport._validate_debug_app_file(package, ROOT)
        if (not isinstance(selector, str) or not selector or not callable(check_continuity)
                or not isinstance(context, dict) or set(context) != {'sourceRevision', 'artifactSha256', 'processIdentity'}
                or not isinstance(context['sourceRevision'], str) or re.fullmatch('[0-9a-f]{40}', context['sourceRevision']) is None
                or not isinstance(context['artifactSha256'], str) or re.fullmatch('[0-9a-f]{64}', context['artifactSha256']) is None
                or not isinstance(context['processIdentity'], str) or not 1 <= len(context['processIdentity']) <= 160
                or any(ord(character) < 33 or ord(character) == 127 for character in context['processIdentity'])):
            raise SnapshotFileError('Native Snapshot file context is invalid')
        self.adb, self.selector, self.package = adb, selector, package
        self.last_original = None
        self.context = dict(context)
        self.check_continuity = check_continuity
        self.artifacts = Path(artifact_directory)
        if not self.artifacts.is_absolute() or self.artifacts.is_symlink():
            raise SnapshotFileError('Native Snapshot artifact root is invalid')
        self.artifacts.mkdir(parents=True, exist_ok=True, mode=0o700)
        metadata = self.artifacts.lstat()
        if (not stat.S_ISDIR(metadata.st_mode) or os.name != 'nt'
                and (metadata.st_uid != os.geteuid() or metadata.st_mode & 0o077)):
            raise SnapshotFileError('Native Snapshot artifact root is not private')

    def _check(self):
        try:
            if self.check_continuity() is False:
                raise SnapshotFileError('Continuity lost')
        except Exception:
            raise SnapshotFileError('Native Snapshot lost its bound application') from None

    def _execute(self, script, *arguments, timeout=20):
        # ADB joins host argv for the remote shell. Preserve this fixed script
        # and validated positional arguments as one explicitly quoted command.
        remote = ' '.join(shlex.quote(value) for value in
            ('run-as', self.package, 'sh', '-c', script, 'overte-snapshot-files', *arguments))
        self._check()
        try:
            result = self.adb.execute_bytes(['exec-out', remote], target=self.selector, timeout=timeout)
        except Exception:
            raise SnapshotFileError('Native Snapshot file transport failed') from None
        self._check()
        return result

    def _list(self, prefix, run=''):
        validate_operation_arguments('snapshot.files', {'prefix': prefix})
        if type(run) is not str or run and re.fullmatch('[0-9a-f]{32}',run) is None:
            raise SnapshotFileError('Native Snapshot original run is invalid')
        raw = self._execute(LIST_SCRIPT, prefix, str(MAX_BYTES),run)
        if not isinstance(raw, bytes) or len(raw) > 4096:
            raise SnapshotFileError('Native Snapshot file list exceeds its bound')
        try:
            lines = raw.decode('ascii').splitlines()
        except UnicodeError:
            raise SnapshotFileError('Native Snapshot file list is malformed') from None
        # exec-out does not convey the remote command's exit status. Require
        # this fixed success frame, including after a legitimately empty list.
        if len(lines) < 2 or lines[0] != LIST_HEADER or lines[-1] != LIST_FOOTER:
            raise SnapshotFileError('Native Snapshot file list did not complete')
        lines = lines[1:-1]
        if len(lines) > 8:
            raise SnapshotFileError('Native Snapshot file list exceeds its bound')
        observed = {}
        for line in lines:
            fields = line.split('\t')
            if len(fields) != 5:
                raise SnapshotFileError('Native Snapshot file list is malformed')
            name, size, digest, original, path_digest = fields
            if (re.fullmatch(re.escape(prefix) + r'-[A-Za-z0-9_-]{1,64}\.(png|jpg|gif)', name) is None
                    or name in observed or not size.isascii() or not size.isdigit()
                    or not 0 <= int(size) <= MAX_BYTES or re.fullmatch('[0-9a-f]{64}', digest) is None
                    or re.fullmatch('[0-9a-f]{64}',path_digest) is None
                    or not original_stat(original,int(size))):
                raise SnapshotFileError('Native Snapshot file observation is invalid')
            observed[name] = {'bytes': int(size), 'sha256': digest, 'originalStat': original, 'pathSha256':path_digest}
        return observed

    def _read(self, basename):
        AdbTransport._validate_debug_app_file(self.package, ROOT + '/' + basename)
        raw = self._execute(READ_SCRIPT, basename, str(MAX_BYTES + 1), timeout=90)
        if (not isinstance(raw, bytes) or not raw.startswith(BYTES_HEADER) or not raw.endswith(BYTES_FOOTER)
                or len(raw) > MAX_BYTES + 1 + len(BYTES_HEADER) + len(BYTES_FOOTER)):
            raise SnapshotFileError('Native Snapshot binary transfer did not complete')
        content = raw[len(BYTES_HEADER):-len(BYTES_FOOTER)]
        if len(content) > MAX_BYTES:
            raise SnapshotFileError('Native Snapshot binary transfer exceeds its bound')
        return content

    @staticmethod
    def _matches(metadata, content):
        return (metadata is not None and len(content) == metadata['bytes']
                and hashlib.sha256(content).hexdigest() == metadata['sha256'])

    def _publish(self, basename, content, digest):
        context = json.dumps(self.context | {'basename': basename}, sort_keys=True).encode()
        key = hashlib.sha256(context).hexdigest()[:24]
        filename = 'snapshot-' + key + '-' + digest + '.' + basename.rsplit('.', 1)[1]
        destination = self.artifacts / filename
        # Content-addressed immutable files never overwrite foreign or older
        # artifacts. Existing files must be private ordinary identical bytes.
        try:
            descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        except FileExistsError:
            metadata = destination.lstat()
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                    or metadata.st_size != len(content) or os.name != 'nt'
                    and (metadata.st_uid != os.geteuid() or metadata.st_mode & 0o077)):
                raise SnapshotFileError('Native Snapshot artifact collision') from None
            descriptor = os.open(destination,os.O_RDONLY | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_NONBLOCK',0))
            with os.fdopen(descriptor,'rb') as stream:
                signature=lambda v:(v.st_dev,v.st_ino,v.st_size,v.st_mode,v.st_uid,v.st_nlink,v.st_mtime_ns,v.st_ctime_ns)
                if (signature(os.fstat(stream.fileno()))!=signature(metadata)
                        or hashlib.sha256(stream.read(MAX_BYTES + 1)).hexdigest() != digest
                        or signature(os.fstat(stream.fileno()))!=signature(metadata)
                        or signature(destination.lstat())!=signature(metadata)):
                    raise SnapshotFileError('Native Snapshot artifact collision')
        else:
            try:
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException:
                destination.unlink(missing_ok=True)
                raise
        return filename

    def files(self, prefix, *, run=''):
        self.last_original = None
        before = self._list(prefix,run)
        copied = {}
        for basename, metadata in sorted(before.items()):
            # head imposes the byte ceiling inside the trusted OS file command,
            # before the existing ADB transport buffers the binary response.
            content = self._read(basename)
            if metadata['bytes'] > 0 and not self._matches(metadata, content):
                raise SnapshotFileError('Native Snapshot original bytes changed during transfer')
            copied[basename] = content
        after = self._list(prefix,run)
        # Animated capture publishes its still/GIF companions separately. New
        # entries, or an empty reservation completing, are legitimate progress;
        # already copied nonempty bytes must remain identical. Empty originals
        # remain visible to the pre-capture freshness check and decoder.
        for name, metadata in before.items():
            if metadata['bytes'] == 0 and not self._matches(after.get(name), copied[name]):
                # A reservation may complete while its empty body is read.
                # Retry this read once, never an input/capture, and verify the
                # actual new bytes against a second stable OS observation.
                current = after.get(name)
                if current is None:
                    raise SnapshotFileError('Native Snapshot reservation disappeared')
                copied[name] = self._read(name)
                after = self._list(prefix,run)
                if after.get(name) != current or not self._matches(current, copied[name]):
                    raise SnapshotFileError('Native Snapshot reservation did not settle')
        if (any(metadata['bytes'] > 0 and after.get(name) != metadata for name, metadata in before.items())
                or any(not self._matches(after.get(name), content) for name, content in copied.items())):
            raise SnapshotFileError('Native Snapshot files changed during observation')
        self._check()
        result = [{'basename': name, 'artifact': self._publish(name, content, after[name]['sha256'])}
                  for name, content in sorted(copied.items())]
        self._check()
        self.last_original=deepcopy({'prefix':prefix,'context':self.context,'files':[
            {'basename':row['basename'],'artifact':row['artifact'],**after[row['basename']]} for row in result]})
        return {'files': result}
