"""Historical context capacity, unchanged v1 and unresolved physical owners."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.browser_archive_context import BrowserArchiveContext,read_context
from adapters.script_journey.history import pack,MAX_PACKED,MAX_RAW


class BrowserArchiveContextTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.store=PrivateFeatureState(self.root/'context.json');self.run='a'*32

    def data(self):
        return {'originals':[hashlib.sha256(str(index).encode()).hexdigest() for index in range(2200)]}

    def test_large_exact_original_uses_existing_parts_without_raising_limits(self):
        data=self.data()
        with self.assertRaises(NativeUIError):pack([data])
        owner=BrowserArchiveContext(self.store,self.run,data)
        self.assertGreater(len(owner.chunks.identities),1)
        self.assertEqual(data,read_context(self.store,self.run));owner.verify()
        self.assertEqual(MAX_RAW,16*1024*1024);self.assertEqual(MAX_PACKED,48*1024)
        self.assertEqual('ready',owner.previous['phase'])
        for store in owner.stores():self.assertLessEqual(store.path.stat().st_size,65536)
        for index in range(len(owner.chunks.identities)):
            self.assertLessEqual(len(owner.chunks.store(index).read()['transcript']['data']),MAX_PACKED)

    def test_original_v1_bytes_read_without_rewrite_or_migration(self):
        data={'originals':[{'nonce':'b'*32,'capturedEpochMs':20000}]}
        value=dict(picoBrowserArchiveContextVersion=1,runId=self.run,payload=pack([data]))
        self.store.write(value,None);raw=self.store.path.read_bytes();info=self.store.path.stat()
        self.assertEqual(data,read_context(self.store,self.run))
        after=self.store.path.stat();self.assertEqual(raw,self.store.path.read_bytes())
        self.assertEqual((info.st_ino,info.st_mtime_ns,info.st_ctime_ns),(after.st_ino,after.st_mtime_ns,after.st_ctime_ns))
        with self.assertRaises(NativeUIError):BrowserArchiveContext(self.store,self.run,data)

    def test_lost_landed_child_preserves_reading_and_orphan_without_cold_adoption(self):
        write=PrivateFeatureState.write;landed=[]
        def lost(store,value,previous):
            write(store,value,previous)
            if '.frame-' in store.path.name:
                landed.append(store.path);raise NativeUIError('Original child response lost after durable write')
        with patch.object(PrivateFeatureState,'write',lost),self.assertRaises(NativeUIError):
            BrowserArchiveContext(self.store,self.run,self.data())
        self.assertEqual(1,len(landed));self.assertTrue(landed[0].exists())
        self.assertEqual('reading',self.store.read()['phase']);self.assertEqual([],self.store.read()['chunks'])
        before={path:path.read_bytes() for path in self.root.iterdir()}
        with self.assertRaises(NativeUIError):read_context(self.store,self.run)
        with self.assertRaises(NativeUIError):BrowserArchiveContext(self.store,self.run,self.data())
        self.assertEqual(before,{path:path.read_bytes() for path in self.root.iterdir()})

    def test_same_bytes_replacement_child_is_not_the_warm_original(self):
        owner=BrowserArchiveContext(self.store,self.run,self.data());path=owner.chunks.store(0).path
        original=path.read_bytes();inode=path.stat().st_ino;replacement=self.root/'replacement'
        replacement.write_bytes(original);replacement.chmod(0o600);replacement.replace(path)
        self.assertNotEqual(inode,path.stat().st_ino);self.assertEqual(original,path.read_bytes())
        with self.assertRaises(NativeUIError):owner.verify()
        with self.assertRaises(NativeUIError):owner.stores()
        self.assertEqual('ready',self.store.read()['phase'])
