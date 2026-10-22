"""Real durable query and raw-byte ownership, not native execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import check as transport_check
from ios.adapters.tablet_web_packets import TabletWebPackets
from ios.adapters import tablet_web_sources as sources,tablet_web_dom as dom,uikit_input
from ios.self_tests.test_ios_avatar_input_owner import BINDING as CANDIDATE
from ios.self_tests.test_ios_tablet_web_sources import RUN,ROOT,packet as native_sources,stamp
from ios.self_tests.tablet_web_dom_fixture import original_bodies,packet as native_dom
from ios.self_tests.test_ios_uikit_input import packet as native_uikit

BINDING=dict(CANDIDATE,processIdentity='31')


class TabletWebPacketsTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name);self.root.chmod(0o700)
        self.sends=[];self.current=None
    def owner(self,component='sources',**kwargs):
        return TabletWebPackets(self.root,BINDING,RUN,'primary',ROOT,31,component,lambda:True,monotonic=lambda:0.,epoch_ms=lambda:120000,**kwargs)
    def reader(self,producer=native_sources,cls=sources.IOSTabletSources,original=None,epoch=91000):
        def send(query):
            transport_check();self.sends.append(deepcopy(query));self.current=producer(len(self.sends));self.current['commandId']=query['commandId']
        return cls(send,original or (lambda:json.dumps(self.current)),lambda:epoch,lambda:True,31,monotonic=lambda:0.,sleep=lambda value:None)
    def test_actual_queries_and_raw_bytes_reconstruct_with_new_reader_and_unchanged_callbacks(self):
        owner=self.owner();reader=self.reader();send,original=reader.send,reader.original
        first=owner.capture(reader);second=owner.capture(reader)
        self.assertIs(send,reader.send);self.assertIs(original,reader.original);self.assertEqual(2,len(self.sends))
        reconstructed=self.owner();self.assertEqual([first,second],reconstructed.history())
        record=reconstructed.originals.read(reconstructed.originals.expand(reconstructed.state['records'][0]))
        raw=reconstructed.segments.read(record['raws'][0]['segments'])
        self.assertEqual(first,json.loads(raw));self.assertEqual(self.sends[0],record['query'])
        self.assertEqual(3,reconstructed.state['nextRaw']);self.assertIsNone(reconstructed.state['pending'])
    def test_lost_send_return_stays_owned_and_is_never_reissued_by_reconstruction(self):
        owner=self.owner();reader=self.reader()
        def lost(query):self.sends.append(deepcopy(query));raise OSError('Actual query return lost')
        reader.send=lost
        with self.assertRaises(NativeUIError):owner.capture(reader)
        restored=self.owner();self.assertEqual([],restored.history());self.assertFalse(restored.state['pending']['sendReturned'])
        with self.assertRaises(NativeUIError):restored.capture(self.reader())
        restored.archive_pending(abandon=True);self.assertEqual(1,len(self.sends));self.assertEqual([],restored.history())
        self.assertEqual('abandoned',restored.originals.read(restored.originals.expand(restored.state['records'][0]))['status'])
    def test_pending_dom_raw_is_durable_and_later_same_query_ready_preserves_native_history(self):
        bodies=original_bodies();ready=native_dom(bodies[0][0]);clock=ready['clockBefore'];pending=deepcopy(ready)
        pending.update(status='pending',source={});raws=[]
        def produce(index):
            raws[:]=[pending,ready];return deepcopy(ready)
        def original():
            value=deepcopy(raws.pop(0));value['commandId']=self.sends[-1]['commandId']
            if value['status']=='ready':value['source']['dom']['requestId']=value['commandId']
            return json.dumps(value)
        owner=self.owner('dom');reader=self.reader(produce,dom.IOSTabletWebDOM,original,epoch=clock['epochMs'])
        actual=owner.capture(reader);self.assertEqual('ready',actual['status'])
        history=self.owner('dom').history();self.assertEqual(['pending','ready'],[row['status'] for row in history]);self.assertEqual(1,len(self.sends))
    def test_abandoned_actual_pending_source_birth_remains_a_floor_for_new_query(self):
        body=original_bodies()[0][0];pending=native_dom(body);pending.update(status='pending',source={});count=[0]
        def original():
            count[0]+=1
            if count[0]>1:raise OSError('Actual pending poll return lost')
            return json.dumps(dict(pending,commandId=self.sends[-1]['commandId']))
        owner=self.owner('dom');reader=self.reader(lambda index:deepcopy(pending),dom.IOSTabletWebDOM,original,epoch=pending['clockAfter']['epochMs'])
        with self.assertRaises(NativeUIError):owner.capture(reader)
        restored=self.owner('dom');self.assertEqual(1,len(restored.history()));restored.archive_pending(abandon=True)
        changed=deepcopy(pending);changed.update(instance='0'*32,sequence=2)
        reader=self.reader(lambda index:deepcopy(changed),dom.IOSTabletWebDOM,epoch=changed['clockAfter']['epochMs'])
        with self.assertRaises(NativeUIError):restored.capture(reader)
        rejected=self.owner('dom');self.assertEqual(1,len(rejected.history()));self.assertEqual(2,len(self.sends))
        row=rejected.state['pending']['raws'][0];self.assertEqual('rejected',row['outcome'])
        self.assertEqual('0'*32,json.loads(rejected.segments.read(row['segments']))['instance']);rejected.archive_pending(abandon=True)
        reconstructed=self.owner('dom');self.assertTrue(reconstructed.blocked)
        with self.assertRaises(NativeUIError):reconstructed.capture(self.reader(lambda index:deepcopy(pending),dom.IOSTabletWebDOM,epoch=pending['clockAfter']['epochMs']))
        self.assertEqual(2,len(self.sends))
    def test_complete_record_after_lost_flush_can_recover_without_rewrite_or_native_request(self):
        owner=self.owner();reader=self.reader();fsync=os.fsync;failed=[False]
        def lost(descriptor):
            name=os.readlink('/proc/self/fd/'+str(descriptor))
            if not failed[0] and 'tabletweb-sources-packets-frame-' in name:
                failed[0]=True;raise OSError('Actual complete record flush return lost')
            return fsync(descriptor)
        with patch('os.fsync',side_effect=lost),self.assertRaises(OSError):owner.capture(reader)
        restored=self.owner();ref=deepcopy(restored.state['recordIntent']);self.assertEqual('opened',ref['phase'])
        path=restored.originals.path(ref);before=path.stat();raw=path.read_bytes();restored.recover_record()
        self.assertEqual(before,path.stat());self.assertEqual(raw,path.read_bytes());self.assertEqual(1,len(self.sends))
        self.assertEqual(1,len(self.owner().history()))
    def test_unsafe_legacy_uikit_never_creates_raw_file_and_historical_index_reset_fails(self):
        owner=self.owner('uikit');reader=self.reader(lambda index:native_uikit(index),uikit_input.IOSUIKitInput)
        with self.assertRaises(NativeUIError):owner.capture(reader)
        self.assertEqual([],list(self.root.glob('*-frame-*')));restored=self.owner('uikit');self.assertEqual(1,restored.state['nextRaw'])
        unsafe=restored.state['pending']['unsafe'];self.assertEqual([dict(bytes=len(json.dumps(self.current).encode()),sha256=hashlib.sha256(json.dumps(self.current).encode()).hexdigest())],unsafe)
        self.assertTrue(restored.blocked)
        owner=self.owner();owner.capture(self.reader());bad=deepcopy(owner.state);bad['nextRaw']=1
        owner.store.write(bad,owner.saved)
        with self.assertRaises(NativeUIError):self.owner()
    def test_actual_empty_opened_prefix_cannot_change_after_failed_capture_and_archive(self):
        owner=self.owner();callback=owner.segments.intent
        def lost(value):
            callback(value)
            if value['chunks'] and value['chunks'][-1]['phase']=='opened':raise OSError('Actual opened prefix return lost')
        owner.segments.intent=lost
        with self.assertRaises(NativeUIError):owner.capture(self.reader())
        restored=self.owner();parent=restored.state['pending']['raws'][0]['segments'];path=restored.segments.store.path(parent['chunks'][0])
        self.assertEqual(0,path.stat().st_size);restored.archive_pending(abandon=True);path.write_bytes(b'{')
        with self.assertRaises(NativeUIError):self.owner()
    def test_slow_issued_journal_blocks_actual_transport_and_host_rollback_blocks_new_query(self):
        owner=self.owner();clock=[0.];owner.monotonic=lambda:clock[0];save=owner.save
        def slow():
            save()
            if owner.state['pending'] is not None and owner.state['pending']['status']=='issued':clock[0]=2.
        owner.save=slow
        with self.assertRaises(NativeUIError):owner.capture(self.reader())
        self.assertEqual([],self.sends);self.assertFalse(owner.state['pending']['sendReturned'])
        owner=self.owner();owner.archive_pending(abandon=True);owner.monotonic=lambda:3.;owner.epoch_ms=lambda:120001
        owner.capture(self.reader());restored=self.owner();restored.epoch_ms=lambda:119999
        before=len(self.sends)
        with self.assertRaises(NativeUIError):restored.capture(self.reader())
        self.assertEqual(before,len(self.sends))
    def test_historical_reader_only_revalidates_real_files_and_refuses_all_new_ownership(self):
        owner=self.owner();actual=owner.capture(self.reader());before={p.name:(p.stat(),p.read_bytes()) for p in self.root.iterdir()}
        historical=self.owner(historical=True);self.assertEqual([actual],historical.history())
        for action in (lambda:historical.capture(self.reader()),historical.save,historical.archive_pending,historical.recover_record):
            with self.assertRaises(NativeUIError):action()
        self.assertEqual(before,{p.name:(p.stat(),p.read_bytes()) for p in self.root.iterdir()});self.assertEqual(1,len(self.sends))
        with self.assertRaises(NativeUIError):self.owner('state',historical=True)
        self.assertEqual(before,{p.name:(p.stat(),p.read_bytes()) for p in self.root.iterdir()})
    def test_reader_with_unowned_prior_observation_cannot_be_adopted_or_reset(self):
        reader=self.reader();reader.read(RUN,ROOT);owner=self.owner()
        with self.assertRaises(NativeUIError):owner.capture(reader)
        self.assertEqual(1,len(self.sends));self.assertIsNone(owner.state['pending'])
    def test_actual_pid_must_match_canonical_original_binding_before_any_ownership_file(self):
        for binding,pid in ((CANDIDATE,31),(dict(BINDING,processIdentity='031'),31),(BINDING,True)):
            with self.subTest(binding=binding['processIdentity'],pid=pid),self.assertRaises(NativeUIError):
                TabletWebPackets(self.root,binding,RUN,'primary',ROOT,pid,'sources',lambda:True)
        self.assertEqual([],list(self.root.iterdir()))
    def test_matching_wrong_pid_original_is_retained_exactly_but_never_a_valid_floor_or_live_result(self):
        def wrong(index):return dict(native_sources(index),processId=42)
        owner=self.owner();reader=self.reader(wrong)
        with self.assertRaises(NativeUIError):owner.capture(reader)
        restored=self.owner();self.assertEqual([],restored.history());self.assertTrue(restored.blocked)
        row=restored.state['pending']['raws'][0];self.assertEqual('rejected',row['outcome'])
        self.assertEqual(json.dumps(self.current).encode(),restored.segments.read(row['segments']))
        restored.archive_pending(abandon=True)
        with self.assertRaises(NativeUIError):self.owner().capture(self.reader())
        self.assertEqual(1,len(self.sends))
    def test_same_query_terminal_dom_rewrite_is_preserved_as_rejected_after_real_first_ready(self):
        body=original_bodies()[0][0];ready=native_dom(body);changed=deepcopy(ready)
        changed['source']['dom']['editor']['text']='changed controlled text'
        next(row for row in changed['source']['dom']['elements'] if row['id']=='text')['value']='changed controlled text'
        values=[]
        def producer(index):values[:]=[ready,changed];return deepcopy(ready)
        def original():
            value=deepcopy(values.pop(0));value['commandId']=self.sends[-1]['commandId'];value['source']['dom']['requestId']=value['commandId'];return json.dumps(value)
        reader=self.reader(producer,dom.IOSTabletWebDOM,original,epoch=ready['clockAfter']['epochMs'])
        # Force one extra read to expose a source violating its terminal-cache
        # contract; the collector must independently reject the actual rewrite.
        reader._ready=lambda value:False
        with self.assertRaises(NativeUIError):self.owner('dom').capture(reader)
        restored=self.owner('dom');self.assertEqual(1,len(restored.history()));self.assertTrue(restored.blocked)
        self.assertEqual(['accepted','rejected'],[row['outcome'] for row in restored.state['pending']['raws']])
    def test_unknown_private_grammar_has_only_digest_responsibility_and_never_raw_artifact(self):
        def unsafe(index):return dict(native_uikit(index),iosUIKitInputVersion=2,capturedPassword='must-not-persist')
        with self.assertRaises(NativeUIError):self.owner('uikit').capture(self.reader(unsafe,uikit_input.IOSUIKitInput))
        restored=self.owner('uikit');self.assertTrue(restored.blocked);self.assertEqual(1,len(restored.state['pending']['unsafe']))
        self.assertEqual([],list(self.root.glob('*-frame-*')))
        self.assertFalse(any(b'must-not-persist' in path.read_bytes() for path in self.root.iterdir()))


if __name__=='__main__':unittest.main()
