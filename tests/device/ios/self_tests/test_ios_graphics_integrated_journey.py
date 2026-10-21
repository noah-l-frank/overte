"""Unchanged fifteen Graphics steps, actual worker and paired SDK retirement.

Fixtures, private files and PNG originals are host-owned; native/OS SDKs are
models. This establishes composition, never compiled-client/device acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import threading
import time
import traceback
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import unpack
from adapters.script_feature.lock import ScriptSourceBusy
from feature_journeys.engine import Journey
from ios import graphics_observer as worker
from ios.adapters.graphics_fixture import GraphicsPhasePending
from ios.self_tests.test_ios_graphics_journey import JOURNEY_POLICY
from ios.self_tests.test_ios_graphics_scene import RUN
from ios.self_tests.test_ios_graphics_session_retirement import GraphicsSessionHarness


def diagnose(error):
    seen=set()
    while error is not None and id(error) not in seen:
        seen.add(id(error));traceback.print_exception(type(error),error,error.__traceback__,chain=False)
        error=error.__context__


class GraphicsIntegratedJourneyTests(GraphicsSessionHarness,unittest.TestCase):
    def feature(self,role='primary'):
        flow=super().feature(role);flow.policy=deepcopy(JOURNEY_POLICY);return flow

    def sleep_actor(self,seconds):
        # The actual worker alone owns actor sources; this sleep merely lets
        # its thread progress while the primary waits for paired observations.
        self.sdk.sleep(seconds)

    def test_all_steps_with_actual_worker_paired_finalizer_sdk_deletion_and_historical_repeat(self):
        stopped=threading.Event();finalizing=threading.Event();errors=[];results=[];reports=[]
        demand=threading.Condition();requested=[0];finished=[0];actor=self.feature('actor')
        original_sleep=self.sdk.sleep
        def native_sleep(seconds):original_sleep(seconds);time.sleep(.03)
        self.sdk.sleep=native_sleep
        config=dict(fixtureUrl=self.client.url,artifactRoot=str(actor.root),imagePolicy=actor.policy,durationSeconds=1800)
        original_publish=actor.publish
        def publish():
            try:value=original_publish()
            except (GraphicsPhasePending,ScriptSourceBusy):raise
            except Exception as error:diagnose(error);raise
            with demand:finished[0]=requested[0];demand.notify_all()
            return value
        actor.publish=publish
        def worker_sleep(_seconds):
            # Schedule source acquisition only; no primary measurement, state
            # or expected effect crosses to the worker. The public worker's
            # actual source reads/retirement decisions remain unchanged.
            while not stopped.is_set():
                if finalizing.is_set():time.sleep(.03);return
                try:
                    with actor.lock.held():
                        if actor.retirement_store.read() is not None:return
                        state=actor.control()
                        with demand:due=requested[0]>finished[0]
                        if state is None:return
                        if state['phase']=='restart-observing':due=state['restartRejoined']['actor'] is None
                        if state['phase']=='restart-barrier':
                            item=state['restartBarrier']['roles']['actor'];due=item is None or item['phase']!='observed'
                        if state['phase']=='calibrating':
                            value=PrivateFeatureState(self.root/'ios-graphics-calibration.json').read()
                            round_=None if value is None else unpack(value['payload'])[0]['rounds'][-1]
                            due=(round_ is not None and round_['ordinal']==state['calibration']['ordinal']
                                 and round_['phase']=='off' and round_['roles']['actor'] is None)
                        if due:return
                except ScriptSourceBusy:pass
                time.sleep(.03)
            raise RuntimeError('Owned host worker was interrupted')
        def independent():
            try:
                results.append(worker.run_flow(config,actor.store.read,actor.retirement_store.read,lambda run:actor,
                    monotonic=time.monotonic,sleep=worker_sleep))
            except Exception as error:diagnose(error);errors.append(error)
            finally:
                print('GRAPHICS_INTEGRATED_HOST_WORKER_EXIT',results,flush=True)
                stopped.set()
                with demand:demand.notify_all()
        thread=threading.Thread(target=independent,daemon=True);thread.start()
        def checked():
            if errors:raise AssertionError('Independent Graphics worker failed') from errors[0]
            self.assertFalse(worker.failure(actor,config),'Original actor failure cannot become green')
        def invoke(operation,values):
            checked()
            try:return getattr(self.feature(),operation.rsplit('.',1)[1])(values)
            except Exception as error:diagnose(error);raise
        def peer():
            checked()
            with demand:
                requested[0]+=1;target=requested[0];until=time.monotonic()+20
                while finished[0]<target and not errors and time.monotonic()<until:demand.wait(.05)
            checked();return self.client.observe()
        def activate(ticket,verb='baseline',inputs=None):
            self.client.activate(ticket,verb,inputs);self.gpu.marker=ticket
            print('GRAPHICS_INTEGRATED_HOST_PHASE',verb,flush=True)
        journey=Journey('graphics',RUN,self.client.url+'/runs/'+RUN+'/',invoke=invoke,witness=peer,activate=activate,
            read_artifact=lambda name:(self.root/'pixels'/name).read_bytes(),image_policy={'screen':JOURNEY_POLICY},
            continuity=lambda *_:checked(),monotonic=lambda:self.sdk.clock,epoch_ms=self.sdk.host_epoch,
            sleep=self.sdk.sleep,report=reports.append)
        try:
            journey.execute();checked()
            self.assertTrue(reports[-1]['sequenceCompleted']);self.assertTrue(reports[-1]['cleanupSucceeded'])
            self.assertEqual('cleaned',self.feature().control()['phase']);self.assertTrue(thread.is_alive())
            print('GRAPHICS_INTEGRATED_HOST_OBSERVABLE_CLEANUP_COMPLETE',flush=True)
            self.client.close();finalizing.set()
            transaction=self.transaction()
            try:self.assertEqual({'cleaned':True},transaction.finalize())
            except Exception as error:diagnose(error);raise
            print('GRAPHICS_INTEGRATED_HOST_SDK_RETIRED',flush=True)
            # A finalizer step has the real 60-second contract, including pure
            # validation of both complete immutable stage histories and PNGs.
            thread.join(60);checked();self.assertEqual([0],results)
            self.assertEqual(['lifecycle.background','app.launch','app.stop','app.launch','app.stop'],self.inputs)
            self.assertEqual(43,self.sdk.pid);self.assertTrue(self.sdk_deleted)
            self.assertEqual(1,sum(method=='DELETE' for method,_ in self.sdk_calls))
            self.assertIsNone(actor.store.read());self.assertIsNone(actor.retirement_store.read())
            self.assertIsNone(self.session_store.read());self.assertIsNone(self.base._binding_store('owned').read())
            self.assertEqual({'cleaned':True},transaction.historical(transaction.receipt.read()))
        finally:
            stopped.set();finalizing.set()
            with demand:demand.notify_all()
            thread.join(60)
            self.assertFalse(thread.is_alive(),'Owned independent worker did not drain')


if __name__=='__main__':unittest.main()
