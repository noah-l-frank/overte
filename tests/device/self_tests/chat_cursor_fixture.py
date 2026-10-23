"""Actual cache retirement with explicit metadata for 24 unexecuted inputs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import uuid

from adapters.chat_journey.cleanup_admission import ChatCleanupAdmission
from adapters.chat_journey.cache_lifetime import ChatCacheLifetime
from adapters.chat_journey.flow_inputs import recipe
from adapters.chat_journey.phase_fence import ChatPhaseFence,bind_phase_fence
from adapters.chat_journey.observation import ChatObservationOwner
from adapters.chat_journey.samples import ChatCacheAbsence
from adapters.native_chat_observation import OwnedChatCapture
from adapters.normal_feature_state import PrivateFeatureState


def cleanup(compiled,cursor):
    """Caller has actually observed initial absence and ordinary first Open."""
    flow=compiled.h;native=flow.h.native;root=flow.root;run=cursor.scope['runId']
    for step in recipe(run)[2:]:
        flow.sleep(.01);flow.w.journal.activate(run,uuid.uuid4().hex,step['verb'],step['inputs'])
        with flow.flow.session():flow.flow.begin(flow.flow.source.read());flow.flow.finish()
    flow.w.journal.activate(run,uuid.uuid4().hex,'cleanup',{})
    admission=ChatCleanupAdmission(flow.flow,PrivateFeatureState(root/'cleanup-admission.json'))
    with flow.flow.session():admission.admit()
    flow.widgets.panel=False;flow.widgets.tablet=False;flow.widgets.focus=False;flow.widgets.keyboard_request=False;flow.sync()
    fence=ChatPhaseFence(flow.flow,cleanup=admission)
    with flow.flow.session():
        for old,boundary in zip(flow.owner.caches,(flow.h.h.primary,flow.h.h.peer)):
            reader=boundary.reader();reader.pid=old.reader.pid
            reader.clock_ms=lambda:native.epoch;reader.monotonic=lambda:native.host;reader.sleep=flow.sleep
            cache=ChatCacheLifetime(OwnedChatCapture(reader,old.capture.owner,run),old.store,old.lock,monotonic=lambda:native.host)
            bind_phase_fence(cache,fence);cache.retire()
    role=cursor.scope['role'];source=cursor.current.source;key='global-'+role+'-cleanup'
    samples=compiled.samples(role,PrivateFeatureState(root/(key+'-samples.json')),kind=ChatCacheAbsence,
        script_source=cursor.current.samples.script_source)
    return ChatObservationOwner(source,samples,flow.flow.store,PrivateFeatureState(root/(key+'-observation.json')),
        stage='cleanup',cleanup_store=admission.store,monotonic=lambda:native.host)
