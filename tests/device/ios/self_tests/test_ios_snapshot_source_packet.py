"""Actual immutable source files over explicitly modeled native SDK/clock seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json
import os
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import feature_observation,snapshot_source_packet as source
from ios.self_tests import test_ios_snapshot_owned_packet as owned_fixture
from ios.self_tests import test_ios_snapshot_work as work_fixture
from ios.self_tests import test_ios_snapshot_captures as capture_fixture
from ios.self_tests import test_ios_snapshot_exports as export_fixture
from ios.self_tests import test_ios_snapshot_inputs as input_fixture


class SnapshotSourcePackets(unittest.TestCase):
    def setUp(self):
        self.f=owned_fixture.SnapshotOwnedPackets();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.component='work';self.counter=0;self.calls=[];self.raw=None;self.lost=False
        self.f.transport.execute=self.execute
        actual=patch.object(feature_observation,'post_request',self.post);actual.start();self.addCleanup(actual.stop)

    def producer(self,component):
        self.component=component;self.counter=0
        self.native=(capture_fixture.Native() if component=='captures' else export_fixture.Native() if component=='exports'
            else input_fixture.Native() if component=='inputs' else None)
        self.f.model.now=work_fixture.EPOCH-1 if self.native is None else self.native.epoch if component=='inputs' else self.native.now

    def packet(self,q):
        if self.component=='work':
            value=work_fixture.packet();value.update(sequence=self.counter,requestId=q['commandId'])
            for key,offset in (('clockBefore',0),('clockAfter',1)):
                value[key]=dict(epochMs=self.f.model.now+1+offset,monotonicMs=1+self.counter*10+offset)
        elif self.component=='captures':
            value=self.native.read();value['requestId']=q['commandId']
        else:
            self.native.send(q);value=deepcopy(self.native.packet)
        self.f.model.now=value['clockAfter']['epochMs'];return value

    def post(self,request,timeout):
        q=self.f.transport.fixture.set_client_command(json.loads(request.data));self.calls.append(q);self.counter+=1
        self.f.transport.echo=json.dumps(q).encode();self.raw=json.dumps(self.packet(q),indent=1)+'\n'
        if self.lost:raise OSError('Actual source publication completed but HTTP result was lost')
        return self.f.transport

    def execute(self,session,operation,args):
        self.assertEqual('mobile: pullFile',operation)
        self.assertTrue(args['remotePath'].endswith('/'+source.PACKETS[self.component]._source.FILE))
        return base64.b64encode(self.raw.encode()).decode()

    def owner(self,index=1,*,kind=None,historical=False):
        cls=source.PACKETS[kind or self.component];f=self.f
        store=PrivateFeatureState(f.root/('ios-snapshot-primary-'+cls._name+'-'+format(index,'04d')+'.json'))
        args=(store,f.lock,f.binding,owned_fixture.RUN,'primary',index)
        if historical:return cls.history(*args)
        return cls(*args,f.feature,f.native(),lambda:True,epoch_ms=lambda:f.model.now,monotonic=lambda:(f.model.now-10000)/1000)

    def capture(self):
        owner=self.owner();owner.reserve();owner.send();return owner,owner.retain()

    def test_all_four_existing_native_DTOs_keep_original_raw_bytes_and_actual_historical_files(self):
        with self.f.lock.held():
            for component in source.PACKETS:
                with self.subTest(component=component):
                    self.producer(component);owner,frame=self.capture();self.assertEqual(self.raw,frame['raw']);owner.qualified()
                    self.assertEqual(frame,self.owner(historical=True).historical())
                    self.assertEqual(frame['packet'],json.loads(self.raw));self.assertNotIn('captureSucceeded',frame)
                    self.assertIn('snapshot-'+component+'-source-parts',str(owner.parts().store.path(owner.state['rawParts']['chunks'][0])))
            self.assertEqual(4,len(self.calls))

    def test_held_real_native_capture_and_export_owner_remain_live_observations_not_retired_effects(self):
        with self.f.lock.held():
            self.producer('captures');capture,_=self.native.begin();owner,frame=self.capture()
            self.assertTrue(frame['packet']['source']['captures'][0]['alive']);owner.qualified()
            with self.assertRaises(NativeUIError):capture_fixture.source.drained(frame['packet'])
            self.producer('exports');operation=self.native.start();owner,frame=self.capture()
            self.assertTrue(frame['packet']['source']['operations'][0]['alive']);owner.qualified()
            self.assertIsNotNone(capture);self.assertIsNotNone(operation)

    def test_lost_send_result_and_late_original_are_never_reissued_or_retimed(self):
        with self.f.lock.held():
            self.producer('captures');owner=self.owner();owner.reserve();self.lost=True
            with self.assertRaises((NativeUIError,OSError)):owner.send()
            actual=self.raw;self.f.model.now+=2000;rebuilt=self.owner();frame=rebuilt.retain()
            self.assertEqual(actual,frame['raw']);self.assertEqual(1,len(self.calls))
            with self.assertRaises(NativeUIError):rebuilt.qualified()
            self.assertEqual(frame,self.owner(historical=True).historical())
            with self.assertRaises(NativeUIError):rebuilt.send()

    def test_complete_opened_actual_source_parts_recover_without_AFC_query_or_inode_rewrite(self):
        with self.f.lock.held():
            self.producer('work');owner=self.owner();owner.reserve();owner.send();fsync=os.fsync
            def lost(fd):
                if 'snapshot-work-source-parts-frame-' in os.readlink('/proc/self/fd/'+str(fd)):raise OSError('Actual complete raw flush return lost')
                return fsync(fd)
            with patch('os.fsync',side_effect=lost),self.assertRaises(OSError):owner.retain()
            rebuilt=self.owner();path=rebuilt.parts().store.path(rebuilt.state['rawParts']['chunks'][0]);before=path.stat();raw=path.read_bytes()
            def forbidden(*_a,**_k):raise AssertionError('Repeated original source acquisition')
            rebuilt.feature.original=forbidden;frame=rebuilt.retain()
            self.assertEqual(self.raw,frame['raw']);self.assertEqual(raw,path.read_bytes());self.assertEqual(before,path.stat());self.assertEqual(1,len(self.calls))

    def test_component_query_role_and_actual_part_inode_cannot_be_relabelled(self):
        with self.f.lock.held():
            self.producer('captures');owner,frame=self.capture()
            wrong=deepcopy(frame['query']);wrong['action']=source.PACKETS['work']._source.ACTION
            other=self.owner(kind='work')
            with self.assertRaises(NativeUIError):other.parent(owner.state['rawParts'],wrong)
            path=owner.parts().store.path(owner.state['rawParts']['chunks'][0]);raw=path.read_bytes();before=path.stat();path.rename(path.with_suffix('.retained'));path.write_bytes(raw);path.chmod(0o600)
            self.assertNotEqual(before.st_ino,path.stat().st_ino)
            with self.assertRaises(NativeUIError):self.owner(historical=True)

    def test_historical_source_decoder_has_no_SDK_guard_clock_or_mutation_authority(self):
        with self.f.lock.held():
            self.producer('inputs');owner,frame=self.capture()
            def forbidden(*_a,**_k):raise AssertionError('Historical source attempted SDK access')
            self.f.feature.guard=self.f.feature.original=self.f.native=forbidden
            historical=self.owner(historical=True);self.assertEqual(frame,historical.historical())
            for action in (historical.reserve,historical.send,historical.retain):
                with self.assertRaises(NativeUIError):action()
            self.assertEqual(1,len(self.calls))


if __name__=='__main__':unittest.main()
