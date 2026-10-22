"""Actual host file bytes and synthetic native descriptors/clocks only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_bookmarks as bookmarks, avatar_state
from ios.self_tests.test_ios_avatar_state import packet


class BookmarkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name)/'avatarbookmarks.json'
        self.original = dict(existing=dict(avatarUrl='https://original.invalid/avatar.fst', avatarScale=1, avatarEntites=[], version=3))
    def file(self, value=None, raw=None):
        self.path.write_bytes(json.dumps(value).encode() if raw is None else raw)
        data = self.path.read_bytes(); info = self.path.stat()
        return dict(source=bookmarks.SOURCE, status='ready', reason='', bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(), contentBase64=base64.b64encode(data).decode(),
            identity=dict(device=str(info.st_dev), inode=str(info.st_ino)))
    def loaded(self, value): return dict(source='AvatarBookmarks.getBookmarks', entries=deepcopy(value), loadError=False)
    def test_exact_actual_bytes_and_loaded_map_preserve_unowned_bookmarks(self):
        actual = deepcopy(self.original); owned = dict(avatarUrl='https://fixture.invalid/avatar-a.fst', avatarScale=1, avatarEntites=[], version=3)
        actual['owned'] = owned; source = self.file(actual)
        self.assertEqual(self.path.read_bytes(), bookmarks.original_bytes(source))
        self.assertTrue(bookmarks.owned(source, self.loaded(actual), 'owned', self.original, saved=owned))
        self.assertFalse(bookmarks.owned(self.file(self.original), self.loaded(self.original), 'owned', self.original))
    def test_loaded_bookmark_without_actual_saved_bytes_or_stale_partial_save_cannot_pass(self):
        actual = deepcopy(self.original); actual['owned'] = dict(avatarUrl='A', avatarScale=1, avatarEntites=[])
        for saved in (self.original, actual | dict(owned=dict(avatarUrl='A', avatarScale=1.5, avatarEntites=[]))):
            with self.subTest(saved=saved), self.assertRaises(NativeUIError):
                bookmarks.owned(self.file(saved), self.loaded(actual), 'owned', self.original)
    def test_absent_unavailable_invalid_or_duplicate_original_file_is_not_empty_bookmarks(self):
        for status in ('absent', 'unavailable'):
            source = dict(source=bookmarks.SOURCE, status=status, reason='' if status == 'absent' else 'changed-file',
                bytes=None, sha256=None, contentBase64=None, identity=None)
            self.assertIsNone(bookmarks.entries(source)['entries'])
            with self.assertRaises(NativeUIError): bookmarks.persisted(source, self.loaded({}))
        for raw in (b'{"owned":{},"owned":{}}', b'[]', b'{', b'\xff'):
            source = self.file(raw=raw); self.assertEqual('invalid-json', bookmarks.entries(source)['status'])
            with self.assertRaises(NativeUIError): bookmarks.persisted(source, self.loaded({}))
    def test_changed_unowned_row_and_unreadable_loaded_service_refuse_cleanup(self):
        changed = deepcopy(self.original); changed['existing']['avatarScale'] = 1.5
        with self.assertRaises(NativeUIError): bookmarks.owned(self.file(changed), self.loaded(changed), 'owned', self.original)
        loaded = self.loaded(self.original); loaded['loadError'] = True
        with self.assertRaises(NativeUIError): bookmarks.persisted(self.file(self.original), loaded)
    def test_false_size_hash_base64_identity_and_wrong_path_provenance_are_rejected(self):
        source = self.file(self.original)
        for fault in ('size', 'hash', 'base64', 'identity', 'source'):
            altered = deepcopy(source)
            if fault == 'size': altered['bytes'] = True
            elif fault == 'hash': altered['sha256'] = '0'*64
            elif fault == 'base64': altered['contentBase64'] += '\n'
            elif fault == 'identity': altered['identity']['inode'] = '0'
            else: altered['source'] = 'app-local-data/avatarbookmarks.json'
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): bookmarks.original_bytes(altered)
    def test_version2_retains_original_file_and_cannot_downgrade_after_acceptance(self):
        value = packet(); value['iosAvatarStateVersion'] = 2; value['source']['bookmarkFile'] = self.file(self.original)
        value['source']['bookmarks'] = self.loaded(self.original)
        self.assertEqual(self.original, bookmarks.persisted(avatar_state.original(value)['source']['bookmarkFile'], value['source']['bookmarks']))
        old = packet(); old['sequence'] = 2; old['requestId'] = 'ios-'+'e'*32
        old['clockBefore'] = dict(epochMs=1700000000300, monotonicMs=300)
        old['clockAfter'] = dict(epochMs=1700000000400, monotonicMs=400)
        query = dict(schemaVersion=1, commandId=old['requestId'], action=avatar_state.ACTION, runId=old['runId'])
        with self.assertRaises(NativeUIError): avatar_state.validate(old, query, 42, previous=value)


if __name__ == '__main__': unittest.main()
