"""Actual shared cleanup dispatch over an explicit synthetic phase producer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import threading
import time
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from feature_journeys.scenarios import SCENARIOS,VERSION
from feature_journeys.witness import Client
from feature_journeys.server import make_server
from feature_journeys.phase_fixture import PhaseFixtureReader
from adapters.feature_fixture_access import AdapterFixtureClient
from overte_phone_feature_dispatch import invoke

RUN='a'*32


class Boundary:
    def __init__(self,area,active):
        self.area,self.active=area,active;self.calls=[];self.requests=[];self.fault=None;self.failure=None
        self.client=Client('http://127.0.0.1:1/feature-fixture/v1','a'*64)
        self.client.request=self.request

    def request(self,path,*,phase_nonce):
        self.requests.append((path,phase_nonce));epoch=int(time.time()*1000)
        value=dict(fixturePhaseVersion=1,instance='b'*32,sequence=1,requestId=phase_nonce,runId=RUN,area=self.area,
            capturedEpochMs=epoch,active=self.active,createdEpochMs=epoch-10000,
            retiredEpochMs=None if self.active else epoch-100,
            activations=[dict(sequence=1,ticket='c'*32,activatedEpochMs=epoch-500,
                stimulus=dict(verb='cleanup',inputs={}))])
        if self.fault:self.fault(value)
        return deepcopy(value)

    def factory(self,retired):
        self.calls.append(('owner',retired));boundary=self
        class Owner:
            def cleanup(self,fields):
                boundary.calls.append(('cleanup',fields));return {'performed':True}
            def finalize(self):
                boundary.calls.append(('finalize',None))
                if boundary.failure:raise boundary.failure
                # The real owners have much stronger original evidence. This
                # seam ensures dispatch cannot treat routing metadata as proof.
                if boundary.active:raise ValueError('Provider became active before finalization')
            def observe(self,fields):raise AssertionError('Unused observation seam')
        return Owner()

    def cleanup(self):return invoke('feature.'+self.area+'.cleanup',dict(contractVersion=VERSION,runId=RUN),self.factory,lambda:self.client)


class FeatureDispatchTests(unittest.TestCase):
    def test_all_14_active_phases_keep_normal_cleanup_and_closed_phases_require_full_finalization(self):
        self.assertEqual(14,len(SCENARIOS))
        for area in SCENARIOS:
            for active in (True,False):
                with self.subTest(area=area,active=active):
                    b=Boundary(area,active);self.assertEqual({'performed':True},b.cleanup())
                    self.assertEqual(('owner',not active),b.calls[0])
                    self.assertEqual('cleanup' if active else 'finalize',b.calls[1][0]);self.assertEqual(2,len(b.calls))
                    self.assertEqual('/runs/'+RUN+'/phase',b.requests[0][0]);self.assertEqual(32,len(b.requests[0][1]))

    def test_missing_stale_foreign_or_incomplete_closure_never_reaches_an_owner(self):
        for fault in ('nonce','run','area','old','version','missing','closure','desired'):
            with self.subTest(fault=fault):
                b=Boundary('snapshots',False)
                def mutate(row):
                    if fault=='nonce':row['requestId']='d'*32
                    elif fault=='run':row['runId']='d'*32
                    elif fault=='area':row['area']='audio'
                    elif fault=='old':row['capturedEpochMs']-=5000
                    elif fault=='version':row['fixturePhaseVersion']=True
                    elif fault=='missing':row.pop('retiredEpochMs')
                    elif fault=='closure':row['retiredEpochMs']=None
                    else:row['expectedRetired']=True
                b.fault=mutate
                with self.assertRaises((RuntimeError,ValueError)):b.cleanup()
                self.assertEqual([],b.calls)

    def test_unfinished_files_native_work_or_actor_termination_cannot_be_hidden_by_closure(self):
        for failure in ('Original files remain','Actor has not terminated','Native work returned','Originals replaced'):
            with self.subTest(failure=failure):
                b=Boundary('snapshots',False);b.failure=ValueError(failure)
                with self.assertRaisesRegex(ValueError,failure):b.cleanup()
                self.assertEqual(['owner','finalize'],[row[0] for row in b.calls])

    def test_lost_finalization_ack_is_not_automatically_replayed(self):
        b=Boundary('snapshots',False);b.failure=OSError('Lost original retirement response')
        with self.assertRaises(OSError):b.cleanup()
        self.assertEqual(1,len(b.requests));self.assertEqual(1,len([row for row in b.calls if row[0]=='finalize']))

    def test_requested_foreign_or_unversioned_cleanup_is_rejected_before_provider_access(self):
        b=Boundary('snapshots',False)
        for values in (dict(contractVersion=True,runId=RUN),dict(contractVersion=17,runId=RUN),dict(contractVersion=VERSION,runId='foreign'),
                dict(contractVersion=VERSION,runId=RUN,expectedRetired=True)):
            with self.subTest(values=values),self.assertRaises((RuntimeError,ValueError)):
                invoke('feature.snapshots.cleanup',values,b.factory,lambda:b.client)
        self.assertEqual([],b.requests);self.assertEqual([],b.calls)

    def test_actual_loopback_provider_and_separate_adapter_credential_select_closed_phase_for_all_14_areas(self):
        server=make_server('r'*64,'a'*64,adapter_token='d'*64)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url='http://127.0.0.1:'+str(server.server_address[1])+'/feature-fixture/v1'
        try:
            for area in SCENARIOS:
                with self.subTest(area=area):
                    # This is the actual phase authority, not a full account,
                    # navigation or social provider qualification. Provision
                    # its input journal directly; acquire it over real HTTP.
                    run=server.journal.register(area);server.journal.activate(run,'e'*32)
                    adapter=AdapterFixtureClient(url,'d'*64);calls=[]
                    class Owner:
                        def cleanup(self,fields):calls.append('cleanup');return {'performed':True}
                        def finalize(self):
                            # The independent source is reacquired here. Real
                            # Phone owners also require native/actor/file proof;
                            # this test exercises only actual HTTP phase routing.
                            actual=PhaseFixtureReader(adapter,run,area).status()
                            if actual['active']:raise ValueError('Original provider is still active')
                            calls.append('finalize')
                    def factory(retired):calls.append(retired);return Owner()
                    operation='feature.'+area+'.cleanup';fields=dict(contractVersion=VERSION,runId=run)
                    invoke(operation,fields,factory,lambda:adapter)
                    self.assertEqual([False,'cleanup'],calls)
                    server.journal.close(run);invoke(operation,fields,factory,lambda:adapter)
                    self.assertEqual([False,'cleanup',True,'finalize'],calls)
            self.assertEqual(0,server.internal_errors)
        finally:
            server.shutdown();server.server_close();thread.join(3)
            self.assertFalse(thread.is_alive())


if __name__=='__main__':unittest.main()
