"""Avatar ordinary marker Node script plus genuine host weak objects/private files."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import gc
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_marker_entities import IOSAvatarMarkerEntities
from ios.adapters.emote_marker_entities import IOSEmoteMarkerEntities
from ios.self_tests import test_ios_avatar_marker_scope as marker_fixture
from ios.self_tests.marker_entities_fixture import EntityDomain


class AvatarEntityDomain(EntityDomain):
    def owner(self):
        s=self.scope;return IOSAvatarMarkerEntities(PrivateFeatureState(s.root/('ios-avatar-'+s.role+'-marker-entities.json')),
            s.root,s.binding,s.run,s.role,s.lock,lambda:True,native=s.native,entities=self.reader,
            epoch_ms=s.epoch_ms,monotonic=s.monotonic)


class AvatarMarkerEntityTests(unittest.TestCase):
    def setUp(self):
        f=marker_fixture.AvatarMarkerScopeTests();f.setUp();self.addCleanup(f.doCleanups)
        self.scope,self.domain=f.scope,f.domain;self.entities=AvatarEntityDomain(self,self.scope,self.domain)
        self.owner=self.entities.owner();self.owner.capture()
    def test_actual_avatar_code_api_return_tree_birth_and_real_weak_death_are_separate_from_scope_map_absence(self):
        self.scope.prepare();self.domain.paint();self.scope.admit_rendered();identity=self.scope.state['admission']['marker']['id']
        held=self.entities.native.items[identity];self.scope.cleanup();self.owner.capture()
        with self.assertRaises(NativeUIError):self.owner.closed(self.scope)
        del held;gc.collect();self.owner.capture();result=self.owner.closed(self.scope)
        self.assertEqual('weak-expired',result['kind']);self.assertEqual(identity,result['ownership']['returned']['entityId'])
        self.assertTrue(result['lifetime']['destroyed'])
        snapshot=self.owner.store.read();before=len(self.entities.native.commands)
        archived=IOSAvatarMarkerEntities.archive(snapshot,store=self.owner.store,root=self.scope.root,binding=self.scope.binding,
            run=self.scope.run,role=self.scope.role,lock=self.scope.lock)
        self.assertEqual(result,archived.closed(self.scope));self.assertEqual(before,len(self.entities.native.commands))
        with self.assertRaises(NativeUIError):IOSEmoteMarkerEntities.archive(snapshot,store=self.owner.store,root=self.scope.root,
            binding=self.scope.binding,run=self.scope.run,role=self.scope.role,lock=self.scope.lock)
    def test_newly_observed_marker_UUID_cannot_replace_foreign_original_return_and_live_reuse(self):
        self.scope.prepare();identity=self.scope.state['admission']['marker']['id'];self.scope.cleanup();self.owner.capture();self.owner.closed(self.scope)
        self.entities.native.add(id_=identity);self.owner.capture()
        with self.assertRaises(NativeUIError):self.owner.closed(self.scope)
    def test_already_ended_avatar_script_still_owns_actual_return_birth_and_expiry(self):
        self.scope.prepare();identity=self.scope.state['admission']['marker']['id'];self.domain.stop();self.scope.cleanup();self.owner.capture()
        result=self.owner.closed(self.scope);self.assertEqual('finished-execution',self.scope.state['cleanupMode'])
        self.assertEqual(identity,result['ownership']['returned']['entityId']);self.assertTrue(result['lifetime']['destroyed'])
        self.assertNotIn('scripts.stop.0',self.domain.io.actions)


if __name__=='__main__':unittest.main()
