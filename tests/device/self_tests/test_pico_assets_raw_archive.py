"""Real binary originals and original OFDs; no native/device source authority."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from adapters.chat_journey import source_bundles
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.normal_feature_state import PrivateFeatureState
from adapters.observer_return import state as file_state
from adapters.pico4.assets_raw_archive import AssetsRawArchive, MAX_LITERAL, quoted_bytes, compact
from adapters.pico4.assets_prefix_originals import AssetsPrefixOriginals
from adapters.script_journey.history import same
from adapters.script_journey.lock import ScriptSourceLock


class RawFixtureOwner:
    """Only the actual enclosing journal/CAS/bill seam is supplied here."""
    def __init__(self, root,*,version=2):
        self.store = PrivateFeatureState(root/'raw-fixture.json')
        self.scope = dict(assetsPrefixVersion=version, runId='a'*32)
        self.lock = ScriptSourceLock(root/'raw-fixture.lock')
        self.disk = self.stamp = None
        self.state = dict(**self.scope, phase='reading', chunks=[], bundles=[], pendingRawRead=None,rawReads=[])
        self.history = ChatSourceChunks(self.store, self.scope)
        self.raws = None
        with self.lock.held():
            self.save()
            self.raws = AssetsRawArchive(self)

    def identity(self):
        if self.disk is None:
            assert self.store.read() is None
        else:
            value, _raw, stamp = file_state(self.store)
            assert same(value, self.disk) and stamp == self.stamp
        self.history.verify()

    def save(self):
        self.identity()
        self.store.write(self.state, self.disk)
        value, _raw, self.stamp = file_state(self.store)
        self.disk = deepcopy(value)

    def bill(self):
        extra = dict(parts=0, bytes=0) if self.raws is None else self.raws.bill()
        paths = [self.store.path, *[self.history._path(index) for index in range(len(self.history.identities))]]
        return dict(frames=len(self.history.identities)+extra['parts']+len(self.state['rawReads']),
            decodedBytes=source_bundles.logical_bytes(self.state['bundles'])+extra['bytes']+len(json.dumps(self.state['rawReads']).encode()),
            storedBytes=sum(path.stat().st_size for path in paths)+extra['bytes'])

    def original(self, index):
        return source_bundles.original(self.history, self.disk['chunks'], self.disk['bundles'], index)[0]

    def raw_record(self,index):
        return deepcopy(self.disk['rawReads'][index])

    def acquire(self, getter, command=None):
        command = dict(commandId=uuid.uuid4().hex) if command is None else command
        self.raws.reserve('mappings', command)
        text = getter()
        reference = self.raws.retain(text)
        index = len(self.state['rawReads'])
        self.state['rawReads'].append(dict(role='mappings',rawOriginal=compact(reference)))
        self.raws.clear_intent()
        self.save()
        self.raws.delivered(index)
        return reference, command


class AssetsRawArchiveTests(unittest.TestCase):
    def setUp(self):
        destination = os.environ.get('OVERTE_ASSETS_RAW_EVIDENCE')
        if destination is None:
            temporary = tempfile.TemporaryDirectory(prefix='pico-assets-raw-')
            self.addCleanup(temporary.cleanup)
            root = Path(temporary.name)
        else:
            root = Path(tempfile.mkdtemp(prefix=self._testMethodName+'-', dir=destination))
        self.owner = RawFixtureOwner(root)
        self.addCleanup(self.owner.raws.close_host)

    def test_exact_quoted_length_matches_ascii_codec_without_large_wrapped_allocation(self):
        texts = ['', 'plain', '"\\', ''.join(chr(code) for code in range(256)),
            '\ud800\udfff', '\U0001f41a', 'a\x7f\t\n', 'é"\\\n', 'z'*262144]
        texts.extend(chr(code) for code in range(128))
        texts.extend(chr(left)+chr(right) for left in range(128) for right in range(128))
        for text in texts:
            actual = quoted_bytes(text)
            self.assertIs(type(actual), int)
            self.assertEqual(len(json.dumps(text, ensure_ascii=True).encode('ascii')), actual)
        calls = []
        class Foreign(str):
            def __len__(self):
                calls.append('len')
                raise AssertionError('foreign length callback')
            def __iter__(self):
                calls.append('iter')
                raise AssertionError('foreign iterator callback')
            def isascii(self):
                calls.append('isascii')
                raise AssertionError('foreign ASCII callback')
            def isprintable(self):
                calls.append('isprintable')
                raise AssertionError('foreign print callback')
            def count(self, *args):
                calls.append('count')
                raise AssertionError('foreign count callback')
        class Equal(type):
            def __eq__(self, other):
                calls.append('type-equality')
                return True
        class Alias(str, metaclass=Equal):
            pass
        for value in (None, True, 1, 1.0, b'plain', [], {}, Foreign('plain'), Alias('plain')):
            from adapters.normal_ui import NativeUIError
            with self.assertRaises(NativeUIError):
                quoted_bytes(value)
        self.assertEqual([], calls)

    def test_actual_four_mib_control_literal_survives_before_decoder_refusal(self):
        owner = self.owner
        text = '\0'*MAX_LITERAL
        calls = []
        with owner.lock.held():
            reference, command = owner.acquire(lambda:(calls.append(True), text)[1])
            self.assertEqual(64, len(reference['parts']))
            self.assertTrue(all(row['bytes'] <= 65536 for row in reference['parts']))
            with self.assertRaises(Exception):
                owner.raws.parser_capacity(text, command)
            self.assertEqual(text.encode(), owner.raws.literal(reference))
            self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), reference['sha256'])
            self.assertEqual(1, len(calls))
            self.assertIsNone(owner.disk['pendingRawRead'])
            self.assertLessEqual(owner.bill()['decodedBytes'], 16*1024*1024)

    def test_actual_existing_literals_exhaust_next_reservation_before_getter(self):
        owner = self.owner
        calls = []
        with owner.lock.held():
            for character in ('a', 'b', 'c'):
                text = character*MAX_LITERAL
                owner.acquire(lambda text=text:(calls.append(True), text)[1])
            before = list(calls)
            with self.assertRaises(Exception):
                owner.acquire(lambda:(calls.append(True), 'never acquired')[1])
            self.assertEqual(before, calls)
            self.assertEqual(3*MAX_LITERAL, owner.raws.bill()['bytes'])
            self.assertEqual(192, owner.raws.bill()['parts'])

    def test_same_inode_recycled_directory_description_refuses_before_getter(self):
        owner = self.owner
        foreign = None
        with owner.lock.held():
            original = owner.raws.directory
            descriptor = original.fd
            os.close(descriptor)
            foreign = os.open(owner.store.path.parent, os.O_RDONLY|os.O_DIRECTORY)
            if foreign != descriptor:
                os.dup2(foreign, descriptor)
                os.close(foreign)
                foreign = descriptor
            self.assertEqual(original.node, (os.fstat(foreign).st_dev, os.fstat(foreign).st_ino))
            calls = []
            with self.assertRaises(Exception):
                owner.acquire(lambda:(calls.append(True), 'never acquired')[1])
            self.assertFalse(calls)
            self.assertFalse(owner.raws.close_host())
            self.assertEqual(original.node[1], os.fstat(foreign).st_ino)
        # The explicit test owner closes its own foreign handle, never module cleanup.
        os.close(foreign)

    def test_recycled_same_file_writer_description_is_never_force_closed(self):
        owner=self.owner;write=os.write;foreign=[]
        def recycled(descriptor,data):
            path=os.readlink('/proc/self/fd/'+str(descriptor));before=os.fstat(descriptor)
            os.close(descriptor);replacement=os.open(path,os.O_WRONLY|os.O_NOFOLLOW)
            if replacement!=descriptor:
                os.dup2(replacement,descriptor);os.close(replacement)
            foreign.append(descriptor)
            self.assertEqual(before.st_ino,os.fstat(descriptor).st_ino)
            return write(descriptor,data)
        try:
            with owner.lock.held():
                owner.raws.reserve('mappings',dict(commandId='a'*32))
                with patch('os.write',side_effect=recycled),self.assertRaises(Exception):
                    owner.raws.retain('actual acquired source bytes')
                self.assertTrue(owner.raws.uncertain_writers)
                self.assertFalse(owner.raws.close_host())
                self.assertGreater(os.fstat(foreign[0]).st_size,0)
        finally:
            for descriptor in foreign:os.close(descriptor)

    def test_identical_replacement_binary_is_not_adopted(self):
        owner=self.owner
        with owner.lock.held():
            reference,_command=owner.acquire(lambda:'original literal')
            path=owner.store.path.parent/reference['parts'][0]['name']
            raw=path.read_bytes();path.rename(path.with_name(path.name+'.retained-original'))
            path.write_bytes(raw);path.chmod(0o400)
            self.assertEqual(raw,path.read_bytes())
            with self.assertRaises(Exception):owner.raws.literal(reference)
            getters=[]
            with self.assertRaises(Exception):owner.acquire(lambda:(getters.append(True),'never acquired')[1])
            self.assertFalse(getters)
