"""Actual original-process PNG/input owner, with declared native producers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.navigation_initial_restored_image import NavigationInitialRestoredImage
from ios.adapters.pointer_state import IOSPointerState
from ios.self_tests import test_ios_navigation_initial_restored_state as sources
from ios.self_tests.emote_keys_fixture import KeyDomain
from ios.self_tests.test_ios_pointer_state import NativePointerBoundary


class NavigationInitialRestoredImageTests(unittest.TestCase):
    setUp=sources.NavigationInitialRestoredStateTests.setUp
    acquire=sources.NavigationInitialRestoredStateTests.acquire

    def inputs(self):
        h=self.h;sdk=h.sdk;pid=int(h.binding['processIdentity'])
        class Domain:
            @property
            def time(_):return sdk.gpu.clock
            @time.setter
            def time(_,value):sdk.gpu.clock=value
            def epoch(_):return sdk.gpu.epoch()
            def sleep(_,delay):sdk.gpu.sleep(delay)
        self.domain=Domain();self.keys=KeyDomain(None,self.domain,binding=h.binding)
        class Pointer(NativePointerBoundary):
            def send(p,query):
                super().send(query);p.packet['processId']=pid
        self.pointer=Pointer()
        def tick():sdk.gpu.clock+=.001;self.pointer.now=sdk.gpu.epoch();return self.pointer.now
        self.pointer.tick=tick;self.pointer.now=sdk.gpu.epoch()
        self.pointer_reader=IOSPointerState(self.pointer.send,self.pointer.original,sdk.gpu.epoch,lambda:sdk.okay,pid,
            monotonic=h.mono,sleep=sdk.gpu.sleep)

    def owner(self,call,request,*,historical=False):
        h=self.h
        return NavigationInitialRestoredImage(PrivateFeatureState(h.root/('ios-navigation-initial-restored-primary-'+request[4:]+'.json')),
            h.root,h.binding,h.run,'primary',request,h.flow.lock,lambda:h.sdk.okay,
            native=None if historical else h.native,sources=None if historical else self.sources,
            fixture=None if historical else h.fixture,frame_factory=None if historical else h.gpu.factory,
            historical=historical,epoch_ms=h.now,monotonic=h.mono,sleep=h.sdk.gpu.sleep,
            admission=h.flow.initial_owner(),directory=call['directory'],previous=self.prior_owner,fixture_url=h.fixture.fixture_url,
            input_readers=None if historical else dict(keys=self.keys.reader(),pointer=self.pointer_reader,geometry=self.keys.geometry()))

    def test_original_process_static_image_and_inputs_replay_after_sdk_disappearance(self):
        call=self.acquire();self.inputs();h=self.h;request='ios-'+uuid.uuid4().hex
        with h.flow.held():
            owner=self.owner(call,request);result,proof,raw=owner.acquire(h.now())
            self.assertEqual(h.binding,proof['binding']);self.assertTrue(proof['lifetimeEndRequired'])
            self.assertEqual('A',result['rendered']['location']);self.assertEqual(b'\x89PNG\r\n\x1a\n',raw[:8])
            self.assertEqual(int(h.binding['processIdentity']),owner.originals()['capture']['processId'])
            self.assertTrue(proof['placesRoots']['roots']);commands=deepcopy(h.gpu.commands)
            inputs=deepcopy(self.keys.commands);pointer=deepcopy(self.pointer.requests);h.sdk.okay=False
            frozen=self.owner(call,request,historical=True);self.assertEqual((result,proof,raw),frozen.archive())
            self.assertEqual(commands,h.gpu.commands);self.assertEqual(inputs,self.keys.commands);self.assertEqual(pointer,self.pointer.requests)
            with self.assertRaises(NativeUIError):owner.bound()

    def test_actual_unreleased_key_blocks_static_admission_and_retains_original_ownership(self):
        call=self.acquire();self.inputs();h=self.h
        self.keys.qt.finish(self.keys.qt.enter('key-press'))
        with h.flow.held():
            owner=self.owner(call,'ios-'+uuid.uuid4().hex)
            with self.assertRaises(NativeUIError):owner.acquire(h.now())
            self.assertEqual('reading',owner.state['phase']);self.assertIsNotNone(owner.store.read())
            self.assertIsNotNone(owner.input_owner().store.read());self.assertNotIn('retired',owner.state)

    def test_literal_version_one_originals_keep_bytes_clocks_and_grammar_under_the_new_reader(self):
        call=self.acquire();self.inputs();h=self.h;request='ios-'+uuid.uuid4().hex
        with h.flow.held():
            with patch.object(NavigationInitialRestoredImage,'WRITER_VERSION',1):
                old=self.owner(call,request);expected=old.acquire(h.now())
            originals={path:(path.stat().st_ino,path.read_bytes()) for path in h.root.iterdir() if request[4:] in path.name}
            self.assertTrue(originals);self.assertEqual(1,expected[1]['iosNavigationInitialRestoredStateVersion'])
            frozen=self.owner(call,request,historical=True)
            self.assertEqual(1,frozen.version);self.assertNotIn('missingOwner',frozen.KEYS);self.assertEqual(expected,frozen.archive())
            current=self.owner(call,'ios-'+uuid.uuid4().hex);new=current.acquire(h.now())
            self.assertEqual(2,current.version);self.assertEqual(2,new[1]['iosNavigationInitialRestoredStateVersion'])
            self.assertIsNone(current.originals()['missingOwner'])
            self.assertEqual(originals,{path:(path.stat().st_ino,path.read_bytes()) for path in originals})


if __name__=='__main__':unittest.main()
