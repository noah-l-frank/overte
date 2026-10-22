"""Real private native-DTo files/query journals with explicit native producer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_input_reads import IOSAvatarInputReads
from ios.adapters import avatar_inputs
from ios.self_tests import test_ios_avatar_inputs as fixture


class AvatarInputReadsTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AvatarInputsTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.root=self.f.f.path/'reads';self.root.mkdir(mode=0o700);self.clock=1.;self.epoch=self.f.value['clockAfter']['epochMs']
        self.requests=[];self.current=None;self.lost=False
        def native_clock():self.epoch+=1;return self.epoch
        def send(query):
            from adapters.script_feature.history import unpack
            self.assertEqual(query,unpack(self.store.read()['payload'])[0]['pending']['query'])
            self.requests.append(deepcopy(query));self.epoch+=1;self.clock+=.001;value=deepcopy(self.f.value)
            value.update(requestId=query['commandId'],sequence=len(self.requests))
            for key in ('clockBefore','clockAfter'):value[key]=dict(epochMs=self.epoch,monotonicMs=len(self.requests)+2)
            self.current=value
            if self.lost:raise OSError('Synthetic lost native query return')
        self.reader=avatar_inputs.IOSAvatarInputs(send,lambda:json.dumps(self.current),native_clock,lambda:True,42,
            monotonic=lambda:self.clock,sleep=lambda seconds:setattr(self,'clock',self.clock+seconds))
        self.store=PrivateFeatureState(self.f.f.path/'ios-avatar-primary-input-reads.json')
    def owner(self,*,historical=False):
        return IOSAvatarInputReads(self.store,self.root,fixture.fixture.BINDING,fixture.fixture.RUN,'primary',self.f.f.lock,lambda:True,
            None if historical else self.reader,historical=historical,monotonic=lambda:self.clock)
    def test_completed_native_read_and_exact_original_delivery_survive_file_only_reconstruction(self):
        owner=self.owner();row=owner.read();before=deepcopy(self.requests)
        self.assertEqual('observed',row['status']);restored=self.owner(historical=True)
        receipt=restored.delivered(row,self.f.intent);self.assertEqual(self.f.intent['nativeCommand'],receipt['command'])
        self.assertEqual(before,self.requests);self.assertEqual(0o600,self.store.path.stat().st_mode&0o777)
        path=owner.originals.path(row['original']);self.assertEqual(0o600,path.stat().st_mode&0o777)
    def test_query_is_owned_before_transport_and_lost_return_uses_a_distinct_nonce(self):
        self.lost=True;owner=self.owner()
        with self.assertRaises(NativeUIError):owner.read()
        original=deepcopy(owner.state['pending']['query']);self.assertEqual(self.requests[0],original)
        before=len(self.requests);restored=self.owner();row=restored.recover();self.assertEqual(before,len(self.requests))
        self.assertEqual('abandoned',row['status']);self.assertEqual(original,row['query']);self.lost=False
        nextrow=restored.read();self.assertNotEqual(original['commandId'],nextrow['query']['commandId'])
        self.assertEqual(2,len(self.requests))
    def test_lost_saved_raw_source_return_is_retained_before_distinct_future_read(self):
        owner=self.owner();callback=owner.originals.intent
        def lost(kind,value):
            callback(kind,value)
            if value['phase']=='saved':raise OSError('Synthetic lost immutable original return')
        owner.originals.intent=lost
        with self.assertRaises(NativeUIError):owner.read()
        original=deepcopy(owner.state['pending']['original']);before=len(self.requests)
        restored=self.owner();row=restored.recover();self.assertEqual('abandoned',row['status']);self.assertEqual(before,len(self.requests))
        self.assertEqual(original,row['original']);self.assertEqual(self.current,restored.packet(row))
        current=restored.read();self.assertEqual(2,len(self.requests));self.assertNotEqual(row['query'],current['query'])
        self.assertEqual(2,len(list(self.root.glob('avatar-input-read-frame-*.json'))))
    def test_partial_writer_inode_is_retained_and_replacement_cannot_clear_responsibility(self):
        owner=self.owner();callback=owner.originals.intent
        def lost(kind,value):
            callback(kind,value)
            if value['phase']=='opened':raise OSError('Synthetic lost opened writer')
        owner.originals.intent=lost
        with self.assertRaises(NativeUIError):owner.read()
        original=deepcopy(owner.state['pending']['original']);path=owner.originals.path(original);inode=path.stat().st_ino
        restored=self.owner();row=restored.recover();self.assertEqual('abandoned',row['status']);self.assertEqual(inode,path.stat().st_ino)
        before=len(self.requests)
        with self.assertRaises(NativeUIError):restored.read()
        self.assertEqual(before,len(self.requests))
        raw=path.read_bytes();path.unlink();path.write_bytes(raw);path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.owner(historical=True)
    def test_lost_completed_metadata_return_is_adopted_without_query_or_original_write(self):
        owner=self.owner();write=self.store.write
        def lost(value,previous):
            write(value,previous)
            from adapters.script_feature.history import unpack
            pending=unpack(value['payload'])[0]['pending']
            if pending is not None and pending['acquisition'] is not None:raise OSError('Synthetic lost completed owner save')
        with patch.object(self.store,'write',side_effect=lost):
            with self.assertRaises(OSError):owner.read()
        before=len(self.requests);restored=self.owner();row=restored.recover()
        self.assertEqual('observed',row['status']);self.assertEqual(before,len(self.requests));restored.delivered(row,self.f.intent)
        self.assertEqual(1,len(list(self.root.glob('avatar-input-read-frame-*.json'))))
    def test_slow_final_owner_save_refuses_fresh_return_and_keeps_original_for_history(self):
        owner=self.owner();write=self.store.write
        def delayed(value,previous):
            write(value,previous)
            from adapters.script_feature.history import unpack
            state=unpack(value['payload'])[0]
            if state['rows'] and state['pending'] is None:self.clock+=1.501
        with patch.object(self.store,'write',side_effect=delayed):
            with self.assertRaises(NativeUIError):owner.read()
        before=len(self.requests);restored=self.owner(historical=True);row=restored.state['rows'][0]
        self.assertEqual('observed',row['status']);restored.delivered(row,self.f.intent);self.assertEqual(before,len(self.requests))

    def test_failed_query_journal_prevents_the_native_transport(self):
        owner=self.owner();write=self.store.write
        def fail(value,previous):
            from adapters.script_feature.history import unpack
            pending=unpack(value['payload'])[0]['pending']
            if pending is not None and pending['query'] is not None:raise OSError('Synthetic query journal failure')
            return write(value,previous)
        with patch.object(self.store,'write',side_effect=fail):
            with self.assertRaises(NativeUIError):owner.read()
        self.assertEqual([],self.requests);restored=self.owner();row=restored.recover()
        self.assertEqual('abandoned',row['status']);self.assertIsNone(row['query'])

    def test_returned_native_prefix_cannot_be_reset_by_a_later_source_query(self):
        owner=self.owner();row=owner.read();self.f.value['source']['events']=[]
        with self.assertRaises(NativeUIError):owner.read()
        self.assertEqual(2,len(self.requests));restored=self.owner()
        with self.assertRaises(NativeUIError):restored.recover()
        self.assertEqual(2,len(self.requests));self.assertEqual(row,restored.state['rows'][0])

    def test_pending_and_completed_read_schemas_reject_unknown_fields_boolean_version_and_forged_deadline(self):
        owner=self.owner();owner.read();state=deepcopy(owner.state)
        for fault in ('unknown-pending','version','deadline','orphan-file'):
            value=deepcopy(state)
            if fault=='unknown-pending':
                value['pending']=dict(index=2,query=None,epochs=[],original=None,acquisition=None,expected=True)
            elif fault=='version':value['rows'][0]['acquisition']['iosAvatarInputsAcquisitionVersion']=True
            elif fault=='deadline':
                acquisition=value['rows'][0]['acquisition'];acquisition['hostAfterMonotonic']=acquisition['hostBeforeMonotonic']+1.5
            else:
                value['rows']=[dict(index=1,status='abandoned',query=None,epochs=[],original=None,acquisition=None,partialFile=dict(bytes=1))]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.parse(owner.envelope(value))


if __name__=='__main__':unittest.main()
