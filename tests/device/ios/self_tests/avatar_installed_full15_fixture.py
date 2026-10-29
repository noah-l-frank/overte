"""Unchanged InstalledAdapter and common15 over declared native producers.

Normal Qt/SDK/GPU/OS are models selected before first candidate binding. Actual
HTTPS, Node/Pal/People/Script input, Source/pixel files, controls, public APIs,
Actor run(), common assertions, publication and canonical end remain literal.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import threading
import time
import traceback
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.avatar_primary_control import prepare as prepare_control
from feature_journeys.engine import Journey
from feature_journeys.evidence import read_private_artifact
from feature_journeys.terminal import PROFILE
from feature_journeys.witness import Client
from ios import avatar_observer
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.self_tests.avatar_canonical_frontdoor_fixture import AvatarCanonicalFrontdoor,CanonicalTerminalDomain
from ios.self_tests.avatar_installed_native_channels import AvatarNativeChannels,RealtimeProducerClock
from ios.self_tests.avatar_prepare_fixture import RUN


class OriginalAvatarActor:
    """Actual original worker run(), independent thread, no result substitution.

    This does not execute the CLI native adapter constructor in another OS
    process. Its actual thread must stop after the genuine canonical SDK end.
    """
    def __init__(self,runtime,configuration,root,test):
        self.runtime,self.configuration,self.root=runtime,configuration,root
        self.result=None;self.error=None;self.cancel=threading.Event();self.events=[]
        self.thread=threading.Thread(target=self.work,name='avatar-installed-original-actor',daemon=True)
        test.addCleanup(self.close);self.thread.start()
    def event(self,value):
        self.events.append(value)
        path=self.root/'actual-avatar-actor-events.json'
        with path.open('w') as stream:json.dump(self.events,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    def sleep(self,seconds):
        if self.cancel.wait(seconds):raise RuntimeError('Declared host Actor schedule cancelled after test failure')
    def work(self):
        try:self.result=avatar_observer.run(self.runtime,self.configuration,monotonic=time.monotonic,sleep=self.sleep)
        except BaseException as error:
            self.error=error
            self.event(dict(event='uncaught-original-worker-error',type=type(error).__name__,traceback=''.join(traceback.format_exception(error))))
        finally:self.event(dict(event='actual-original-worker-return',returnCode=self.result,uncaughtType=None if self.error is None else type(self.error).__name__))
    def check(self):
        if self.error is not None:raise self.error
        # run_flow's own failure journal is authoritative responsibility. An
        # already caught source error is not silently treated as a clean worker.
        path=Path(self.configuration['artifactRoot'])/('avatar-worker-failed-'+self.configuration['runId']+'.json')
        need(not path.exists())
    def finish(self):
        self.thread.join(timeout=30);need(not self.thread.is_alive());self.check();need(self.result==0)
    def close(self):
        if self.thread.is_alive():self.cancel.set();self.thread.join(timeout=30)
        need(not self.thread.is_alive())


class NativeCanonicalTerminalDomain(CanonicalTerminalDomain):
    def create_clock(self):return RealtimeProducerClock()
    def declare_native_target(self,role,native):
        super().declare_native_target(role,native);AvatarNativeChannels(self,role,native)


class NativeInstalledFrontdoor(AvatarCanonicalFrontdoor):
    domain_type=NativeCanonicalTerminalDomain


class AvatarInstalledFull15:
    def __init__(self,test):
        self.frontdoor=NativeInstalledFrontdoor(test);f=self.frontdoor;d=self.domain=f.domain
        # Two real instances of the same canonical InstalledAdapter class,
        # sharing declared candidate files but separate operation ownership.
        self.adapter,self.actor_adapter=f.adapter,type(f.adapter)()
        self.root=f.root;self.calls=[];self.reports=[]
        self.control_root=self.root/'primary-control';self.control_root.mkdir(mode=0o700)
        self.reader=Client(d.client.url,d.reader)
        self.reader.run=RUN;self.reader.area='avatar-people';self.reader.closed=False
        prepare_control(self.reader,PrivateFeatureState(self.control_root/('avatar-primary-control-'+RUN+'.json')),RUN)
        self.configuration=f.configuration(10)
        self.configuration.update(avatarCoordinatorVersion=1)
        self.configuration['avatarPeople']['authorityControlRoot']=str(self.control_root)
        f.set_configuration(self.configuration)
        actor=d.owners['actor']
        self.actor_configuration=dict(iosAvatarObserverVersion=1,target='actor',primaryTarget='primary',runId=RUN,
            candidateArguments=['declared-host-runtime-only'],fixtureUrl=d.client.url,actorToken=d.actor,
            authorityRead=dict(mode='adapter',token=d.adapter),durationSeconds=1800,
            artifactRoot=str(actor.root),imagePolicy=deepcopy(actor.policy))
        self.worker=OriginalAvatarActor(IOSAvatarRuntime(self.actor_adapter),self.actor_configuration,self.root,test)
        # Same existing preparation position as other public common fixtures:
        # complete ordinary preparation before the runner activates fresh phase1.
        self.invoke('feature.avatar-people.observe',dict(contractVersion=16,runId=RUN,afterSequence=0))
        self.journey=Journey('avatar-people',RUN,d.client.url+'/runs/'+RUN+'/',invoke=self.invoke,
            witness=self.witness,activate=self.reader.activate,
            read_artifact=lambda name:read_private_artifact(Path(self.configuration['avatarPeople']['artifactRoot']),name),
            image_policy=dict(screen=deepcopy(self.configuration['avatarPeople']['imagePolicy'])),continuity=self.continuity,
            monotonic=time.monotonic,epoch_ms=lambda:time.time()*1000,sleep=time.sleep,report=self.reports.append,
            terminal_profile=PROFILE,retire_fixture=self.reader.close)
    def invoke(self,operation,values):
        self.worker.check();self.calls.append((operation,deepcopy(values)))
        return self.adapter.invoke('primary',operation,values)
    def witness(self):self.worker.check();return self.reader.observe()
    def continuity(self,_phase,_verb):
        self.worker.check()
        for n in self.domain.natives.values():need(n.running and n.process()['foreground'])
    def metadata_effects(self):
        return dict(native={role:deepcopy(n.commands) for role,n in self.domain.natives.items()},
            inputs={role:list(n.input_log) for role,n in self.domain.natives.items()},
            lifecycle={role:list(n.lifecycle_inputs) for role,n in self.domain.natives.items()},sdk=deepcopy(self.domain.sdk_requests))
