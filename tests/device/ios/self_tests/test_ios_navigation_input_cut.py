"""Actual source codecs and immutable files; Qt/UIKit producers are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.navigation_input_cut import NavigationInputCut
from ios.self_tests.emote_keys_fixture import KeyDomain
from ios.self_tests.test_ios_pointer_state import NativePointerBoundary,EPOCH
from ios.self_tests.test_ios_world_web_keys import LegacyQtKeys
from self_tests.test_completed_frame_lease import BINDING

RUN='a'*32


class NavigationInputCutTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.request='ios-'+uuid.uuid4().hex
        self.d=SimpleNamespace(time=10.)
        self.d.epoch=lambda:EPOCH+round(self.d.time*1000)
        self.d.sleep=lambda delay:setattr(self.d,'time',self.d.time+delay)
        self.keys=KeyDomain(None,self.d,binding=BINDING)
        self.pointer=NativePointerBoundary()
        def tick():self.d.time+=.001;self.pointer.now=self.d.epoch();return self.pointer.now
        self.pointer.tick=tick;self.pointer.now=self.d.epoch();self.okay=True
        self.store=PrivateFeatureState(self.root/('ios-navigation-input-primary-'+self.request[4:]+'.json'))

    def owner(self,*,historical=False):
        reader=self.pointer.reader();reader.monotonic=lambda:self.d.time;reader.sleep=self.d.sleep
        return NavigationInputCut(self.store,self.root,BINDING,RUN,'primary',self.request,self.lock,lambda:self.okay,
            readers=None if historical else dict(keys=self.keys.reader(),pointer=reader,geometry=self.keys.geometry()),
            historical=historical,monotonic=lambda:self.d.time)

    def test_large_original_key_packets_and_real_pointer_geometry_replay_without_sdk(self):
        for _ in range(240):
            self.keys.qt.finish(self.keys.qt.enter('key-press'));self.keys.qt.finish(self.keys.qt.enter('key-release'))
        self.pointer.touch('touch-begin');self.pointer.touch('touch-end')
        with self.lock.held():
            owner=self.owner();actual=owner.acquire();self.assertGreater(len(json.dumps(actual['keys'])),400000)
            self.assertLess(self.store.path.stat().st_size,48000);self.assertEqual(1,len(actual['pointer']['source']['ends']))
            commands=deepcopy(self.keys.commands);pointers=deepcopy(self.pointer.requests);self.okay=False
            archived=self.owner(historical=True);self.assertEqual(actual,archived.archive())
            self.assertEqual(commands,self.keys.commands);self.assertEqual(pointers,self.pointer.requests)
            ref=archived.state['accepted']['keys'];path=archived.files.path(ref)
            original=path.read_bytes();path.write_bytes(original.replace(b'key-press',b'key-xxxxx',1))
            with self.assertRaises((NativeUIError,ValueError)):archived.archive()

    def test_unsafe_matching_legacy_is_never_copied_to_a_host_original_or_reissued(self):
        # A genuine old producer emits its old grammar from birth.
        self.keys.qt=LegacyQtKeys()
        with self.lock.held():
            owner=self.owner()
            with self.assertRaises(NativeUIError):owner.acquire()
            self.assertEqual([],list(self.root.glob('navigation-input-*-frame-*')))
            original=deepcopy(self.store.read());commands=deepcopy(self.keys.commands);again=self.owner()
            with self.assertRaises(NativeUIError):again.acquire()
            self.assertEqual(commands,self.keys.commands);self.assertEqual(original,self.store.read())
            self.assertIsNotNone(again.state['queries']['keys']);self.assertEqual({},again.state['accepted'])

    def test_lost_final_result_recovers_complete_originals_without_any_source_query(self):
        with self.lock.held():
            owner=self.owner();write=owner.store.write
            def lose(value,previous):
                from adapters.script_feature.history import unpack
                if unpack(value['payload'])[0]['phase']=='observed':raise OSError('Lost final input-cut return')
                write(value,previous)
            owner.store.write=lose
            with self.assertRaises(OSError):owner.acquire()
            owner.store.write=write
            commands=deepcopy(self.keys.commands);pointers=deepcopy(self.pointer.requests)
            again=self.owner();again.recover();self.assertEqual(commands,self.keys.commands);self.assertEqual(pointers,self.pointer.requests)
            self.assertEqual(2,again.archive()['keys']['iosWorldWebKeysVersion'])

    def test_partial_geometry_query_keeps_originals_and_cannot_restart_the_cut(self):
        self.keys.fail_geometry=True
        with self.lock.held():
            owner=self.owner()
            with self.assertRaises(NativeUIError):owner.acquire()
            original=deepcopy(self.store.read());commands=deepcopy(self.keys.commands);again=self.owner()
            self.assertEqual({'keys','pointer'},set(again.state['accepted']))
            with self.assertRaises(NativeUIError):again.recover()
            with self.assertRaises(NativeUIError):again.acquire()
            self.assertEqual(original,self.store.read());self.assertEqual(commands,self.keys.commands)


if __name__=='__main__':unittest.main()
