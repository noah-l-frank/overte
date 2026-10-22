"""Single-use live Documents acquisition, with actual original-byte counterproofs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import threading
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(Path(__file__).parent)]
from adapters.normal_ui import NativeUIError
import test_snapshot_documents as originals
import test_snapshot_documents_journey_boundary as journey


class SnapshotDocumentsAcquisitionLeaseTests(unittest.TestCase):
    def setUp(self):
        self.b=originals.Boundary();self.reader=self.b.reader()
        self.resolution=originals.UI().resolve()
    def lease(self):
        self.reader.observe();return self.reader.acquisition_lease()
    def acquire(self,token):
        return self.reader.acquire(originals.DOC,self.b.native,self.b.capture(),11000,self.resolution,observation_lease=token)
    def bodies(self):return [row for row in self.b.calls if row[0]=='binary']
    def test_only_redundant_before_read_is_removed_and_postbinary_source_is_original(self):
        token=self.lease();before=deepcopy(self.reader.last)
        result,raw=self.acquire(token)
        self.assertEqual(self.b.bytes,raw);self.assertEqual(19002,result['capturedEpochMs'])
        self.assertEqual(20000,result['acquiredEpochMs']);self.assertEqual(2,self.b.seq)
        self.assertEqual(1,len(self.bodies()));self.assertGreater(self.reader.last['sequence'],before['sequence'])
        self.assertNotEqual(before['observationId'],self.reader.last['observationId'])
        with self.assertRaises(NativeUIError):self.acquire(token)
        self.assertEqual(1,len(self.bodies()))
        # Ordinary callers retain the original acquire path and both source reads.
        self.reader.acquire(originals.DOC,self.b.native,self.b.capture(),11000,self.resolution)
        self.assertEqual(4,self.b.seq)
    def test_live_source_is_required_and_historical_floor_cannot_mint_authority(self):
        with self.assertRaises(NativeUIError):self.reader.acquisition_lease()
        first=self.reader.observe();actor=self.b.reader(True,self.reader.binding());actor.restore_history([first])
        with self.assertRaises(NativeUIError):actor.acquisition_lease()
        actor.observe();token=actor.acquisition_lease()
        self.assertEqual(self.b.bytes,actor.acquire(originals.DOC,self.b.native,self.b.capture(),11000,self.resolution,observation_lease=token)[1])
    def test_foreign_token_caller_dto_and_other_reader_cannot_authorize_binary(self):
        for foreign in ('object','dto','reader'):
            self.setUp();token=self.lease()
            if foreign=='object':value=object()
            elif foreign=='dto':value=deepcopy(self.reader.last)
            else:
                other=self.b.reader();other.observe();value=other.acquisition_lease()
            with self.subTest(foreign=foreign),self.assertRaises(NativeUIError):self.acquire(value)
            with self.assertRaises(NativeUIError):self.acquire(token)
            self.assertEqual([],self.bodies())
    def test_mint_once_per_original_and_new_observe_or_control_invalidates_lease(self):
        token=self.lease()
        with self.assertRaises(NativeUIError):self.reader.acquisition_lease()
        self.reader.observe()
        with self.assertRaises(NativeUIError):self.acquire(token)
        token=self.reader.acquisition_lease();self.reader.control('arm')
        with self.assertRaises(NativeUIError):self.acquire(token)
        self.assertEqual([],self.bodies())
    def test_delayed_frozen_epoch_or_regressing_clock_fail_before_binary_without_retry(self):
        for fault in ('stale','frozen','regression','during_identity'):
            self.setUp();token=self.lease()
            if fault=='stale':self.b.epoch+=1501
            elif fault=='frozen':self.b.clock=1.501
            elif fault=='regression':self.b.clock=-.001
            else:
                identity=self.b.identity
                def delayed():
                    result=identity();self.b.clock=1.501;return result
                self.b.identity=delayed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.acquire(token)
            with self.assertRaises(NativeUIError):self.acquire(token)
            self.assertEqual([],self.bodies())
    def test_consumption_cannot_regress_below_original_final_monotonic_read(self):
        ticks=iter((0.,.1,.2));self.reader.monotonic=lambda:next(ticks)
        token=self.lease();self.b.clock=.15;self.reader.monotonic=lambda:self.b.clock
        with self.assertRaises(NativeUIError):self.acquire(token)
        self.assertEqual([],self.bodies())
    def test_current_uid_pid_apk_and_start_identity_are_rechecked_before_body(self):
        for field,value in (('uid',12001),('processId',46),('apkSha256','9'*64),('processIdentity','45:1235')):
            self.setUp();token=self.lease();self.b.identity_value[field]=value
            with self.subTest(field=field),self.assertRaises(NativeUIError):self.acquire(token)
            self.assertEqual([],self.bodies())
    def test_tampered_last_private_original_or_guard_loss_cannot_authorize_binary(self):
        for fault in ('last','private','bound','guard'):
            self.setUp();token=self.lease()
            if fault=='last':self.reader.last['documents'][0]['inode']+=1
            elif fault=='private':self.reader._qualified['documents'][0]['inode']+=1
            elif fault=='bound':self.reader.bound['uid']+=1
            else:self.b.okay=False
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.acquire(token)
            self.assertEqual([],self.bodies())
    def test_identity_query_cannot_hide_intervening_original_mutation(self):
        for fault in ('original','new_read'):
            self.setUp();token=self.lease();identity=self.b.identity
            def changed():
                value=identity()
                if fault=='original':self.reader._qualified['documents'][0]['inode']+=1
                else:
                    # A newer acquisition invalidates this transaction even if
                    # the original binary still has identical bytes.
                    with self.reader._lease_lock:self.reader._qualified=None
                return value
            self.b.identity=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.acquire(token)
            self.assertEqual([],self.bodies())
    def test_pending_or_failed_writer_never_reads_binary(self):
        for fault in ('pending','failed'):
            self.setUp()
            if fault=='pending':
                self.b.document['writeClosedEpochMs']=0;self.b.fd.update(closed=False,closedEpochMs=0)
            else:self.b.fd['error']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.acquire(self.lease())
            self.assertEqual([],self.bodies())
    def test_final_observe_rejects_frozen_sequence_foreign_source_content_and_lost_guard(self):
        for fault in ('sequence','instance','inode','hash','writer','guard'):
            self.setUp();token=self.lease()
            def change(row):
                if fault=='sequence':row['sequence']=1
                elif fault=='instance':row['instance']='9'*32
                elif fault=='inode':row['documents'][0]['inode']+=1
                elif fault=='hash':row['documents'][0]['sha256']='9'*64
                elif fault=='writer':row['fdLifetimes'][0].update(closed=False,closedEpochMs=0)
                else:self.b.okay=False
            self.b.fault=change
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.acquire(token)
            self.assertEqual(2,self.b.seq);self.assertEqual(1,len(self.bodies()))
            with self.assertRaises(NativeUIError):self.acquire(token)
    def test_wrong_binary_is_rejected_and_failed_lease_cannot_be_reused(self):
        token=self.lease();binary=self.b.binary
        self.b.binary=lambda *args:binary(*args)+b'changed'
        with self.assertRaises(NativeUIError):self.acquire(token)
        with self.assertRaises(NativeUIError):self.acquire(token)
        self.assertEqual(1,len(self.bodies()))
    def test_two_concurrent_consumers_issue_exactly_one_original_body_read(self):
        token=self.lease();entered=threading.Event();release=threading.Event();binary=self.b.binary;results=[]
        def body(*args):
            entered.set();self.assertTrue(release.wait(2));return binary(*args)
        self.b.binary=body
        def run():
            try:self.acquire(token);results.append('complete')
            except NativeUIError:results.append('rejected')
        first=threading.Thread(target=run);first.start();self.assertTrue(entered.wait(2))
        second=threading.Thread(target=run);second.start();second.join(2);release.set();first.join(2)
        self.assertFalse(first.is_alive() or second.is_alive());self.assertCountEqual(['complete','rejected'],results)
        self.assertEqual(1,len(self.bodies()))


class SnapshotDocumentsActualFileLeaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):journey.SnapshotDocumentsJourneyTests.setUpClass()
    def setUp(self):
        self.flow=journey.SnapshotDocumentsJourneyTests();self.flow.setUp();self.addCleanup(self.flow.tearDown)
    def test_actual_normal_picker_write_acquires_original_java_file_and_completion(self):
        f=self.flow;doc=f.save();token=f.owner.acquisition_lease()
        result,raw=f.owner.acquire(doc['documentId'],f.identity(),f.capture(),journey.PHONE_UID,f.resolution,observation_lease=token)
        path=f.boundary.provider.parent/('overte-snapshot-documents-'+journey.RUN)/(doc['documentId']+'.png')
        self.assertEqual(path.read_bytes(),raw);self.assertEqual(doc['writeClosedEpochMs'],result['capturedEpochMs'])
        self.assertEqual(doc['inode'],path.stat().st_ino);f.retire();self.assertFalse(path.exists())
    def test_changed_actual_file_bytes_after_lease_remain_unqualified_and_preserved(self):
        f=self.flow;doc=f.save();token=f.owner.acquisition_lease()
        path=f.boundary.provider.parent/('overte-snapshot-documents-'+journey.RUN)/(doc['documentId']+'.png')
        original_inode=path.stat().st_ino;path.write_bytes(path.read_bytes()+b'changed')
        self.assertEqual(original_inode,path.stat().st_ino)
        with self.assertRaises(NativeUIError):f.owner.acquire(doc['documentId'],f.identity(),f.capture(),journey.PHONE_UID,f.resolution,observation_lease=token)
        self.assertTrue(path.exists());self.assertTrue(path.read_bytes().endswith(b'changed'))
    def test_same_bytes_foreign_actual_inode_and_changed_file_remain_red_and_preserved(self):
        f=self.flow;doc=f.save();token=f.owner.acquisition_lease()
        path=f.boundary.provider.parent/('overte-snapshot-documents-'+journey.RUN)/(doc['documentId']+'.png')
        original=path.with_suffix('.retained');path.rename(original);path.write_bytes(original.read_bytes());path.chmod(0o600)
        self.assertNotEqual(doc['inode'],path.stat().st_ino)
        with self.assertRaises(NativeUIError):f.owner.acquire(doc['documentId'],f.identity(),f.capture(),journey.PHONE_UID,f.resolution,observation_lease=token)
        with self.assertRaises(RuntimeError):f.boundary.provider.call('delete',doc['documentId'])
        self.assertEqual(original.read_bytes(),path.read_bytes());self.assertTrue(original.exists())


if __name__=='__main__':unittest.main()
