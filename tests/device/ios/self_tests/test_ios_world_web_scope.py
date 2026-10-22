"""World-only native/SDK models run actual staged Script and ordinary inputs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_scope import IOSWorldWebScope
from ios.adapters.world_web_files import OwnedWorldWebFiles
from ios.adapters.world_web_originals import IOSWorldWebOriginals
from ios.adapters.world_web_marker_recovery import IOSWorldWebMarkerRecovery
from ios.self_tests import test_ios_emote_marker_scope as scaffolding
from ios.self_tests.world_web_scope_fixture import WorldWebDomain


class WorldWebScopeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=scaffolding.MarkerScopeTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.scope=self.owner();self.domain=WorldWebDomain(self.scope)

    def owner(self):
        s=self.fixture.owner();s.__class__=IOSWorldWebScope
        s.store=PrivateFeatureState(s.root/'ios-worldweb-primary-marker.json')
        s.files=OwnedWorldWebFiles(None,PrivateFeatureState(s.root/'ios-worldweb-primary-marker-files.json'),s.binding)
        s.originals=IOSWorldWebOriginals(s.root,s.binding,s.run,s.role,s.guard,s.storage_intent,kind='inputs')
        s.previous=s.store.read();s.state['phase']='new'
        if s.previous is not None:s.state=s.decode(s.previous)
        return s

    def test_actual_world_only_script_camera_preservation_full_quiet_and_repeat_without_native_input(self):
        original=deepcopy(self.domain.world_template['source']['view']);owned=self.scope.prepare()
        self.assertTrue(owned['marker']['sourceUrl'].endswith('/reference.html'))
        self.assertEqual(original,self.domain.world_template['source']['view'])
        self.assertNotIn('select-marker-view',[r['label'] for r in self.scope.state['operations']])
        self.assertEqual([0,1.6,5.5],owned['marker']['position'])
        self.domain.paint();self.scope.admit_rendered();value=self.scope.snapshot()
        retained=IOSWorldWebScope.archive(value,root=self.scope.root,binding=self.scope.binding,run=self.scope.run,
            role=self.scope.role,lock=self.scope.lock,require_ready=True)
        self.assertEqual(owned['marker']['id'],retained.state['admission']['marker']['id'])
        self.assertEqual({'performed':True},self.scope.cleanup());self.assertFalse(self.domain.files.root.exists())
        self.assertFalse(any(row.startswith('view.') for row in self.domain.io.actions))
        first=self.scope.frames[self.scope.state['quiet'][0]-1];last=self.scope.frames[-1]
        self.assertGreaterEqual(last['clockJoin']['hostBeforeMonotonic']-first['clockJoin']['hostAfterMonotonic'],3)
        actions=list(self.domain.io.actions);self.scope.cleanup();self.assertEqual(actions,self.domain.io.actions)
        self.assertEqual(self.scope.frames,self.owner().frames)

    def test_lost_real_stop_is_owned_reconstruction_observes_terminal_without_replay(self):
        self.scope.prepare();self.domain.paint();self.scope.admit_rendered();activate=self.domain.io.activate
        def lost(identifier,**kwargs):
            activate(identifier,**kwargs)
            if identifier=='scripts.stop.0':raise NativeUIError('modeled lost normal Stop response')
        with patch.object(self.domain.io,'activate',side_effect=lost),self.assertRaises(NativeUIError):self.scope.cleanup()
        rebuilt=self.owner();self.domain.attach(rebuilt);rebuilt.cleanup()
        self.assertEqual(1,self.domain.io.actions.count('scripts.stop.0'))

    def test_interrupted_original_preserves_web_namespace_bytes_and_new_read_identity(self):
        self.domain.web_failure=True
        with self.assertRaises(OSError):self.scope.capture('interrupted-web-source')
        partial=deepcopy(self.scope.state['pending']['partial']['world']);self.domain.web_failure=False
        current=self.scope.capture('fresh-web-source');recovery=IOSWorldWebMarkerRecovery(self.scope)
        self.assertEqual(1,len(recovery.state['records']));record=recovery.record(recovery.state['records'][0])
        self.assertEqual(1,record['iosWorldWebMarkerAbandonedReadVersion'])
        self.assertEqual(partial,recovery.prior(record['priorOwner'])['pending']['partial']['world'])
        self.assertNotEqual(partial['requestId'],current['world']['requestId'])


if __name__=='__main__':unittest.main()
