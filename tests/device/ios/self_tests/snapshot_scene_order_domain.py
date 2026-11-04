"""Genuine normal Snapshot/Actor owners with a declared lower frame timeline.

The independent renderer state is chosen before input. Its second frame is a
scheduled model event after the existing lower normal-capture callback; no
query creates a frame or supplies desired entity values. No native executes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import uuid
from adapters.native_feature_observation import NativeFeatureObservation
from ios.adapters.feature_observation import FeatureObservation
from ios.adapters.snapshot_review_runtime import IOSSnapshotReviewRuntime
from ios.adapters.snapshot_scene_pair_runtime import IOSSnapshotScenePairRuntime
from ios.self_tests.snapshot_scene_domain import SceneCaptureDomain,SceneActorDomain,RUN,TICKET


class OrderedSceneDomain:
    def __init__(self,case):
        self.primary=SceneCaptureDomain(case);self.actor=SceneActorDomain(case,self.primary)
        self.emit_after_capture=True;self.lose_after=False;self.frame_events=[]
        effect=self.primary.capture.capture_effect
        def captured():
            effect()
            if self.emit_after_capture:self.render_actor_frame()
            if self.lose_after:self.actor.lose=True
        self.primary.capture.capture_effect=captured
        base=type(self.primary.runtime)
        class PrimaryRuntime(IOSSnapshotScenePairRuntime,base):pass
        self.primary.runtime=PrimaryRuntime(self.primary.runtime.adapter)
        a=self.actor
        # A fresh genuine FeatureObservation constructor is bound to the
        # independent lower SDK model's actual selected session before birth.
        a.ctx.feature=FeatureObservation(a.ctx.files,a.binding['sessionId'],a.ctx.files.target,a.ctx.files.process,
            epoch_ms=a.clock,monotonic=a.monotonic,sleep=self.primary.capture.sleep)
        model=self
        class ActorRuntime(IOSSnapshotReviewRuntime):
            def _sources(self,selector):
                native=NativeFeatureObservation(a.ctx.native.send,a.ctx.native.original,a.clock,a.ctx.native.guard,42,ios=True,
                    monotonic=a.monotonic,sleep=model.primary.capture.sleep)
                return dict(binding=deepcopy(a.binding),check=lambda:a.ctx.good,observer=a.ctx.feature,clock_source=native)
        self.actor_runtime=ActorRuntime(SimpleNamespace(state_path=lambda _selector:a.ctx.root/'session.json',
            _candidate_guard=lambda:True,_binding=lambda:None))

    def render_actor_frame(self):
        a=self.actor;frame=deepcopy(a.frame)
        frame.update(frameInstance=uuid.uuid4().hex,frameIndex=frame['frameIndex']+1,recordedEpochMs=a.clock(),consumedEpochMs=a.clock())
        a.frame=frame;self.frame_events.append(dict(index=frame['frameIndex'],epoch=frame['consumedEpochMs']))

    def owner(self):
        d=self.primary
        return d.runtime.scene_capture_order('primary',self.actor_runtime,'actor',RUN,d.capture.client(),
            epoch_ms=d.capture.epoch,monotonic=d.capture.mono,sleep=d.capture.sleep)
