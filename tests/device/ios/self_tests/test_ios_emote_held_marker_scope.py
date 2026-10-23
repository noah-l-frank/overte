"""Real v2 private once-intents; physical inputs and native sources modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.emote_marker_scope import IOSEmoteMarkerScope
from ios.adapters.emote_held_marker_scope import IOSEmoteHeldMarkerScope
from ios.adapters.emote_marker_files import OwnedEmoteMarkerFiles
from ios.adapters.emote_originals import IOSEmoteOriginals
from ios.self_tests import test_ios_emote_marker_scope as fixtures


class EmoteHeldMarkerScopeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.MarkerScopeTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        # Initialize the explicit new consumer before its first original/input.
        # No existing version-one carrier is relabeled or migrated.
        self.skeleton=self.fixture.owner().__dict__.copy()

    def owner(self):
        scope=object.__new__(IOSEmoteHeldMarkerScope);scope.__dict__.update(self.skeleton)
        scope.files=OwnedEmoteMarkerFiles(None,PrivateFeatureState(scope.root/'ios-emote-primary-marker-files.json'),scope.binding)
        scope.originals=IOSEmoteOriginals(scope.root,scope.binding,scope.run,scope.role,scope.guard,scope.storage_intent,kind='inputs')
        scope.state=deepcopy(self.skeleton['state']);scope.frames=[];scope.previous=scope.store.read()
        if scope.previous is not None:scope.state=scope.decode(scope.previous)
        return scope

    def test_new_literal_scope_writes_two_and_preserves_actual_once_delivery_across_reconstruction(self):
        calls=[];scope=self.owner();scope.once('open-marker-manager',lambda:calls.append('input'))
        before=(scope.store.path.stat().st_ino,scope.store.path.read_bytes())
        self.assertEqual(2,scope.previous['iosEmoteMarkerScopeVersion'])
        self.owner().once('open-marker-manager',lambda:calls.append('replayed'));self.assertEqual(['input'],calls)
        self.assertEqual(before,(scope.store.path.stat().st_ino,scope.store.path.read_bytes()))
        # Literal version one retains its original semantics and rejects two.
        with self.assertRaises(NativeUIError):self.fixture.owner()
        with self.assertRaises(NativeUIError):IOSEmoteMarkerScope.archive(scope.previous,root=scope.root,binding=scope.binding,
            run=scope.run,role=scope.role,lock=scope.lock)
        historical=IOSEmoteHeldMarkerScope.archive(scope.previous,root=scope.root,binding=scope.binding,
            run=scope.run,role=scope.role,lock=scope.lock)
        self.assertEqual(scope.state,historical.state)

    def test_unknown_input_keeps_issued_responsibility_and_can_never_resend(self):
        calls=[]
        def lost():calls.append('delivered');raise OSError('Actual normal delivery return lost')
        with self.assertRaises(OSError):self.owner().once('load-marker-script',lost)
        scope=self.owner();self.assertEqual('issued',scope.state['operations'][0]['phase'])
        with self.assertRaises(NativeUIError):scope.once('load-marker-script',lambda:calls.append('replayed'))
        self.assertEqual(['delivered'],calls)

    def test_new_reader_cannot_reinterpret_literal_version_one(self):
        self.fixture.owner().once('open-marker-manager',lambda:None)
        before=self.fixture.owner().store.path.read_bytes()
        with self.assertRaises(NativeUIError):self.owner()
        self.assertEqual(before,self.fixture.owner().store.path.read_bytes())


if __name__=='__main__':unittest.main()
