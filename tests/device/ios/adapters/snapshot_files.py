"""Original native Snapshot bytes through the closed read-only E2E producer.

PID/nonce continuity is UI-component evidence, not an installed-code binding.
No AFC root, requested capture result or replacement image is accepted.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time
from urllib.request import Request, urlopen
import uuid

from adapters.normal_ui import NativeUIError
from ios.adapters.appium_adapter import AppiumAdapter, WebDriverRequestError
from ios.adapters.normal_input import _fresh, _integer, _uuid
from snapshot_file_contract import CHUNK_BYTES, MAX_FILE_BYTES, MAX_FILES, read_request


class SnapshotFiles:
    def __init__(self, client, session, target, observe_process, native_instance, artifacts, *,
                 monotonic=time.monotonic, sleep=time.sleep):
        if (not isinstance(session, str) or re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', session) is None
                or not callable(observe_process) or not _uuid(native_instance)
                or target.get('nativeUiObservation') != {'kind': 'uikit-documents', 'version': 1}
                or type(target['nativeUiObservation']['version']) is not int):
            raise NativeUIError('Original iOS Snapshot requires an explicit native UI component session')
        self.client, self.session, self.target = client, session, target
        self.observe_process, self.monotonic, self.sleep = observe_process, monotonic, sleep
        self.process, self.last_clock = None, None
        self._check()
        self.context = {'bundleId': target['appId'], 'session': session, 'processId': self.process['pid'],
                        'nativeInputInstance': native_instance, 'scope': 'NATIVE_UI_COMPONENT_ONLY'}
        self.artifacts = Path(artifacts)
        if not self.artifacts.is_absolute() or self.artifacts.resolve() != self.artifacts:
            raise NativeUIError('Original iOS Snapshot artifact root is invalid')
        self.artifacts.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._artifact_root()

    def _artifact_root(self):
        if self.artifacts.resolve() != self.artifacts:
            raise NativeUIError('Original iOS Snapshot artifact root became an alias')
        self._private(self.artifacts, directory=True)

    def _check(self):
        value = self.observe_process()
        if (not isinstance(value, dict) or set(value) != {'bundleId', 'pid', 'foreground'}
                or value['bundleId'] != self.target['appId'] or not _integer(value['pid'], 1)
                or value['foreground'] is not True or self.process is not None and self.process != value):
            raise NativeUIError('Original iOS Snapshot lost its foreground process')
        self.process = dict(value)

    def _now(self):
        value = self.monotonic()
        if (type(value) not in (int, float) or not math.isfinite(value)
                or self.last_clock is not None and value < self.last_clock):
            raise NativeUIError('Original iOS Snapshot clock is invalid')
        self.last_clock = value
        return value

    def _request(self, operation, prefix, **arguments):
        command = read_request({'schemaVersion': 1, 'commandId': 'ios-' + uuid.uuid4().hex,
            'action': 'snapshot-files', 'operation': operation, 'prefix': prefix, **arguments})
        self._check()
        origin = self.target['testBuild']['fixtureOrigin']
        AppiumAdapter.controlled_http_url(origin, 'original Snapshot fixture origin')
        request = Request(origin + '/e2e-client-command.json', data=json.dumps(command).encode(),
            headers={'Content-Type': 'application/json'}, method='POST')
        with urlopen(request, timeout=5) as response:
            raw = response.read(4097)
            if response.status != 200 or len(raw) > 4096 or json.loads(raw) != command:
                raise NativeUIError('Original iOS Snapshot fixture changed the read request')
        remote = (f"@{self.target['appId']}:documents/{self.target['testBuild']['resultsDirectory']}/"
                  'ios-snapshot-file-result.json')
        deadline = self._now() + 15
        for _attempt in range(151):
            self._check()
            try:
                encoded = self.client.execute(self.session, 'mobile: pullFile', {'remotePath': remote})
            except WebDriverRequestError as error:
                # A newly queued native producer may not have published its
                # first receipt. Only bounded read polling is retried; failure
                # never becomes an empty manifest or a successful capture.
                if error.status != 500:
                    raise
                encoded = None
            if encoded is not None:
                if not isinstance(encoded, str) or len(encoded) > 196608:
                    raise NativeUIError('Original iOS Snapshot receipt exceeds its transport bound')
                try:
                    raw = base64.b64decode(encoded, validate=True)
                    if len(raw) > 131072:
                        raise ValueError('receipt bound')
                    value = json.loads(raw)
                except (ValueError, UnicodeError):
                    raise NativeUIError('Original iOS Snapshot receipt is malformed') from None
                if isinstance(value, dict) and value.get('commandId') == command['commandId']:
                    fields = {'schemaVersion', 'commandId', 'operation', 'prefix', 'processId', 'sampleEpochMs', 'ok'}
                    fields.add('files' if operation == 'list' else 'file')
                    if (set(value) != fields or type(value['schemaVersion']) is not int or value['schemaVersion'] != 1
                            or value['operation'] != operation or value['prefix'] != prefix or value['ok'] is not True
                            or not _integer(value['processId'], 1) or value['processId'] != self.process['pid']
                            or not _fresh(value['sampleEpochMs'], time.time() * 1000)):
                        raise NativeUIError('Original iOS Snapshot read did not freshly succeed')
                    self._check()
                    return value['files' if operation == 'list' else 'file']
            if self._now() >= deadline:
                break
            self.sleep(0.1)
        raise NativeUIError('Original iOS Snapshot did not publish this read receipt')

    def _list(self, prefix):
        rows = self._request('list', prefix)
        if not isinstance(rows, list) or len(rows) > MAX_FILES:
            raise NativeUIError('Original iOS Snapshot file list exceeds its bound')
        result = {}
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {'name', 'size', 'revision', 'sha256'}
                    or not _integer(row['size']) or row['size'] > MAX_FILE_BYTES
                    or not isinstance(row['sha256'], str) or re.fullmatch(r'[0-9a-f]{64}', row['sha256']) is None):
                raise NativeUIError('Original iOS Snapshot file observation is invalid')
            read_request({'schemaVersion': 1, 'commandId': 'ios-' + 'a' * 32, 'action': 'snapshot-files',
                'operation': 'read', 'prefix': prefix, 'name': row['name'], 'revision': row['revision'], 'offset': 0})
            if row['name'] in result:
                raise NativeUIError('Original iOS Snapshot file observation is duplicated')
            result[row['name']] = row
        if sum(row['size'] for row in result.values()) > MAX_FILE_BYTES:
            raise NativeUIError('Original iOS Snapshot total exceeds its bound')
        return result

    def _read(self, prefix, row):
        result = bytearray()
        while len(result) < row['size']:
            offset = len(result)
            value = self._request('read', prefix, name=row['name'], revision=row['revision'], offset=offset)
            if (not isinstance(value, dict) or set(value) != {'name', 'revision', 'size', 'offset', 'eof', 'data'}
                    or value['name'] != row['name'] or value['revision'] != row['revision']
                    or not _integer(value['size']) or value['size'] != row['size']
                    or not _integer(value['offset']) or value['offset'] != offset or type(value['eof']) is not bool
                    or not isinstance(value['data'], str) or len(value['data']) > 4 * ((CHUNK_BYTES + 2) // 3)):
                raise NativeUIError('Original iOS Snapshot chunk is invalid')
            try:
                chunk = base64.b64decode(value['data'], validate=True)
            except ValueError:
                raise NativeUIError('Original iOS Snapshot chunk is malformed') from None
            if (len(chunk) != min(CHUNK_BYTES, row['size'] - offset)
                    or value['eof'] != (offset + len(chunk) == row['size'])):
                raise NativeUIError('Original iOS Snapshot chunk is incomplete')
            result.extend(chunk)
        if hashlib.sha256(result).hexdigest() != row['sha256']:
            raise NativeUIError('Original iOS Snapshot bytes changed during transport')
        return bytes(result)

    @staticmethod
    def _private(path, *, directory=False):
        metadata = path.lstat()
        if (not (stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode))
                or not directory and metadata.st_nlink != 1
                or os.name != 'nt' and (metadata.st_uid != os.geteuid() or metadata.st_mode & 0o077)):
            raise NativeUIError('Original iOS Snapshot artifact is not a private ordinary file')
        return metadata

    def _path(self, row):
        context = json.dumps(self.context | {'basename': row['name']}, sort_keys=True).encode()
        key = hashlib.sha256(context).hexdigest()[:24]
        return self.artifacts / ('snapshot-' + key + '-' + row['sha256'] + '.' + row['name'].rsplit('.', 1)[1])

    def _cached(self, row):
        self._artifact_root()
        path = self._path(row)
        try:
            before = self._private(path)
        except FileNotFoundError:
            return None
        if before.st_size != row['size']:
            raise NativeUIError('Original iOS Snapshot artifact content changed')
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(descriptor, 'rb') as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise NativeUIError('Original iOS Snapshot artifact was replaced')
            digest = hashlib.sha256()
            count = 0
            while chunk := stream.read(CHUNK_BYTES):
                count += len(chunk)
                if count > row['size']:
                    raise NativeUIError('Original iOS Snapshot artifact exceeds its bound')
                digest.update(chunk)
            after = os.fstat(stream.fileno())
        current = self._private(path)
        if (count != row['size'] or digest.hexdigest() != row['sha256']
                or (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
                   != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                or (current.st_dev, current.st_ino) != (after.st_dev, after.st_ino)):
            raise NativeUIError('Original iOS Snapshot artifact content changed')
        return path

    def files(self, prefix):
        self._artifact_root()
        before = self._list(prefix)
        pending = {}
        for name, row in before.items():
            if row['size'] == 0:
                continue
            path = self._cached(row)
            if path is None:
                pending[name] = self._read(prefix, row)
        after = self._list(prefix)
        result = []
        for name, row in before.items():
            if row['size'] == 0:
                continue
            if after.get(name) != row:
                raise NativeUIError('Original iOS Snapshot changed before artifact publication')
            path = self._cached(row)
            if path is None:
                self._artifact_root()
                path = self._path(row)
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(pending[name]); stream.flush(); os.fsync(stream.fileno())
                path = self._cached(row)
            result.append({'basename': name, 'artifact': str(path)})
        self._check()
        return {'files': result}
