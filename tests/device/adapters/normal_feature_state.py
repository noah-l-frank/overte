"""Private, process-bound ownership for normal feature input adapters.

This file records input/cleanup intent, never observed feature success.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from adapters.original_file_reads import record as record_original_read,check_writable
from pathlib import Path
import re
import stat
import tempfile

from adapters.normal_ui import NativeUIError

CONTEXT = {'sourceRevision', 'artifactSha256', 'processIdentity', 'sessionId',
           'generation', 'targetFingerprint'}
COMPONENT_CONTEXT = {'scope', 'processIdentity', 'sessionId', 'generation', 'targetFingerprint'}


def need(value):
    if not value:
        raise NativeUIError('Normal feature ownership or observation is invalid')


def context(value, *, component_only=False):
    need(type(component_only) is bool and type(value) is dict
         and set(value) == (COMPONENT_CONTEXT if component_only else CONTEXT))
    if component_only:
        need(value['scope'] == 'NATIVE_UI_COMPONENT_ONLY')
    patterns = (('targetFingerprint', r'[0-9a-f]{64}'),
                         ('sessionId', r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}'),
                         ('processIdentity', r'[!-~]{1,160}'))
    if not component_only:
        patterns += (('sourceRevision', r'[0-9a-f]{40}'), ('artifactSha256', r'[0-9a-f]{64}'))
    for key, pattern in patterns:
        need(type(value[key]) is str and re.fullmatch(pattern, value[key]) is not None)
    need(type(value['generation']) is int and value['generation'] >= 0)
    return value


class PrivateFeatureState:
    def __init__(self, path):
        self.path = Path(path)

    def _parent(self):
        need(self.path.is_absolute() and self.path.parent.resolve(strict=True) == self.path.parent)
        info = self.path.parent.lstat()
        need(stat.S_ISDIR(info.st_mode) and (os.name == 'nt' or
             info.st_uid == os.geteuid() and not info.st_mode & 0o077))

    def read(self):
        self._parent()
        try:
            before = self.path.lstat()
        except FileNotFoundError:
            return None
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1)
        try:
            descriptor = os.open(self.path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                                 | getattr(os, 'O_NONBLOCK', 0))
        except OSError:
            raise NativeUIError('Normal feature ownership file is unavailable') from None
        try:
            with os.fdopen(descriptor, 'r', encoding='utf-8') as stream:
                info = os.fstat(stream.fileno())
                current = self.path.lstat()
                need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 65536
                     and stat.S_ISREG(current.st_mode)
                     and (info.st_dev, info.st_ino) == (before.st_dev, before.st_ino)
                     == (current.st_dev, current.st_ino)
                     and (os.name == 'nt' or info.st_uid == os.geteuid()
                          and stat.S_IMODE(info.st_mode) == 0o600))
                def pairs(items):
                    result = {}
                    for key, value in items:
                        need(key not in result)
                        result[key] = value
                    return result
                value = json.loads(stream.read(65537), object_pairs_hook=pairs)
                need(type(value) is dict)
                record_original_read(self.path)
                return value
        except (ValueError, UnicodeError, OSError):
            raise NativeUIError('Normal feature ownership file is invalid') from None

    def write(self, value, previous):
        check_writable()
        self._parent()
        need(self.read() == previous)
        raw = json.dumps(value, allow_nan=False, sort_keys=True, separators=(',', ':'))
        need(len(raw.encode()) <= 65536)
        descriptor, temporary = tempfile.mkstemp(dir=self.path.parent, prefix='feature-input.')
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                stream.write(raw + '\n'); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def discard(self, previous):
        check_writable()
        need(self.read() == previous)
        self.path.unlink(missing_ok=True)
