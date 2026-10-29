"""Actual public/common/rooted Emote graph over declared host producers.

Node/JS, W3C inputs, UDP, HTTP, PNG, original files and end owners are actual.
Native/Qt/GPU/OS producers, installed target and release preflight are models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
from pathlib import Path
import json
import os
import threading
import traceback
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.engine import Journey
from feature_journeys.terminal import PROFILE
from feature_journeys.witness import Client
from ios import emote_observer
from ios.adapters import feature_configuration
from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
from ios.adapters.emote_runtime import IOSEmoteRuntime
from ios.self_tests.emote_rooted_whole_end_fixture import WholeRootedEndFixture


class ScheduledEmoteActor:
    """Original worker iterations run only outside the Primary SDK lease."""
    def __init__(self,flow,configuration,clock,report):
        self.flow,self.configuration,self.clock,self.report=flow,configuration,clock,report
        self.condition=threading.Condition();self.requested=self.completed=0
        self.cancelled=False;self.result=None;self.error=None
        self.thread=threading.Thread(target=self.work,name='emote-public-actor',daemon=True);self.thread.start()
    def wait(self):
        with self.condition:
            self.condition.wait_for(lambda:self.cancelled or self.requested>self.completed)
            if self.cancelled:raise RuntimeError('Declared host worker schedule cancelled')
    def pause(self,_seconds):
        with self.condition:self.completed+=1;self.condition.notify_all()
        self.wait()
    def work(self):
        try:
            self.wait()
            self.result=emote_observer.run_flow(self.flow,self.configuration,monotonic=self.clock,sleep=self.pause)
        except BaseException as error:
            self.error=error;self.report(dict(event='uncaught-worker-exception',exceptionType=type(error).__name__,traceback=''.join(traceback.format_exception(error))))
        finally:
            self.report(dict(event='actual-worker-return',returnCode=self.result,uncaughtExceptionType=None if self.error is None else type(self.error).__name__))
            with self.condition:self.condition.notify_all()
    def cycle(self):
        with self.condition:
            need(self.error is None and self.result is None and self.requested==self.completed)
            self.requested+=1;wanted=self.requested;self.condition.notify_all()
            # The original worker publish ceiling is60s. This scheduler wait
            # neither changes that budget nor advances native/model time.
            need(self.condition.wait_for(lambda:self.completed>=wanted or self.error is not None or self.result is not None,timeout=65))
            if self.error is not None:raise self.error
            need(self.completed==wanted and self.result is None)
    def finish(self):
        with self.condition:
            need(self.error is None and self.result is None and self.requested==self.completed)
            self.requested+=1;self.condition.notify_all()
        self.thread.join(timeout=65);need(not self.thread.is_alive())
        if self.error is not None:raise self.error
        need(self.result==0)
    def close(self):
        with self.condition:self.cancelled=True;self.condition.notify_all()
        self.thread.join(timeout=65);need(not self.thread.is_alive())


class PublicEmoteVertical:
    def __init__(self,test):
        from ios.self_tests.emote_animation_fixture import bundled_frames
        from ios.self_tests import emote_script_vm_fixture as vm
        from ios.self_tests import emote_active_observer_fixture as native_fixture
        frames=bundled_frames()
        # Select the declared Rig curve before its first native capture.
        # Loaded clip duration comes from the original ordinary JS request.
        with (patch.object(vm,'ActualEmoteVM',partial(vm.ActualEmoteVM,frame_counts=frames)),
              patch.object(native_fixture,'ActualVMRig',partial(native_fixture.ActualVMRig,pose_profile='requested-clip'))):
            self.end=WholeRootedEndFixture(test,retain_originals=True,normal_scripts_profile=True)
        self.normal=self.end.normal;self.adapter=self.end.base;self.runtime=self.end.runtime
        self.domain=self.normal.target.domain;self.root=self.end.root
        self.calls=[];self.factories=[];self.reports=[];self.worker_events=[];self.worker=None
        self.reader=Client(self.normal.target.client.url,'r'*64)
        self.configuration_path=self.root/'public-feature-configuration.json';access=self.root/'public-fixture-reader.json'
        PrivateFeatureState(access).write(dict(fixtureAdapterAccessVersion=1,fixtureUrl=self.normal.target.client.url,adapterToken='d'*64),None)
        self.configuration=dict(iosFeatureAdapterVersion=8,areas=['emotes'],fixtureConfig=str(access),
            graphics=None,create=None,emotes=dict(artifactRoot=str(self.normal.flow.root),imagePolicy=deepcopy(self.normal.flow.policy),actorTarget='actor'),
            worldNavigation=None,avatarPeople=None,worldWeb=None,tabletWeb=None,emoteCoordinatorVersion=2,worldWebCoordinatorVersion=None)
        self.configuration['emoteTargets']=dict(primaryTarget='primary',actorTarget='actor',
            primaryArtifactRoot=str(self.normal.flow.root),actorArtifactRoot=str(self.normal.actor.flow.root))
        PrivateFeatureState(self.configuration_path).write(self.configuration,None)
        test.enterContext(patch.dict(os.environ,OVERTE_IOS_FEATURE_ADAPTER_CONFIG=str(self.configuration_path)))
        need(feature_configuration.VERSION==8)
        self.flows={}
        for role,item in self.end.roles.items():
            # The old single-thread fixture must never run hidden direct peer
            # operations. All independent work below uses the actual worker.
            item.flow.sleep=item.target.domain.sleep
            self.flows[role]=self.make_flow(role,item.flow.client)
        self.primary,self.actor=self.flows['primary'],self.flows['actor']
        def factory(runtime,selector,run,*,role,client,settings,target_pair=None):
            need(runtime.adapter is self.adapter and selector==role and run==self.primary.run)
            from ios.adapters.emote_configuration import settings as validate
            expected=dict(artifactRoot=str(self.flows[role].root),imagePolicy=self.flows[role].policy,
                **({'actorTarget':'actor'} if role=='primary' else {'primaryTarget':'primary'}))
            need(validate(settings,role=role,target=selector)==expected and client.url==self.primary.client.url
                and target_pair==self.configuration['emoteTargets'])
            self.factories.append((selector,run,role))
            # A fresh exact product Flow owns the ACTUAL configured adapter
            # reader, just as the normal production factory does. Existing
            # typed children are only the declared producer assembly seam.
            flow=self.make_flow(role,client);self.flows[role]=flow
            if role=='primary':self.primary=flow;flow.sleep=self.primary_sleep
            return flow
        test.enterContext(patch.object(IOSEmoteRuntime,'_emote_rooted_feature',factory))
        actual_step=emote_observer.rooted_step
        def observed_step(flow,configuration):
            try:return actual_step(flow,configuration)
            except BaseException as error:
                if flow is self.actor:self.record_worker(dict(event='actual-step-exception',exceptionType=type(error).__name__,traceback=''.join(traceback.format_exception(error))))
                raise
        test.enterContext(patch.object(emote_observer,'rooted_step',observed_step))
        config=dict(iosEmoteObserverVersion=3,targetPair=deepcopy(self.configuration['emoteTargets']),target='actor',primaryTarget='primary',runId=self.primary.run,
            durationSeconds=1800,artifactRoot=str(self.actor.root),imagePolicy=self.actor.policy,
            primaryArtifactRoot=str(self.primary.root),primaryImagePolicy=self.primary.policy)
        self.worker=ScheduledEmoteActor(self.actor,config,self.primary.monotonic,self.record_worker);test.addCleanup(self.worker.close)
        self.primary.sleep=self.primary_sleep
        # Prepare the actual source before the shared runner selects its fresh
        # baseline ticket, as the established common fixture already does.
        self.invoke('feature.emotes.observe',dict(contractVersion=16,runId=self.primary.run,afterSequence=0))
        self.journey=Journey('emotes',self.primary.run,self.primary.phase.fixture_url,
            invoke=self.invoke,witness=self.witness,activate=self.activate,read_artifact=self.read_artifact,
            image_policy=dict(screen=deepcopy(self.primary.policy)),continuity=self.continuity,
            monotonic=self.primary.monotonic,epoch_ms=self.primary.epoch_ms,sleep=self.domain.sleep,
            report=self.reports.append,terminal_profile=PROFILE,retire_fixture=self.retire)
    def make_flow(self,role,client):
        item=self.end.roles[role];old=item.flow
        flow=IOSEmoteRootedFeature(self.runtime,role,client,old.run,role,old.root,old.policy,
            actor_selector='actor' if role=='primary' else None,primary_selector='primary' if role=='actor' else None,
            epoch_ms=old.epoch_ms,monotonic=old.monotonic,sleep=item.target.domain.sleep,target_pair=self.configuration['emoteTargets'])
        flow.lock=old.lock;flow.primary_lock=self.normal.flow.lock
        def components():
            own,primary=flow.bindings()
            need(flow.state is not None and flow.state['phaseInstance']==flow.phase.previous['instance'])
            parts=item.parts
            need(parts['sources'].binding==primary['binding'] and parts['scope'].binding==own['binding']
                and parts['scope'].lock is flow.lock and parts['observer'].binding==own['binding'])
            own['check']();primary['check']();return parts
        # Same genuine typed assembly as WholePrimary/ActorFixture. No method
        # providing observations, effects, publications or end facts is patched.
        flow.components=components
        return flow
    def record_worker(self,event):
        # This metadata root is outside both product original roots and the
        # immutable candidate tree. No generic locals/config dump is captured.
        self.worker_events.append(deepcopy(event))
        with (self.root/'actual-emote-worker-events.json').open('w') as stream:
            json.dump(self.worker_events,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    def primary_sleep(self,seconds):
        if self.primary.lock._owner is None and self.primary.primary_lock._owner is None:
            if self.primary.phase.status()['active']:self.worker.cycle()
        self.domain.sleep(seconds)
    def activate(self,ticket,verb='baseline',inputs=None):
        self.normal.target.ticket=ticket;self.normal.target.server.journal.activate(self.primary.run,ticket,verb,inputs)
        for item in self.end.roles.values():
            scope=item.parts['scope']
            if scope.previous is None and not scope.frames:scope.ticket=ticket
    def invoke(self,operation,values):
        self.calls.append((operation,deepcopy(values)))
        result=self.adapter.invoke('primary',operation,values);need(self.adapter._operation is None)
        if operation in ('feature.emotes.act','feature.emotes.observe'):self.worker.cycle()
        if operation=='feature.emotes.terminal' and values['stage']=='finish':self.worker.finish()
        return result
    def witness(self):return self.reader.request('/runs/'+self.primary.run)
    def continuity(self,_stage,_verb):need(self.runtime._sources('primary')['check']() is not False)
    def read_artifact(self,name):
        from feature_journeys.evidence import read_private_artifact
        return read_private_artifact(self.primary.root,name)
    def retire(self):return self.reader.request('/runs/'+self.primary.run,method='DELETE')
