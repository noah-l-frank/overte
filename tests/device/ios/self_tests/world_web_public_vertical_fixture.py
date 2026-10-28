"""Public routing and shared Journey over explicit native/Qt/GPU/OS models.

HTTP, actual Node/DOM/Script, file CAS, PNG and original decoders execute on
host only. Existing FeatureWorldWeb producers supply modeled physical sources.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import os
import json
import traceback
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys import terminal
from feature_journeys.engine import Journey
from feature_journeys.evidence import read_private_artifact
from ios import world_web_observer
from ios.adapters import appium_adapter,feature_configuration
from ios.adapters.installed_adapter import create_physical_adapter
from ios.adapters.world_web_feature import IOSWorldWebFeature
from ios.adapters.world_web_runtime import IOSWorldWebRuntime
from ios.adapters.world_web_api_clock import scope as actual_api_scope,SECONDS as ACTUAL_API_SECONDS
from ios.self_tests.world_web_feature_fixture import FeatureWorldWeb
from ios.self_tests.retained_host_roots import retain_owned_root


# Test scheduler allowance, distinct from the unchanged product API25 scope.
# Catch/failure-WAL/report/condition handoff occurs outside original step API.
SCHEDULER_MARGIN_SECONDS=10
SCHEDULER_SECONDS=ACTUAL_API_SECONDS+SCHEDULER_MARGIN_SECONDS


class ScheduledActor:
    """The actual run_flow loop waits without advancing idle model clocks."""
    def __init__(self,flow,clock,report):
        self.report=report
        self.flow,self.clock=flow,clock;self.condition=threading.Condition()
        self.requested=self.completed=0;self.cancelled=False;self.result=None;self.error=None;self.first_step_failure=None
        self.thread=threading.Thread(target=self.work,name='world-public-actor',daemon=True);self.thread.start()
    def wait_cycle(self):
        with self.condition:
            self.condition.wait_for(lambda:self.cancelled or self.requested>self.completed)
            if self.cancelled:raise RuntimeError('Declared host schedule cancelled')
    def pause(self,_delay):
        with self.condition:self.completed+=1;self.condition.notify_all()
        self.wait_cycle()
    def work(self):
        try:
            self.wait_cycle()
            self.result=world_web_observer.run_flow(self.flow,dict(durationSeconds=1800),monotonic=self.clock,sleep=self.pause)
        except BaseException as error:
            self.error=error;self.report(dict(event='uncaught-worker-exception',exceptionType=type(error).__name__,traceback=''.join(traceback.format_exception(error))))
        finally:
            self.report(dict(event='actual-worker-return',returnCode=self.result,uncaughtExceptionType=None if self.error is None else type(self.error).__name__))
            with self.condition:self.condition.notify_all()
    def remember_step_failure(self,error,traceback):
        # Test-only first failure reference; no error is delivered to Primary
        # until unchanged run_flow has finished its catch/WAL and yielded.
        with self.condition:
            if self.first_step_failure is None:self.first_step_failure=(error,traceback)
    def raise_step_failure(self,wanted):
        need(self.completed==wanted)
        if self.first_step_failure is not None:
            error,traceback=self.first_step_failure
            raise error.with_traceback(traceback)
    def cycle(self):
        with self.condition:
            need(self.result is None and self.error is None and self.requested==self.completed)
            self.requested+=1;wanted=self.requested
            self.report(dict(event='schedule-cycle-request',cycle=wanted,hostMonotonicNs=time.monotonic_ns(),
                apiLimitSeconds=ACTUAL_API_SECONDS,schedulerMarginSeconds=SCHEDULER_MARGIN_SECONDS))
            self.condition.notify_all()
            arrived=self.condition.wait_for(lambda:self.completed>=wanted or self.result is not None or self.error is not None,timeout=SCHEDULER_SECONDS)
            self.report(dict(event='schedule-cycle-arrival',cycle=wanted,hostMonotonicNs=time.monotonic_ns(),
                arrived=arrived,completed=self.completed,workerReturned=self.result is not None,workerErrored=self.error is not None))
            need(arrived)
            if self.error is not None:raise self.error
            need(self.completed==wanted)
            self.raise_step_failure(wanted)
            need(self.result is None)
    def finish(self):
        started=time.monotonic()
        with self.condition:
            need(self.requested==self.completed and self.error is None and self.result is None)
            self.requested+=1;wanted=self.requested;self.condition.notify_all()
            arrived=self.condition.wait_for(lambda:self.completed>=wanted or self.result is not None or self.error is not None,timeout=SCHEDULER_SECONDS)
            need(arrived)
            if self.error is not None:raise self.error
            if self.completed==wanted:self.raise_step_failure(wanted)
        remaining=max(0.,SCHEDULER_SECONDS-(time.monotonic()-started))
        self.thread.join(timeout=remaining);need(not self.thread.is_alive())
        if self.error is not None:raise self.error
        need(self.result==0);return self.result
    def close(self):
        with self.condition:self.cancelled=True;self.condition.notify_all()
        self.thread.join(timeout=SCHEDULER_SECONDS);need(not self.thread.is_alive())


class PublicWorldVertical:
    def __init__(self,case):
        self.stack=ExitStack();case.addCleanup(self.stack.close)
        self.f=FeatureWorldWeb();case.addCleanup(self.f.close)
        self.metadata=tempfile.TemporaryDirectory(prefix='world-public-config-');self.root=Path(self.metadata.name)
        retain_owned_root(self.metadata,expected_root=self.root);case.addCleanup(self.metadata.cleanup)
        self.artifacts=self.root/'candidate';self.artifacts.mkdir(mode=0o700)
        (self.artifacts/'declared-model.ipa').write_bytes(b'Declared installed-source model, not an installable build')
        self.worker_events=[];self.worker_events_lock=threading.Lock();self.actor_steps=0
        self.calls=[];self.native_operations=[];self.factories=[];self.reports=[];self.worker=None;self.current_primary=None
        self.targets={selector:dict(platform='ios',physical=True,appId='org.example.overte',serverUrl=self.f.url,
            artifactMode='personal-team-preinstalled',_artifactMode='personal-team-preinstalled',probe=dict(kind='ios-documents'),
            nativeUiObservation=dict(kind='uikit-documents',version=1),normalScripts=dict(contractVersion=1,profile='ios-native-qt-scripts-v1'),
            testBuild=dict(resultsDirectory='owned-results',fixtureOrigin=self.f.network.url,scenePath='/scene.json')) for selector in self.f.sdks}
        self.configuration_path=self.root/'feature-configuration.json';fixture=self.root/'fixture-reader.json'
        PrivateFeatureState(fixture).write(dict(fixtureAdapterAccessVersion=1,fixtureUrl=self.f.network.url,adapterToken='d'*64),None)
        self.configuration=dict(iosFeatureAdapterVersion=7,areas=['world-web'],fixtureConfig=str(fixture),graphics=None,create=None,
            emotes=None,worldNavigation=None,avatarPeople=None,tabletWeb=None,emoteCoordinatorVersion=None,worldWebCoordinatorVersion=1,
            worldWeb=dict(artifactRoot=str(self.f.whole.scope.root),imagePolicy=deepcopy(self.f.primary.policy),origins=deepcopy(self.f.sdk.origins),actorTarget='actor'))
        PrivateFeatureState(self.configuration_path).write(self.configuration,None)
        self.stack.enter_context(patch.dict(os.environ,OVERTE_IOS_FEATURE_ADAPTER_CONFIG=str(self.configuration_path)))
        need(7 in feature_configuration.READS)
        need(set(feature_configuration.capabilities(self.targets['primary']))=={'feature.world-web.'+kind for kind in ('act','observe','cleanup','terminal')})
        outer=self;original_driver=appium_adapter.WebDriver
        class ModelDriver(original_driver):
            # Only OS producer calls are modeled. W3C input and GET/DELETE use
            # the existing real owned loopback transport, not a success spy.
            def execute(_self,session,operation,values):
                selector=next(key for key,sdk in outer.f.sdks.items() if sdk.binding['sessionId']==session)
                model=outer.f.models[selector];sdk=outer.f.sdks[selector];outer.native_operations.append((selector,operation,deepcopy(values)))
                if operation=='mobile: overteProcessInfo':return model.process()
                if operation=='mobile: overteProcessSourceInfo':return deepcopy(model.source)
                if operation=='mobile: terminateApp':
                    need(values==dict(bundleId=model.bundle['bundleId']));outer.f.own.append((selector,'app.stop'))
                    model.running=False;sdk.foreground=False;return True
                if operation=='mobile: backgroundApp':
                    need(values==dict(seconds=-1));outer.f.own.append((selector,'lifecycle.background'))
                    sdk.foreground=False;sdk.lifecycle['backgrounds']+=1;sdk.close_document();return True
                raise AssertionError('Unexpected declared OS operation')
        self.stack.enter_context(patch.object(appium_adapter,'WebDriver',ModelDriver))
        self.f.clients={key:ModelDriver(self.f.url) for key in self.f.sdks}
        class Base:
            def __init__(_self,platform):_self.platform=platform;_self.adapter_id='world-host-declared-native'
            @staticmethod
            def advertised_capabilities(_target):return ['app.launch','app.foreground','app.process']
            def target(_self,selector):return deepcopy(outer.targets[selector])
            def state_path(_self,selector):return outer.f.paths[selector]
            def read_session(_self,selector):return PrivateFeatureState(outer.f.paths[selector]).read()
            def save_session(_self,selector,value):
                store=PrivateFeatureState(outer.f.paths[selector]);store.write(value,store.read())
            def ensure_session(_self,selector):
                value=_self.read_session(selector);need(value is not None);return outer.f.clients[selector],value['sessionId'],value
            def reset_launch_state(_self,*_args):pass
            def query_app_state(_self,_client,session,_target):
                key=next(key for key,sdk in outer.f.sdks.items() if sdk.binding['sessionId']==session)
                return 4 if outer.f.sdks[key].foreground else 3
            def invoke(_self,selector,operation,values):
                need(operation=='app.launch' and values=={});sdk=outer.f.sdks[selector];outer.f.own.append((selector,operation))
                sdk.foreground=True;sdk.lifecycle['activations']+=1;sdk.history=[]
                sdk.open_document(sdk.domain.marker['sourceUrl'],new_view=True);return dict(launched=True)
            def cleanup(_self,_selector):raise AssertionError('Typed World end must precede generic fallback')
        summary=dict(physicalHandoffVersion=1,bundleIdentity=deepcopy(self.f.models['primary'].bundle),
            artifactIdentity={key:self.f.sdk.binding[key] for key in ('sourceRevision','artifactSha256')})
        self.adapter=create_physical_adapter(SimpleNamespace(artifact_root=str(self.artifacts)),Base,lambda _args:deepcopy(summary))
        # Explicit installed-context/target/native PRODUCER seams. Actual
        # candidate/native/physical acceptance is not established here. The
        # real typed InstalledCodeBinding model retains its durable phase CAS.
        def scope(selector,session,state,_target):
            self.adapter._candidate_guard();sdk=self.f.sdks[selector]
            need(session==sdk.binding['sessionId'] and state==self.adapter.read_session(selector))
            return {key:value for key,value in sdk.binding.items() if key!='processIdentity'}
        self.adapter._scope=scope
        self.adapter._binding_store=lambda selector:self.f.models[selector].store
        self.adapter._binding=lambda selector,*_args:self.f.models[selector].gate()
        def retired_scope(selector,value):
            self.adapter._candidate_guard(complete=True)
            need(value=={key:item for key,item in self.f.sdks[selector].binding.items() if key!='processIdentity'})
            return self.adapter._target(selector)
        self.adapter._retired_candidate_scope=retired_scope
        self.f.runtime.adapter=self.adapter;self.f.allow_role_threads()
        # Observe the ORIGINAL step and rethrow unchanged. This captures even
        # exceptions the original run_flow intentionally catches; no product
        # result/guard/capability or requested publication is substituted.
        actual_step=world_web_observer.step
        def observed_step(flow):
            if flow is not self.f.secondary:return actual_step(flow)
            self.actor_steps+=1;serial=self.actor_steps
            entry=time.monotonic_ns();body_return=None;selected=None
            self.record_worker(dict(event='actual-step-entry',step=serial,hostMonotonicNs=entry,
                apiLimitSeconds=ACTUAL_API_SECONDS,apiClock='actual-host-time.monotonic',
                originalFlowClock='declared-model',nativeQualified=False))
            api_enter=time.monotonic_ns()
            try:
                # Same existing production scope/guards; nested publish uses
                # this real25 budget rather than the declared model clock.
                # Logging I/O stays OUTSIDE the original operation budget.
                with actual_api_scope(time.monotonic):
                    selected=actual_step(flow)
                    body_return=time.monotonic_ns()
            except BaseException as error:
                exit_time=time.monotonic_ns()
                from feature_journeys.phase_fixture import PhasePending
                from adapters.script_feature.lock import ScriptSourceBusy
                from ios.adapters.world_web_resource_disposition import ResourceAdmissionPending
                # Exactly run_flow's failure classes, after exempting its
                # three normal readiness signals. Worker behavior is untouched.
                if (isinstance(error,(OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError))
                    and not isinstance(error,(PhasePending,ScriptSourceBusy,ResourceAdmissionPending))):
                    self.worker.remember_step_failure(error,error.__traceback__)
                self.record_worker(dict(event='actual-step-exception',step=serial,
                    apiEnterHostNs=api_enter,bodyReturnHostNs=body_return,apiExitHostNs=exit_time,
                    elapsedApiScopeSeconds=(exit_time-api_enter)/1e9,exceptionType=type(error).__name__,
                    traceback=''.join(traceback.format_exception(error))))
                raise
            exit_time=time.monotonic_ns()
            self.record_worker(dict(event='actual-step-return',step=serial,selected=selected,
                apiEnterHostNs=api_enter,bodyReturnHostNs=body_return,apiExitHostNs=exit_time,
                elapsedApiScopeSeconds=(exit_time-api_enter)/1e9))
            return selected
        self.stack.enter_context(patch.object(world_web_observer,'step',observed_step))
        self.worker=ScheduledActor(self.f.secondary,lambda:self.f.sdk.time,self.record_worker);case.addCleanup(self.worker.close)
        def factory(runtime,selector,run,*,role,client,settings):
            need(runtime.adapter is self.adapter and selector in self.f.sdks and run==self.f.network.run)
            runtime._sources=self.f.sources;runtime._world_web_source_owner=self.f.source_owner
            runtime._world_web_marker=lambda *_args:self.f.whole.scope
            runtime._graphics_final_source=self.f.runtime._graphics_final_source
            runtime._retired_process_observer=self.f.runtime._retired_process_observer
            flow=IOSWorldWebFeature(runtime,selector,client,run,role,settings,
                epoch_ms=self.f.sdk.host_epoch,monotonic=lambda:self.f.sdk.time,sleep=self.primary_sleep)
            flow.lock=self.f.whole.scope.lock if role=='primary' else self.f.actor.lock;flow.primary_lock=self.f.whole.scope.lock
            if role=='primary':self.current_primary=flow
            self.factories.append((selector,run,role));return flow
        self.stack.enter_context(patch.object(IOSWorldWebRuntime,'_world_web_feature',factory))
    def record_worker(self,event):
        # Test evidence is outside ALL product roots and immutable candidate
        # files. No generic locals/config/source values are serialized.
        with self.worker_events_lock:
            self.worker_events.append(deepcopy(event))
            with (self.root/'actual-actor-worker-events.json').open('w') as stream:
                json.dump(self.worker_events,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())

    def primary_sleep(self,delay):
        flow=self.current_primary
        if flow is not None and flow.state is not None and flow.state['phase']=='cleaned' and flow.state['retirement'] is None:self.worker.cycle()
        self.f.sdk.sleep(delay)
    def activate(self,ticket,verb='baseline',inputs=None):
        # Controller challenge precedes production; no old packet is relabeled.
        sdk=self.f.sdk;inputs={} if inputs is None else deepcopy(inputs);sdk.ticket=ticket;sdk.activated_epoch=sdk.host_epoch()
        self.f.network.controller.activate(ticket,verb,inputs)
        if verb=='baseline' and not self.f.whole.scope.frames:
            # Select the initial controller challenge before any Scope frame
            # or feature WAL exists. Never rebind an admitted old original.
            need(self.f.primary.store.read() is None and not self.f.whole.source.state['records'])
            self.f.whole.scope.ticket=ticket
        sdk.activations.append(dict(sequence=len(sdk.activations)+1,ticket=ticket,activatedEpochMs=sdk.activated_epoch,stimulus=dict(verb=verb,inputs=inputs)))
    def invoke(self,operation,values):
        self.calls.append((operation,deepcopy(values)));result=self.adapter.invoke('primary',operation,values);need(self.adapter._operation is None)
        if operation=='feature.world-web.observe':self.worker.cycle()
        if operation=='feature.world-web.terminal' and values['stage']=='finish':self.worker.finish()
        return result
    def continuity(self,_stage,_verb):
        need(self.f.models['primary'].running and self.f.models['primary'].sdk_live);self.f.models['primary'].gate().continuity()
    def journey(self):
        return Journey('world-web',self.f.network.run,self.f.sdk.fixture_url,invoke=self.invoke,witness=self.f.network.controller.observe,
            activate=self.activate,read_artifact=lambda name:read_private_artifact(self.f.whole.scope.root,name),
            image_policy=dict(screen=deepcopy(self.f.primary.policy)),continuity=self.continuity,monotonic=lambda:self.f.sdk.time,
            epoch_ms=self.f.sdk.host_epoch,sleep=self.f.sdk.sleep,report=self.reports.append,terminal_profile=terminal.PROFILE,
            retire_fixture=self.f.network.controller.close)
