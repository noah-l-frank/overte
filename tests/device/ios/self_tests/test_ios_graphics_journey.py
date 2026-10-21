"""Unchanged shared Graphics steps with a separate synthetic SDK actor thread.

No device, simulator, compiler, Appium server or laboratory is invoked. Both
roles read original test SDK packets through real private files/loopback HTTP.
Final native/process retirement is a separate unfinished integration boundary.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import threading
import time
import traceback
import unittest

from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import unpack
from adapters.script_feature.lock import ScriptSourceBusy
from feature_journeys.engine import Journey
from ios.adapters.graphics_fixture import GraphicsPhasePending
from ios.self_tests.test_ios_graphics_feature import FeatureHarness
from ios.self_tests.test_ios_graphics_scene import RUN
from ios.self_tests.test_ios_graphics_samples import POLICY


# Fixed native-frame band through the actual fog-board and reflector interiors.
# The unused lower floor cannot dominate their shared 5% change assertion.
JOURNEY_POLICY=dict(POLICY,subject=[250,175,550,225])


class GraphicsJourneyTests(FeatureHarness,unittest.TestCase):
    def feature(self,role='primary'):
        flow=super().feature(role);flow.policy=deepcopy(JOURNEY_POLICY);return flow
    def test_all_shared_steps_keep_normal_inputs_independent_actors_and_original_cleanup(self):
        stopped=threading.Event();errors=[];actor=self.feature('actor');reports=[]
        demand=threading.Condition();requested=[0];finished=[0]
        original_sleep=self.sdk.sleep
        def native_sleep(seconds):
            original_sleep(seconds);time.sleep(.03)
        self.sdk.sleep=native_sleep
        def worker():
            while not stopped.is_set():
                try:
                    with actor.lock.held():
                        state=actor.control()
                        with demand:due=requested[0]>finished[0]
                        if state is not None and state['phase']=='restart-observing':due=state['restartRejoined']['actor'] is None
                        if state is not None and state['phase']=='restart-barrier':
                            item=state['restartBarrier']['roles']['actor'];due=item is None or item['phase']!='observed'
                        if state is not None and state['phase']=='calibrating':
                            value=PrivateFeatureState(self.root/'ios-graphics-calibration.json').read()
                            round_=None if value is None else unpack(value['payload'])[0]['rounds'][-1]
                            due=(round_ is not None and round_['ordinal']==state['calibration']['ordinal']
                                 and round_['phase']=='off' and round_['roles']['actor'] is None)
                    if state is not None:
                        if due:
                            try:
                                actor.publish()
                                with demand:finished[0]=requested[0];demand.notify_all()
                            except (GraphicsPhasePending,ScriptSourceBusy):pass
                except ScriptSourceBusy:pass
                except Exception as error:
                    errors.append(error);stopped.set()
                    with demand:demand.notify_all()
                    return
                time.sleep(.03)
        thread=threading.Thread(target=worker,daemon=True);thread.start()
        def checked():
            if errors:
                error=errors[0];seen=set()
                while error is not None and id(error) not in seen:
                    seen.add(id(error));traceback.print_exception(type(error),error,error.__traceback__,chain=False)
                    error=error.__context__
                self.fail('Independent original Graphics SDK actor failed')
        def invoke(operation,values):
            checked();flow=self.feature()
            try:return getattr(flow,operation.rsplit('.',1)[1])(values)
            except Exception as error:
                if errors:checked()
                seen=set()
                while error is not None and id(error) not in seen:
                    seen.add(id(error));traceback.print_exception(type(error),error,error.__traceback__,chain=False)
                    error=error.__context__
                raise
        def peer():
            checked()
            # Request only a new independent acquisition. No primary values,
            # expected facts, native packet or desired setting crosses threads.
            with demand:
                requested[0]+=1;target=requested[0];until=time.monotonic()+20
                while finished[0]<target and not errors and time.monotonic()<until:demand.wait(.05)
            checked();return self.client.observe()
        def activate(ticket,verb='baseline',inputs=None):
            self.client.activate(ticket,verb,inputs);self.gpu.marker=ticket
            print('GRAPHICS_HOST_PHASE',verb,flush=True)
        journey=Journey('graphics',RUN,self.client.url+'/runs/'+RUN+'/',invoke=invoke,witness=peer,activate=activate,
            read_artifact=lambda name:(self.root/'pixels'/name).read_bytes(),image_policy={'screen':JOURNEY_POLICY},continuity=lambda *_:checked(),
            monotonic=lambda:self.sdk.clock,epoch_ms=self.sdk.host_epoch,sleep=self.sdk.sleep,report=reports.append)
        original=deepcopy(self.sdk.model.capture())
        try:journey.execute();checked()
        finally:
            stopped.set();thread.join(20)
            self.assertFalse(thread.is_alive(),'Owned independent SDK worker did not drain')
        self.assertTrue(reports[-1]['sequenceCompleted']);self.assertTrue(reports[-1]['cleanupSucceeded'])
        self.assertEqual(['lifecycle.background','app.launch','app.stop','app.launch'],self.inputs)
        self.assertEqual(43,self.sdk.pid);self.assertEqual('cleaned',self.feature().control()['phase'])
        self.assertEqual(.6,self.sdk.model.resolution);self.assertFalse(self.sdk.model.haze);self.assertFalse(self.sdk.model.mirrors)
        self.assertIsNotNone(self.feature().store.read());self.assertFalse(errors)
        self.assertEqual(original['controls'][0]['profile'],self.sdk.model.capture()['controls'][0]['profile'])


if __name__=='__main__':unittest.main()
