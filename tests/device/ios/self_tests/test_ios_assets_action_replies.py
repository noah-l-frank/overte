"""Actual independent reply raws and current phase provenance, no SDK/device."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_action_reply_owner import ActionAssetsReplyReads
from ios.adapters.assets_reply_owner import OwnedAssetsReplyReads
from ios.adapters.assets_episodes import AssetsEpisodes
from ios.self_tests.assets_reply_fixture import Boundary,RUN,URL
from ios.self_tests.test_ios_assets_action_phase import AssetsActionPhaseTests


class AssetsActionRepliesTests(unittest.TestCase):
    def setUp(self):
        self.a=AssetsActionPhaseTests();self.a.setUp();self.addCleanup(self.a.doCleanups);self.episodes=AssetsEpisodes(self.a.selected,self.a.h.locks)
        self.action=None;self.episode=None
        for index in range(1,5):
            ticket,row=self.a.activate(index);self.action=self.a.owner.begin(index,ticket,row['verb'],row['inputs'])
            if index==2:self.episodes.begin(1,ticket)
            if index==4:self.episode=self.episodes.begin(2,ticket)
            else:self.a.owner.complete(self.action)
        held=self.episode.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.binding=deepcopy(self.a.selected.context['roles']['primary']['binding'])
        self.b=Boundary();self.root=Path(self.episode.descriptor['directories']['primary']['stateRoot']['path'])
        self.store=PrivateFeatureState(self.root/('ios-assets-'+RUN+'-primary-replies.json'));self.o=self.owner(self.action)
        self.o.reserve(self.episode.descriptor['ticket'])
    def owner(self,action):
        return ActionAssetsReplyReads(self.b.native(),self.store,self.binding,RUN,URL,lock=self.episode.locks['primary'],
            actions=self.a.owner,episode=self.episode,action=action)
    def advance(self,index):
        self.a.owner.complete(self.action)
        for number in range(self.action.index+1,index+1):
            ticket,row=self.a.activate(number);action=self.a.owner.begin(number,ticket,row['verb'],row['inputs'])
            if number<index:self.a.owner.complete(action)
        self.action=action;self.o=self.owner(action);return action
    def forbidden(self,*_args,**_kwargs):raise AssertionError('Historical source cannot query/send/write')
    def test_new_read_jobs_use_their_actual_distinct_action_tickets_without_retiming_owner_or_old_job(self):
        first=self.o.read('action4-inventory');old=self.o._job('action4-inventory')['query'];self.advance(5)
        second=self.o.read('action5-inventory');new=self.o._job('action5-inventory')['query']
        self.assertEqual(first['mappings'],second['mappings']);self.assertEqual(format(4,'032x'),old['ticket']);self.assertEqual(format(5,'032x'),new['ticket'])
        self.assertEqual(format(4,'032x'),self.o.state['ticket']);self.assertNotEqual(old['commandId'],new['commandId'])
        for query in self.o.state['commands']:
            row=self.o.query_sources.query(query,self.o.state)
            self.assertEqual(query['ticket'],row['actionTicket']);self.assertEqual(int(query['ticket'],16),row['actionIndex'])
        self.assertEqual(3,self.o.previous['iosAssetsReplyOwnerVersion'])
    def test_lost_old_job_return_is_observed_and_retired_with_original_ticket_and_current_cleanup_action(self):
        self.b.defer=True;self.b.lost='inventory'
        with self.assertRaises(NativeUIError):self.o.read('lost-action4')
        original=deepcopy(self.o._job('lost-action4')['query']);self.advance(13);before=deepcopy(self.b.data);self.o.close()
        self.assertEqual('closed',self.o.state['phase']);self.assertEqual(before,self.b.data)
        queries=[q for q in self.b.requests if q['operation'] in ('observe','retire')]
        self.assertTrue(queries);self.assertTrue(any(q['operation']=='retire' for q in queries))
        for query in queries:
            self.assertEqual(original['commandId'],query['jobId']);self.assertEqual(original['ticket'],query['ticket'])
            row=self.o.query_sources.query(query,self.o.state);self.assertEqual(13,row['actionIndex']);self.assertEqual(format(13,'032x'),row['actionTicket'])
            self.assertEqual(original,row['jobOrigin'])
        self.assertEqual(1,sum(q['operation']=='inventory' for q in self.b.requests))
    def test_cross_action_parent_inventory_must_be_fresh_for_new_mapping_job_before_native_delivery(self):
        self.o.read('old-inventory');self.advance(5);count=len(self.b.requests);refs=len(self.o.query_sources.state['refs'])
        with self.assertRaises(NativeUIError):self.o.read('foreign-parent','mapping',source_slot='old-inventory',relative_path='main.gltf')
        self.assertEqual(count,len(self.b.requests));self.assertEqual(refs,len(self.o.query_sources.state['refs']))
        self.o.read('new-inventory');proof=self.o.read('current-mapping','mapping',source_slot='new-inventory',relative_path='main.gltf')
        self.assertEqual('mapping',proof['kind']);self.assertEqual(format(5,'032x'),self.o._job('current-mapping')['query']['ticket'])
    def test_foreign_live_phase_refuses_new_query_before_native_and_before_provenance_birth(self):
        self.a.activate(5);count=len(self.b.requests);before=self.o.query_sources.store.path.read_bytes()
        with self.assertRaises(NativeUIError):self.o.read('stale-scope')
        self.assertEqual(count,len(self.b.requests));self.assertEqual(before,self.o.query_sources.store.path.read_bytes());self.assertEqual([],self.o.state['jobs'])
    def test_cold_originals_are_query_write_free_and_literal_reader_cannot_adopt_version3(self):
        self.o.read('inventory');self.a.owner.complete(self.action);before={str(p):(p.read_bytes(),p.stat().st_ino) for p in self.root.rglob('*') if p.is_file()}
        with patch.object(self.b,'send',side_effect=self.forbidden),patch.object(self.a.phase,'status',side_effect=self.forbidden),patch.object(PrivateFeatureState,'write',side_effect=self.forbidden):
            restored=self.owner(None);self.assertEqual(self.o.state,restored.state)
            with self.assertRaises(NativeUIError):OwnedAssetsReplyReads(self.b.native(),self.store,self.binding,RUN,URL,lock=self.episode.locks['primary'])
        self.assertEqual(before,{str(p):(p.read_bytes(),p.stat().st_ino) for p in self.root.rglob('*') if p.is_file()})
    def test_samebytes_foreign_action_source_inode_refuses_owner_replay_without_native(self):
        self.o.read('inventory');ref=self.o.query_sources.state['refs'][0];path=self.o.query_sources.originals.path(self.o.query_sources.originals.expand(ref));raw=path.read_bytes()
        path.rename(path.with_name('retained-query-action-before-foreign-inode'));path.write_bytes(raw);path.chmod(0o600)
        with patch.object(self.b,'send',side_effect=self.forbidden),patch.object(self.a.phase,'status',side_effect=self.forbidden):
            with self.assertRaises(NativeUIError):self.owner(None)
    def test_saved_provenance_before_lost_parent_cas_recovers_without_issuing_start_or_retiming_source(self):
        actual=self.o.query_sources.save
        def lost():
            if self.o.query_sources.state['pending'] is None and self.o.query_sources.state['refs']:
                raise OSError('Modeled lost provenance parent commit before native start')
            return actual()
        with patch.object(self.o.query_sources,'save',side_effect=lost):
            with self.assertRaises(OSError):self.o.read('unissued')
        self.assertEqual([],self.b.requests);restored=self.owner(self.action)
        with patch.object(self.b,'send',side_effect=self.forbidden),patch.object(self.a.phase,'status',side_effect=self.forbidden):
            row=restored.query_sources.recover();self.assertEqual(4,row['actionIndex'])
        self.assertEqual([],self.b.requests);self.assertEqual([],restored.state['commands']);self.assertEqual([],restored.state['jobs'])
        self.assertEqual(1,len(restored.query_sources.state['refs']))


if __name__=='__main__':unittest.main()
