"""Actual file unlink/weak functor and durable owners over modeled native IO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import feature_observation,snapshot_owned_files as source
from ios.adapters.snapshot_remove_owner import SnapshotRemoveOwner,RECEIPT
from ios.self_tests.test_ios_snapshot_owned_packet import SnapshotOwnedPackets
from ios.self_tests.test_ios_snapshot_owned_files import RUN


class SnapshotRemovalOwners(unittest.TestCase):
    def setUp(self):
        self.f=SnapshotOwnedPackets();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.file=self.f.model.capture();self.jobs=[];self.lost=False;self.ack=None;self.calls=[]
        self.f.transport.execute=self.execute
        actual=patch.object(feature_observation,'post_request',self.post);actual.start();self.addCleanup(actual.stop)
    def post(self,request,timeout):
        q=json.loads(request.data)
        if q['action']!=source.REMOVE:return self.f.post(request,timeout)
        self.f.transport.fixture.set_client_command(q);self.calls.append(deepcopy(q));self.f.transport.echo=json.dumps(q).encode()
        # This explicit modeled boundary executes the same known-file native
        # work; requested IDs are never returned as feature success.
        actual,body=self.f.model.queued(self.file)
        old=actual['commandId'];weak,row=self.f.model.jobs.pop(old);row['query']=deepcopy(q)
        self.file['removeCommandId']=q['commandId'];self.f.model.jobs[q['commandId']]=(weak,row)
        self.jobs.append(body);body();self.ack=json.dumps(dict(iosSnapshotFileRemoveReceiptVersion=1,requestId=q['commandId'],accepted=True))
        if self.lost:raise NativeUIError('Queue ran but HTTP return was lost')
        return self.f.transport
    def execute(self,session,operation,arguments):
        if arguments.get('remotePath','').endswith('/'+RECEIPT):
            self.assertEqual('mobile: pullFile',operation)
            return base64.b64encode((self.ack or '').encode()).decode()
        return self.f.execute(session,operation,arguments)
    def owner(self):
        f=self.f
        return SnapshotRemoveOwner(PrivateFeatureState(f.root/'ios-snapshot-primary-remove-0001.json'),f.lock,f.binding,RUN,'primary',1,
            f.feature,f.native(),lambda:True,epoch_ms=lambda:f.model.now,monotonic=lambda:(f.model.now-10000)/1000)
    def packet(self,index):
        owner=self.f.owner(index);owner.reserve();owner.send();owner.retain();return owner
    def prepare(self):
        admission=self.packet(1);owner=self.owner();query=owner.reserve(admission,self.file['id']);return owner,query
    def historical(self):
        f=self.f
        return SnapshotRemoveOwner.history(PrivateFeatureState(f.root/'ios-snapshot-primary-remove-0001.json'),f.lock,f.binding,RUN,'primary',1)

    def test_actual_unlink_and_weak_functor_end_are_separate_from_ack_and_source_original(self):
        with self.f.lock.held():
            owner,q=self.prepare();owner.send();owner.acknowledge();self.assertFalse((self.f.root/self.file['file']['name']).exists())
            held=self.packet(2)
            with self.assertRaises(NativeUIError):owner.observe(held)
            self.assertEqual('issued',self.owner().state['phase']);self.jobs.clear();ended=self.packet(3)
            fact=self.owner().observe(ended);self.assertTrue(fact['independentAbsenceRequired']);self.assertTrue(fact['quietWindowRequired'])
            self.assertEqual(q,fact['query']);self.assertEqual(1,len(self.calls));self.assertEqual(3,len(self.f.commands))
            self.assertEqual(fact,self.historical().proof())
            with self.assertRaises(NativeUIError):self.owner().send()

    def test_lost_queue_return_resolves_only_original_ack_then_passive_job_source(self):
        with self.f.lock.held():
            owner,q=self.prepare();self.lost=True
            with self.assertRaises(NativeUIError):owner.send()
            again=self.owner();self.assertEqual(q,again.state['query']);again.acknowledge();self.jobs.clear()
            fact=again.observe(self.packet(2));self.assertEqual(q,fact['query']);self.assertEqual(1,len(self.calls))
            with self.assertRaises(NativeUIError):self.owner().send()

    def test_missing_or_wrong_ack_never_allows_followup_observation_and_never_resends_input(self):
        with self.f.lock.held():
            owner,q=self.prepare();owner.send();correct=self.ack
            for bad in ('','{',json.dumps(dict(iosSnapshotFileRemoveReceiptVersion=1,requestId='ios-'+'f'*32,accepted=True))):
                self.ack=bad
                with self.assertRaises(NativeUIError):owner.acknowledge()
                self.assertIsNone(self.owner().state['receiptRaw']);self.assertEqual(1,len(self.calls))
            self.ack=correct;self.owner().acknowledge();self.assertEqual(correct,self.owner().state['receiptRaw'])

    def test_late_result_can_resolve_old_unlink_without_becoming_a_fresh_admission(self):
        with self.f.lock.held():
            owner,q=self.prepare();owner.send();owner.acknowledge();self.jobs.clear()
            result=self.f.owner(2);result.reserve();result.send();self.f.model.now+=2000;result.retain()
            with self.assertRaises(NativeUIError):result.qualified()
            fact=self.owner().observe(result);self.assertEqual(q,fact['query']);self.assertTrue(fact['quietWindowRequired'])

    def test_slow_issued_save_blocks_actual_unlink_and_issued_nonce_stays_owned(self):
        with self.f.lock.held():
            owner,_q=self.prepare();save=owner.save
            def slow():
                save()
                if owner.state['phase']=='issued':self.f.model.now+=2000
            owner.save=slow
            with self.assertRaises(NativeUIError):owner.send()
            self.assertEqual([],self.calls);self.assertTrue((self.f.root/self.file['file']['name']).exists())
            self.assertEqual('issued',self.owner().state['phase'])
            with self.assertRaises(NativeUIError):self.owner().send()

    def test_failed_native_unlink_original_is_retained_and_cannot_be_retired_as_success(self):
        with self.f.lock.held():
            owner,_q=self.prepare();path=self.f.root/self.file['file']['name'];path.write_bytes(b'foreign changed content')
            owner.send();owner.acknowledge();self.jobs.clear();result=self.packet(2)
            with self.assertRaises(NativeUIError):self.owner().observe(result)
            state=self.owner().state;self.assertEqual('issued',state['phase']);self.assertEqual(1,len(state['observations']))
            self.assertTrue(path.exists());self.assertEqual(1,len(self.calls))
            self.assertFalse(result.historical()['packet']['source']['jobs'][0]['result']['ok'])

    def test_new_source_birth_is_retained_as_failed_observation_without_cleanup_credit(self):
        with self.f.lock.held():
            owner,_q=self.prepare();owner.send();owner.acknowledge();self.jobs.clear()
            read=self.f.model.read
            def replacement(q=None):return dict(read(q),instance='f'*32)
            self.f.model.read=replacement;changed=self.packet(2)
            with self.assertRaises(NativeUIError):self.owner().observe(changed)
            retained=self.owner();self.assertEqual('issued',retained.state['phase']);self.assertEqual(1,len(retained.state['observations']))
            self.assertEqual('f'*32,changed.historical()['packet']['instance']);self.assertEqual(1,len(self.calls))
            self.f.model.read=read;later=self.packet(3)
            with self.assertRaises(NativeUIError):retained.observe(later)
            self.assertEqual(2,len(self.owner().state['observations']))

    def test_lost_successful_metadata_return_recovers_original_result_without_any_resend(self):
        with self.f.lock.held():
            owner,q=self.prepare();owner.send();owner.acknowledge();self.jobs.clear();result=self.packet(2);save=owner.save
            def lost():
                save()
                if owner.state['phase']=='observed':raise OSError('Successful metadata return lost')
            owner.save=lost
            with self.assertRaises(OSError):owner.observe(result)
            self.assertEqual('observed',self.owner().state['phase']);fact=self.historical().proof()
            self.assertEqual(q,fact['query']);self.assertEqual(1,len(self.calls))

    def test_historical_success_revalidates_actual_original_files_without_any_sdk(self):
        with self.f.lock.held():
            owner,_q=self.prepare();owner.send();owner.acknowledge();self.jobs.clear();result=self.packet(2);expected=owner.observe(result)
            def forbidden(*_a,**_k):raise AssertionError('Historical cleanup touched SDK')
            self.f.feature.guard=self.f.feature.original=self.f.native=forbidden
            self.assertEqual(expected,self.historical().proof())
            path=result.files().path(result.state['storage']);path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaises(NativeUIError):self.historical()


def load_tests(loader,tests,pattern):
    return loader.loadTestsFromTestCase(SnapshotRemovalOwners)


if __name__=='__main__':unittest.main()
