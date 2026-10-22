"""Actual host weak objects/private originals; native API source is modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_marker_entities import IOSEmoteMarkerEntities
from ios.self_tests import test_ios_emote_marker_scope as marker_fixture
from ios.self_tests.emote_marker_domain_fixture import RunningDomain
from ios.self_tests.marker_entities_fixture import EntityDomain


class MarkerEntityTests(unittest.TestCase):
    def setUp(self):
        self.fixture=marker_fixture.MarkerScopeTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.scope=self.fixture.owner();self.domain=RunningDomain(self.scope);self.entities=EntityDomain(self,self.scope,self.domain)
        self.owner=self.entities.owner();self.owner.capture()
    def test_actual_marker_vm_code_returned_uuid_tree_birth_and_weak_death_join(self):
        self.scope.prepare();self.domain.paint();self.scope.admit_rendered();id_=self.scope.state['admission']['marker']['id']
        held=self.entities.native.items[id_];self.scope.cleanup();self.owner.capture()
        with self.assertRaises(NativeUIError):self.owner.closed(self.scope)
        del held;gc.collect();self.owner.capture();result=self.owner.closed(self.scope)
        self.assertEqual('weak-expired',result['kind']);self.assertEqual(id_,result['ownership']['returned']['entityId'])
        self.assertTrue(result['lifetime']['destroyed'])
        saved=self.owner.store.read();archived=IOSEmoteMarkerEntities.archive(saved,store=self.owner.store,root=self.scope.root,
            binding=self.scope.binding,run=self.scope.run,role=self.scope.role,lock=self.scope.lock)
        self.assertEqual(result,archived.closed(self.scope))
    def test_wrong_actual_api_return_or_live_same_uuid_replacement_never_borrows_map_absence(self):
        self.scope.prepare();id_=self.scope.state['admission']['marker']['id'];self.scope.cleanup();self.owner.capture();self.owner.closed(self.scope)
        self.entities.native.add(id_=id_);self.owner.capture()
        with self.assertRaises(NativeUIError):self.owner.closed(self.scope)
    def test_script_ending_before_scope_cleanup_retains_transient_actual_return_and_weak_death(self):
        self.scope.prepare();id_=self.scope.state['admission']['marker']['id'];self.domain.stop();self.scope.cleanup();self.owner.capture()
        self.assertEqual('finished-execution',self.scope.state['cleanupMode']);result=self.owner.closed(self.scope)
        self.assertEqual('weak-expired',result['kind']);self.assertEqual(id_,result['ownership']['returned']['entityId'])
    def test_observed_marker_id_cannot_replace_a_missing_or_foreign_actual_api_return(self):
        self.scope.prepare();self.scope.cleanup();self.entities.native.call_events[0]['entityId']='12345678-1234-4234-8234-123456789abc'
        self.owner.capture()
        with self.assertRaises(NativeUIError):self.owner.closed(self.scope)
    def test_original_lifetime_prefix_or_candidate_cannot_be_rewritten(self):
        self.scope.prepare();self.scope.cleanup();self.owner.capture();saved=self.owner.store.read()
        raw=self.owner.record_store(self.owner.state['records'][-1]['index']).read();changed=deepcopy(raw)
        changed['binding']['processIdentity']='32';self.owner.record_store(self.owner.state['records'][-1]['index']).write(changed,raw)
        with self.assertRaises(NativeUIError):self.entities.owner()

    def test_foreign_tree_identity_in_both_entity_originals_cannot_borrow_scope_map(self):
        from adapters.original_marker_entities import closure
        self.scope.prepare();self.scope.cleanup();self.owner.capture()
        before=deepcopy(self.owner.original(self.owner.state['records'][0]));after=deepcopy(self.owner.latest())
        for value in (before,after):
            value['packet']['source']['tree']['treeInstance']='0'*32
            from adapters.native_clock_join import digest
            originals=dict(entities=value['packet'],entitiesClock=dict(capturedEpochMs=value['packet']['clockAfter']['epochMs']))
            value['clockJoin']['originalsSha256']=digest(originals)
        with self.assertRaises(NativeUIError):closure(before,after,self.scope)

    def test_unloaded_setup_cannot_ignore_transient_tree_birth_with_omitted_api_return(self):
        id_=self.entities.native.add();self.entities.native.delete(id_);self.entities.native.call_events=[]
        self.scope.cleanup();self.owner.capture();self.assertEqual('unloaded',self.scope.state['cleanupMode'])
        with self.assertRaises(NativeUIError):self.owner.closed(self.scope)
    def test_not_called_finished_setup_cannot_ignore_transient_owned_tree_birth(self):
        self.scope.prepare();self.domain.stop();self.scope.cleanup();self.entities.native.call_events=[];self.owner.capture()
        self.assertEqual('finished-execution',self.scope.state['cleanupMode']);self.assertIsNone(self.scope.state['admission']['marker'])
        with self.assertRaises(NativeUIError):self.owner.closed(self.scope)

    def test_lost_passive_query_retains_attempt_and_never_resends_nonce(self):
        send=self.entities.reader.send
        def lost(query):send(query);raise OSError('Lost actual entity source return')
        with patch.object(self.entities.reader,'send',lost),self.assertRaises(NativeUIError):self.owner.capture()
        commands=deepcopy(self.entities.native.commands);rebuilt=self.entities.owner();self.assertTrue(rebuilt.abandon())
        self.assertEqual(commands,self.entities.native.commands);rebuilt.capture()
        self.assertEqual(1,len(rebuilt.state['abandoned']));self.assertNotEqual(commands[-1]['commandId'],self.entities.native.commands[-1]['commandId'])
    def test_lost_original_file_return_adopts_without_reacquiring_native(self):
        from adapters.normal_feature_state import PrivateFeatureState
        write=PrivateFeatureState.write;lost=[]
        def once(store,value,previous):
            write(store,value,previous)
            if store.path==self.owner.record_store(2).path and not lost:lost.append(True);raise OSError('Lost immutable entity record return')
        with patch.object(PrivateFeatureState,'write',once),self.assertRaises(OSError):self.owner.capture()
        calls=len(self.entities.native.commands);rebuilt=self.entities.owner();self.assertTrue(rebuilt.resolve())
        self.assertEqual(calls,len(self.entities.native.commands));self.assertEqual(2,len(rebuilt.state['records']))


if __name__=='__main__':unittest.main()
