"""Existing-SDK lifecycle over real native adapter methods and HTTP transport.

The OS/native lifecycle producer is explicitly modeled. Real IOSNativeMixin
and AppiumAdapter methods perform the ordinary background, activation and
termination calls. This selector fixture does not qualify InstalledAdapter's
outer candidate/bundle re-verification or native/device execution.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters import appium_adapter
from ios.adapters.adapter import IOSNativeMixin
from ios.adapters.feature_observation import FeatureObservation
from ios.adapters.tablet_web_runtime import IOSTabletWebRuntime
from ios.self_tests.tablet_web_paired_fixture import ExistingAdapter,PairedTabletFixture,SELECTOR


class TabletLifecycleModel:
    OPERATIONS={'mobile: queryAppState','mobile: backgroundApp','mobile: activateApp','mobile: terminateApp'}
    def __init__(self,boundary):
        self.b=boundary;self.running=True;self.foreground=True;self.calls=[]
        self.ignore_background=False;self.lose_return=None
        self.counts=dict(backgrounds=0,activations=1,launches=1)
        previous=boundary.native.mutate
        def captured(value):
            previous(value);value['lifecycle']=deepcopy(self.counts)
        boundary.native.mutate=captured
        boundary.lifecycle=self;boundary.process=self.process
    def process(self):
        return dict(bundleId=self.b.target['appId'],pid=42,foreground=self.foreground) if self.running else None
    def handles(self,operation):return operation in self.OPERATIONS
    def execute(self,operation,arguments):
        need(self.handles(operation));self.calls.append((operation,deepcopy(arguments)))
        if operation=='mobile: queryAppState':
            need(arguments==dict(bundleId=self.b.target['appId']))
            return 4 if self.running and self.foreground else 3 if self.running else 1
        need(self.running)
        if operation=='mobile: backgroundApp':
            need(arguments==dict(seconds=-1) and self.foreground)
            if not self.ignore_background:
                self.foreground=False;self.counts['backgrounds']+=1;self.b.suspend_native()
        elif operation=='mobile: activateApp':
            need(arguments==dict(bundleId=self.b.target['appId']))
            if not self.foreground:
                self.foreground=True;self.counts['activations']+=1;self.b.resume_native()
        elif operation=='mobile: terminateApp':
            need(arguments==dict(bundleId=self.b.target['appId']));self.running=False;self.foreground=False
        self.b.sleep(.002)
        if self.lose_return==operation:
            self.lose_return=None;raise OSError('Actual modeled OS command return lost after delivery')
        return None


class ExistingLifecycleAdapter(ExistingAdapter,IOSNativeMixin,appium_adapter.AppiumAdapter):
    """No ensure/create fallback; immutable prepared selector is test input."""
    platform='ios'
    def __init__(self,root,metadata):
        ExistingAdapter.__init__(self,root,metadata);self._operation=None;self._session_recreation_forbidden=False
    def target(self,selector):return self._target(selector)
    def ensure_session(self,selector):
        client,session,state,_target,_scope=IOSTabletWebRuntime(self)._existing(selector)
        return client,session,state
    def save_session(self,selector,state):
        previous=self.read_session(selector);self._scope(selector,state['sessionId'],previous,self._target(selector))
        need(all(state.get(key)==previous.get(key) for key in ('sessionId','generation','targetFingerprint')))
        PrivateFeatureState(self.state_path(selector)).write(state,previous)
    def _binding_store(self,selector):
        need(selector==SELECTOR);return PrivateFeatureState(self.metadata['installedPath'])
    def _binding(self,selector,client,session,state,target):
        gate=super()._binding(selector,client,session,state,target)
        observer=FeatureObservation(client,session,target,lambda:self.native_process(client,session,target))
        gate.native_bundle=lambda:observer.installed_bundle().read()
        return gate
    def _retired_candidate_scope(self,selector,scope):
        self._candidate_guard();need(scope==self.metadata['scope']);return self._target(selector)
    def invoke(self,selector,operation,values):
        need(operation in ('lifecycle.background','app.launch','app.stop') and values=={} and self._operation is None)
        self._candidate_guard();client,session,state,target,_scope=IOSTabletWebRuntime(self)._existing(selector)
        gate=self._binding(selector,client,session,state,target)
        if operation=='app.stop':gate.begin_retirement()
        else:gate.continuity(allow_background=True)
        self._operation=operation
        try:
            result=IOSNativeMixin.invoke(self,selector,operation,values)
            if operation=='app.stop':gate.finish_retirement()
            else:gate.continuity(allow_background=operation=='lifecycle.background')
            self._candidate_guard();return result
        finally:self._operation=None


def attach(fixture,*,model_type=TabletLifecycleModel):
    """Configure existing launch inputs before any new observer is acquired."""
    b=fixture.boundary;model=model_type(b)
    b.target['testBuild']['scenePath']='/owned-scene.json'
    state=fixture.session
    state.update(processIdentity='42',iosE2ELaunchCompleted=True,
        iosE2ESceneUrl=b.target['testBuild']['fixtureOrigin']+'/owned-scene.json')
    store=PrivateFeatureState(b.root/'session.json');store.write(state,store.read())
    fixture.metadata['target']=deepcopy(b.target);fixture.metadata['session']=deepcopy(state)
    store=PrivateFeatureState(b.root/'paired-input-metadata.json');store.write(fixture.metadata,store.read())
    fixture.primary.runtime.adapter=ExistingLifecycleAdapter(b.root,fixture.metadata)
    return model


class LifecyclePairedTabletFixture(PairedTabletFixture):
    def __init__(self,test):
        super().__init__(test);self.lifecycle=attach(self)
