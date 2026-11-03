"""Actual independent input Journal phases; no target/SDK product execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_action_phase import AssetsActionPhases,input_plan
from ios.adapters.assets_action_runtime import AssetsActionRuntime
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.adapters.script_runtime import IOSScriptRuntime
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Journal,Client
from ios.self_tests.test_ios_assets_selected_end_profile import AssetsSelectedEndProfileTests
from ios.self_tests.assets_picker_fixture import RUN,TICKET,URL


class Runtime(AssetsActionRuntime,IOSAssetsRuntime):pass


class AssetsActionPhaseTests(unittest.TestCase):
    def setUp(self):
        self.h=AssetsSelectedEndProfileTests();self.h.setUp();self.addCleanup(self.h.doCleanups);self.epoch=1900000000000
        self.journal=Journal(lambda:self.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('assets')
        self.journal.activate(RUN,TICKET);self.h.context['inputPhaseOriginal']=self.journal.phase(RUN,'8'*32)
        self.selected=self.h.archive();self.selected.select();self.requests=[]
        client=Client(URL.rsplit('/runs/',1)[0],'r'*64)
        def request(path,**kwargs):
            self.requests.append((path,deepcopy(kwargs)));self.epoch+=1;return self.journal.phase(RUN,kwargs['phase_nonce'])
        client.request=request;self.phase=PhaseFixtureReader(client,RUN,'assets',epoch_ms=lambda:self.epoch,monotonic=lambda:0.)
        self.store=PrivateFeatureState(self.h.roots['primary']/('ios-assets-actions-'+RUN+'.json'))
        self.owner=AssetsActionPhases(self.selected,self.store,self.h.locks,self.phase);self.owner.reserve()
    def activate(self,index):
        row=input_plan(RUN)[index-1];ticket=format(index,'032x');self.epoch+=1
        self.journal.activate(RUN,ticket,row['verb'],row['inputs']);return ticket,row
    def runtime(self,scope):
        test=self
        class Adapter:
            def state_path(_self,selector):return test.h.roots[selector]/'session.json'
            def _candidate_guard(_self):pass
            def _binding(_self,*args):return test.h.no_native(*args)
        return Runtime(Adapter(),assets_action=scope)
    def test_all29_actual_distinct_action_tickets_replay_without_phase_native_queries_or_target_assertions(self):
        for index in range(1,len(input_plan(RUN))+1):
            ticket,row=self.activate(index);scope=self.owner.begin(index,ticket,row['verb'],row['inputs']);scope.guard()
            original=self.owner.complete(scope);self.assertEqual(ticket,original['ticket']);self.assertEqual(row,original['input'])
            self.assertEqual({'iosAssetsActionVersion','index','ticket','input','phaseBefore','phaseAfter'},set(original))
        self.assertTrue(self.owner.state['complete']);self.assertEqual(29,len(self.owner.state['records']))
        before={str(p):(p.stat().st_ino,p.read_bytes()) for root in self.h.roots.values() for p in root.rglob('*') if p.is_file()}
        with patch.object(self.phase,'status',side_effect=AssertionError('Historical phase query')):
            cold=AssetsActionPhases(self.h.archive(),self.store,self.h.locks,None,historical=True)
            self.assertEqual(format(5,'032x'),cold.ticket_for(5));self.assertEqual(format(20,'032x'),cold.ticket_for(20))
            self.assertNotEqual(TICKET,cold.ticket_for(5));self.assertNotEqual(cold.ticket_for(18),cold.ticket_for(20))
        self.assertEqual(before,{str(p):(p.stat().st_ino,p.read_bytes()) for root in self.h.roots.values() for p in root.rglob('*') if p.is_file()})
        self.assertEqual([],self.h.native_calls)
    def test_actual_foreign_activation_blocks_existing_runtime_factory_before_sources_or_any_native_call(self):
        ticket,row=self.activate(1);scope=self.owner.begin(1,ticket,row['verb'],row['inputs']);runtime=self.runtime(scope);self.activate(2)
        with patch.object(IOSScriptRuntime,'_sources',side_effect=self.h.no_native) as native:
            with self.assertRaises(NativeUIError):runtime._sources('primary')
            with self.assertRaises(NativeUIError):runtime._assets_sources('primary',self.h.locks['primary'])
            self.assertEqual(0,native.call_count)
        self.assertIsNotNone(self.owner.state['pending']);self.assertEqual([],self.owner.state['records']);self.assertEqual([],self.h.native_calls)
    def test_completed_old_action_cannot_reacquire_sources_after_next_begin_but_original_ticket_remains_readable(self):
        ticket,row=self.activate(1);first=self.owner.begin(1,ticket,row['verb'],row['inputs']);self.owner.complete(first);runtime=self.runtime(first)
        second,row=self.activate(2);current=self.owner.begin(2,second,row['verb'],row['inputs']);count=len(self.requests)
        with patch.object(IOSScriptRuntime,'_sources',side_effect=self.h.no_native) as native:
            with self.assertRaises(NativeUIError):runtime._sources('primary')
            self.assertEqual(0,native.call_count)
        self.assertEqual(count,len(self.requests));self.assertEqual(ticket,self.owner.ticket_for(1));self.assertTrue(current.guard());self.assertEqual([],self.h.native_calls)
    def test_actual_saved_action_source_after_lost_parent_write_recovers_without_phase_or_native_replay(self):
        ticket,row=self.activate(1);scope=self.owner.begin(1,ticket,row['verb'],row['inputs']);save=self.owner.save
        def lose_parent_return():
            if self.owner.state['pending'] is None and len(self.owner.state['records'])==1:raise OSError('Modeled parent commit failure after actual saved phase original')
            return save()
        self.owner.save=lose_parent_return
        with self.assertRaises(OSError):self.owner.complete(scope)
        reopened=AssetsActionPhases(self.h.archive(),self.store,self.h.locks,self.phase);count=len(self.requests)
        self.assertEqual(ticket,reopened.recover_completed()['ticket']);self.assertEqual(count,len(self.requests));self.assertEqual([],self.h.native_calls)
    def test_same_body_foreign_original_inode_cannot_reopen_completed_action_history(self):
        ticket,row=self.activate(1);scope=self.owner.begin(1,ticket,row['verb'],row['inputs']);self.owner.complete(scope)
        ref=self.owner.state['records'][0];path=self.owner.originals.path(self.owner.originals.expand(ref));raw=path.read_bytes()
        path.rename(path.with_name('retained-action-source-before-foreign-inode'));path.write_bytes(raw);path.chmod(0o600)
        count=len(self.requests)
        with self.assertRaises(NativeUIError):AssetsActionPhases(self.h.archive(),self.store,self.h.locks,None,historical=True)
        self.assertEqual(count,len(self.requests));self.assertEqual([],self.h.native_calls)


if __name__=='__main__':unittest.main()
