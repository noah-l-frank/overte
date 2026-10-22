"""Composed real owners/transports with explicit native/work clock producers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.native_clock_join import NativeClockAcquisition
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import normal_input,snapshot_capture_controls as controls
from ios.adapters.snapshot_input_owner import SnapshotInputOwner
from ios.adapters.snapshot_manifest import SnapshotManifest
from ios.adapters.snapshot_cancellation import pending
from ios.self_tests import test_ios_snapshot_manifest as manifest_fixture
from ios.self_tests.test_ios_snapshot_inputs import Native as InputNative
from ios.self_tests import test_ios_snapshot_captures as capture_fixture
from self_tests.test_native_feature_observation import Boundary

BASE=1700000000000
RUN=manifest_fixture.RUN


class SnapshotCancellationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=manifest_fixture.SnapshotManifestTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.manifest_native=Boundary()
        self.now=BASE
        clock=patch('time.time',lambda:self.now/1000);clock.start();self.addCleanup(clock.stop)
        self.native=InputNative();self.native.name='parity-'+RUN[:16]+'-still-png';actual=self.native.observed
        def observed():
            value=actual();value['controls'][0].update(snapshotMode=0,snapshotFormat='png',snapshotCapturing=self.native.field=='snapshot.cancel')
            return value
        self.native.observed=observed
        transport=patch.object(normal_input,'urlopen',self.native.post);transport.start();self.addCleanup(transport.stop)
        self.normal=self.native.input()

    def manifest(self,index,epoch,files=None):
        fixture=self.fixture;source=self.manifest_native
        # Populate each modeled native source when produced, before transport;
        # never modify a captured original or reuse its acquisition timestamp.
        def produce(value):
            def clocks(node):
                if isinstance(node,dict):
                    for key,item in node.items():
                        if key.endswith('EpochMs'):node[key]=epoch
                        else:clocks(item)
                elif isinstance(node,list):
                    for item in node:clocks(item)
            clocks(value);value['processId']=42;value['instance']=getattr(self,'manifest_birth','a'*32)
        source.mutate=produce
        reader=NativeFeatureObservation(source.send,source.original,lambda:epoch,source.guard,42,ios=True,
            monotonic=lambda:source.clock,sleep=source.sleep)
        clock=NativeClockAcquisition(reader,epoch_ms=lambda:epoch,monotonic=lambda:source.clock)
        store=PrivateFeatureState(fixture.root/('ios-snapshot-primary-manifest-'+format(index,'04d')+'.json'))
        owner=SnapshotManifest(store,fixture.lock,fixture.binding,RUN,'primary',index,fixture.feature,clock,lambda:True)
        actual=fixture.files.post
        def native_files(request,timeout):
            result=actual(request,timeout);fixture.files.value['sampleEpochMs']=epoch
            if files is not None:fixture.files.value['files']=deepcopy(files)
            return result
        from ios.adapters import feature_observation
        with patch.object(feature_observation,'post_request',native_files):
            owner.reserve('still-png');owner.send(epoch);owner.recover()
        return owner

    def prepared(self):
        fixture=self.fixture;first=self.manifest(1,BASE-10)
        owner=SnapshotInputOwner(PrivateFeatureState(fixture.root/'ios-snapshot-primary-inputs.json'),fixture.lock,
            fixture.binding,RUN,'primary',self.normal,lambda:True)
        for offset,control in ((4,'snapshot.capture'),(17,'snapshot.cancel')):
            self.now=BASE+offset;self.native.field=control
            owner.reserve(control,controls.project(self.normal.capture()));owner.send()
        _native,before,work,finished,after=capture_fixture.SnapshotCaptureTests().cancellation()
        last=self.manifest(2,BASE+50)
        return owner,before,work,finished,after,first,last

    def derive(self,args):
        owner,before,work,finished,after,first,last=args
        return pending(owner,1,2,before,work,finished,after,first,last,'qrc:/scripts/')

    def test_actual_durable_normal_inputs_and_clocked_original_files_join_pending_cancellation(self):
        with self.fixture.lock.held():
            args=self.prepared();result=self.derive(args)
            self.assertEqual('snap_1700000000010_1',result['captureId'])
            self.assertTrue(result['quietWindowRequired']);self.assertTrue(result['independentWitnessRequired'])
            self.assertEqual(2,len([row for row in self.native.requests if row['operation']=='edit']))
            self.assertEqual(2,len(self.fixture.files.commands))
            # The entire derivation remains file-only after SDK retirement.
            def forbidden(*_args,**_kwargs):raise AssertionError('Historical cancellation touched SDK')
            self.fixture.feature.guard=self.normal._check=forbidden
            self.assertEqual(result,self.derive(args))

    def test_wrong_mode_work_begin_or_late_input_cannot_turn_ack_into_cancellation(self):
        with self.fixture.lock.held():
            owner,before,work,finished,after,first,last=self.prepared()
            for fault in ('mode','late','native-begin','missing-work'):
                values=[owner,deepcopy(before),deepcopy(work),deepcopy(finished),deepcopy(after),first,last]
                if fault=='mode':
                    for value in values[2:4]:
                        row=value['source']['workers'][0]
                        for event in row['events']:event['state']['mode']='animated'
                        row['state']['mode']=row['latest']['state']['mode']='animated'
                elif fault=='late':
                    values[2]['clockBefore']['epochMs']=BASE+3;values[2]['clockAfter']['epochMs']=BASE+4
                elif fault=='native-begin':values[4]['source']['activity']['requests']=1
                else:values[3]['source']['workers'][0]['events'].pop()
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.derive(values)

    def test_actual_original_manifest_loss_blocks_cancellation_and_never_requeries(self):
        with self.fixture.lock.held():
            args=self.prepared();last=args[-1];path=last.files().path(last.files().expand(last.state['proof']))
            path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaises(NativeUIError):self.derive(args)
            self.assertEqual(2,len(self.fixture.files.commands));self.assertEqual(2,len([row for row in self.native.requests if row['operation']=='edit']))

    def test_actual_nonempty_list_or_new_native_clock_birth_cannot_complete_old_cancellation(self):
        with self.fixture.lock.held():
            args=list(self.prepared())
            row=dict(name='parity-'+RUN[:16]+'-still-png-snap_1700000000010_1.png',size=1,revision='b'*64,sha256='c'*64)
            args[-1]=self.manifest(3,BASE+60,[row])
            with self.assertRaises(NativeUIError):self.derive(args)
            self.manifest_native=Boundary();self.manifest_birth='b'*32
            args[-1]=self.manifest(4,BASE+70)
            with self.assertRaises(NativeUIError):self.derive(args)


if __name__=='__main__':unittest.main()
