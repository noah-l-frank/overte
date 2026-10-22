"""Compose actual private byte owners and cached functors; native IO is modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
import uuid
import weakref
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import feature_observation,snapshot_chunks,snapshot_original_file as source
from ios.adapters.snapshot_manifest import SnapshotManifest
from ios.self_tests import test_ios_snapshot_chunk_owner as fixture
from ios.self_tests import test_ios_snapshot_file_work as work_fixture


class FileJobs(work_fixture.Jobs):
    # All modeled native operations happen in one actual clock millisecond.
    # Each original clock read still has its own nonce and increasing sequence.
    def tick(self):return 20000
    def clock(self):return dict(epochMs=20000,monotonicMs=10000)


class SnapshotOriginalFileTests(unittest.TestCase):
    def setUp(self):
        self.h=fixture.SnapshotChunkOwnerTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.f=self.h.f;self.jobs=FileJobs();self.callbacks=[]
        actual=patch.object(feature_observation,'post_request',self.post);actual.start();self.addCleanup(actual.stop)

    def post(self,request,timeout):
        query=json.loads(request.data);token=work_fixture.Token()
        row=dict(id=uuid.uuid4().hex,query=deepcopy(query),queuedEpochMs=self.jobs.tick(),enteredEpochMs=None,
            returnedEpochMs=None,finallyEpochMs=None,expiredEpochMs=None,publication=None,publishedEpochMs=None,alive=True)
        self.jobs.jobs[row['id']]=(weakref.ref(token),row)
        def queued_native_job():
            held=token
            row['enteredEpochMs']=self.jobs.tick()
            try:
                result=self.h.post(request,timeout)
                row.update(publication=True,publishedEpochMs=self.jobs.tick(),returnedEpochMs=self.jobs.tick())
                return result
            finally:
                row['finallyEpochMs']=self.jobs.tick()
                assert held is token
        result=queued_native_job();self.callbacks.append(queued_native_job);return result

    def completed(self):
        before=self.h.manifest();owners=[]
        for index,offset in enumerate(range(0,self.h.path.stat().st_size,snapshot_chunks.CHUNK_BYTES),1):
            owner=self.h.owner(index);owner.reserve_original(before,self.h.path.name,offset);owner.send(20000);owner.recover();owners.append(owner)
        after=SnapshotManifest(PrivateFeatureState(self.f.root/'ios-snapshot-primary-manifest-0002.json'),
            self.f.lock,self.f.binding,fixture.fixture.RUN,'primary',2,self.f.feature,self.f.new_clock(),lambda:True)
        after.reserve('still-png');after.send(20000);after.recover()
        return before,after,owners

    def test_actual_bytes_stable_manifests_and_separate_cached_functor_death(self):
        with self.f.lock.held():
            before,after,owners=self.completed();held=self.jobs.read()
            with self.assertRaises(NativeUIError):source.original(before,after,owners,held)
            self.callbacks.clear();retired=self.jobs.read();fact,raw=source.original(before,after,owners,retired)
            self.assertEqual(self.h.path.read_bytes(),raw);self.assertEqual(3,len(fact['chunks']))
            self.assertTrue(fact['imageOutcomeRequired']);self.assertTrue(fact['destinationOutcomeRequired'])
            self.assertTrue(fact['quietWindowRequired']);self.assertEqual(5,len(fact['queryIds']))
            # Historical assembly reads the immutable originals only, after SDK retirement.
            def forbidden(*_args,**_kwargs):raise AssertionError('Historical file join touched SDK')
            self.f.feature.original=self.f.clock.finish=forbidden
            self.assertEqual((fact,raw),source.original(before,after,owners,retired))

    def test_unknown_failed_unpublished_and_live_jobs_never_prove_original_file(self):
        with self.f.lock.held():
            before,after,owners=self.completed();self.callbacks.clear();retired=self.jobs.read()
            source.original(before,after,owners,retired)
            for fault in ('query','publication','finally','held','sample','source','run','pid','duplicate-query'):
                value=deepcopy(retired);row=value['source']['jobs'][0]
                if fault=='query':row['query']['commandId']='ios-'+'f'*32
                elif fault=='publication':row['publication']=False
                elif fault=='finally':row['finallyEpochMs']=None
                elif fault=='held':row.update(alive=True,expiredEpochMs=None)
                elif fault=='sample':row['enteredEpochMs']=20001;value['clockAfter']['epochMs']=20002
                elif fault=='source':value['source']['complete']=False
                elif fault=='run':value['runId']='f'*32
                elif fault=='pid':value['processId']=43
                else:value['source']['jobs'][1]['query']=deepcopy(row['query'])
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(before,after,owners,value)

    def test_missing_reordered_duplicate_or_mutated_original_chunks_cannot_assemble(self):
        with self.f.lock.held():
            before,after,owners=self.completed();self.callbacks.clear();retired=self.jobs.read()
            for values in (owners[:-1],owners[::-1],[owners[0],owners[0],owners[2]]):
                with self.subTest(indices=[owner.index for owner in values]),self.assertRaises(NativeUIError):
                    source.original(before,after,values,retired)
            path=owners[1].files().path(owners[1].files().expand(owners[1].state['proof']))
            path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaises(NativeUIError):source.original(before,after,owners,retired)

    def test_changed_actual_file_between_manifests_is_rejected(self):
        with self.f.lock.held():
            actual=self.h.post
            def changed(request,timeout):
                if json.loads(request.data)['operation']=='list' and self.f.files.commands:
                    self.h.path.write_bytes(self.h.path.read_bytes()+b'changed')
                return actual(request,timeout)
            self.h.post=changed
            before,after,owners=self.completed();self.callbacks.clear()
            with self.assertRaises(NativeUIError):source.original(before,after,owners,self.jobs.read())

    def test_changed_actual_native_clock_birth_between_originals_is_rejected(self):
        with self.f.lock.held():
            actual=self.f.native.mutate
            def changed(value):
                actual(value)
                if self.f.native.sequence>2:value['instance']='f'*32
            self.f.native.mutate=changed
            before,after,owners=self.completed();self.callbacks.clear()
            with self.assertRaises(NativeUIError):source.original(before,after,owners,self.jobs.read())


if __name__=='__main__':unittest.main()
