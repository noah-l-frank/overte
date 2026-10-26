"""Small real Stop/OS/SDK suffix after an explicit prior-native-seal model.

The earlier complete Tablet native graph is deliberately unavailable. Every
phase response, source/Stop request, OS child journal and SDK end after that
boundary uses the existing production implementation and local SDK fixture.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
from types import SimpleNamespace
import traceback

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from ios.adapters.tablet_web_process_end import TabletWebProcessEnd
from ios.adapters.tablet_web_session_end import TabletWebSessionEnd
from ios.adapters.tablet_web_terminal_finish import worker_original,worker_store
from ios.adapters.tablet_web_runtime import IOSTabletWebRuntime
from ios.self_tests.tablet_web_host_clock import advance
from ios.self_tests.tablet_web_lifecycle_fixture import ExistingLifecycleAdapter
from ios.self_tests.tablet_web_paired_fixture import SELECTOR,ACTOR
from ios.self_tests.test_ios_tablet_web_sources import RUN


def phase_floor(feature,lock):
    lock.assert_held()
    packet=PhaseFixtureReader(feature.client,RUN,'tablet-web',epoch_ms=feature.epoch_ms,monotonic=feature.monotonic).status()
    value=dict(componentOwnPhaseOriginalVersion=1,hostProcessId=os.getpid(),packet=packet)
    store=PrivateFeatureState(feature.root/('component-phase-floor-'+feature.role+'.json'));store.write(value,None)
    return value


def process(feature,lock):
    """Earlier seal is a visibly non-production carrier, never an End proof."""
    lock.assert_held();store=PrivateFeatureState(feature.root/'component-prior-native-seal.json');previous=store.read()
    need(previous is not None and previous.get('componentPriorNativeSealVersion')==1)
    def replay():
        need(same(store.read(),previous));return deepcopy(previous)
    def floors():
        return {role:PrivateFeatureState(feature.root/('component-phase-floor-'+role+'.json')).read()['packet']
            for role in ('primary','actor')}
    owner=object.__new__(TabletWebProcessEnd)
    owner.feature,owner.lock,owner.binding,owner.run=feature,lock,deepcopy(feature.binding),RUN
    owner.terminal=SimpleNamespace(store=store,previous=previous,replay=replay,phase_floors=floors,
        state=dict(description=dict(ticket=previous['ticket'])))
    owner.store=PrivateFeatureState(feature.root/('tabletweb-process-end-'+RUN+'.json'));owner.previous=owner.store.read()
    owner.state=None if owner.previous is None else owner.decode(owner.previous)
    return owner


def actor(inputs,clock,channel):
    try:
        root,metadata,settings,fixture_url,base=inputs
        def mono():return clock.value
        def epoch():return base+round(clock.value*1000)+10000
        def sleep(seconds):advance(clock,seconds)
        runtime=IOSTabletWebRuntime(ExistingLifecycleAdapter(root,metadata))
        feature=runtime._tablet_web_feature(SELECTOR,RUN,role='actor',client=Client(fixture_url,ACTOR,
            monotonic=mono,sleep=sleep),settings=settings)
        feature.monotonic,feature.epoch_ms,feature.sleep=mono,epoch,sleep
        lock=ScriptSourceLock(Path(root)/'script-feature-sources.lock')
        with lock.held():phase_floor(feature,lock)
        channel.send(dict(kind='ready',hostProcessId=os.getpid()))
        while True:
            command=channel.recv()
            with feature.operation(),lock.held():
                owner=process(feature,lock)
                if command=='advance':channel.send(dict(kind='advanced',done=owner.advance('actor')))
                elif command=='retire':
                    session=TabletWebSessionEnd(owner);value=worker_original(feature,owner,session)
                    store=worker_store(feature);need(store.read() is None);store.write(value,None)
                    need(same(store.read(),value));channel.send(dict(kind='retired',sha256=digest(value)));return
                else:raise AssertionError('Unreviewed component scheduling command')
    except BaseException as error:
        channel.send(dict(error=type(error).__name__,traceback=traceback.format_exc()))
        raise
    finally:channel.close()
