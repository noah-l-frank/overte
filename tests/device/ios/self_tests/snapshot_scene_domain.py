"""Declared lower renderer/Scene/Actor producers, chosen BEFORE Primary input.

No native/SDK/OpenGL/physical scene executes. Actual normal capture, PNG/WDA,
PFS/OFS, independent native brackets, OS locks and retained files are real host
owners. Neither query callback receives desired target entity values.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from contextlib import contextmanager
from copy import deepcopy
import json
import uuid
from unittest.mock import patch
from adapters.native_feature_observation import NativeFeatureObservation,need
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters import feature_observation,snapshot_scene
from ios.adapters.snapshot_scene_witness import SnapshotSceneWitnessOwner
from ios.self_tests.snapshot_provenance_domain import ProvenanceCaptureDomain
from ios.self_tests.test_ios_snapshot_manifest import SnapshotManifestTests
from ios.self_tests.test_ios_snapshot_capture_rendered_review import RUN,TICKET


def model_scene():
    # Finite source state, not expected requested values supplied by the reader.
    matrix=[1,0,0,0,0,1,0,0,0,0,1,-2,0,0,0,1]
    return dict(snapshotRenderedSceneVersion=1,profile='entity-render-entry-v1',complete=True,
        entities=[dict(entityId='12345678-1234-4234-8234-123456789abc',rendererInstance=uuid.uuid4().hex,
            renderItemId=11,modelTransform=list(matrix),renderTransform=list(matrix),worldBounds=[-.5,-.5,-2.5,1,1,1],entered=1,returned=1)])


def model_camera():
    return dict(position=[0,0,0],rotation=[0,0,0,1],projection=[1,0,0,0,0,1,0,0,0,0,-1.002002,-.2002002,0,0,-1,0],
        fieldOfViewDegrees=90,aspectRatio=1,nearClip=.1,farClip=100,perspective=True)


class SceneCaptureDomain(ProvenanceCaptureDomain):
    def __init__(self,case):
        super().__init__(case);self.scene_inputs=model_scene()
        native=self.capture.native;begin=native.begin
        def actual_begin(request='snap_1700000000000_1'):
            cap,identity=begin(request)
            # Extend the lower producer's record at its ORIGINAL birth, before
            # finish/callback/file original publication. No archive is edited.
            self.recorded[identity].update(snapshotFrameProvenanceVersion=2,scene=deepcopy(self.scene_inputs))
            return cap,identity
        native.begin=actual_begin


class SceneActorDomain:
    def __init__(self,case,primary,*,same_target=False):
        self.primary=primary;prior=feature_observation.post_request
        self.ctx=SnapshotManifestTests();self.ctx.setUp();case.addCleanup(self.ctx.doCleanups)
        # The existing lower installed/SDK model's binding is selected before
        # any Actor owner, query, PFS or OFS birth; it is not a real installation.
        self.binding=dict(self.ctx.binding,targetFingerprint=('c' if same_target else 'd')*64)
        self.clock=primary.capture.epoch;self.monotonic=primary.capture.mono
        self.scene_inputs=model_scene();self.camera=model_camera();self.sequence=0;self.queries=[];self.raw=None;self.lose=False;self.fault=None
        self.frame=dict(snapshotFrameProvenanceVersion=2,frameInstance=uuid.uuid4().hex,frameIndex=1,
            processId=42,pipeline='forward-primary-mono',recordedEpochMs=self.clock(),transformSlot=0,viewport=[0,0,128,128],
            worldFromCamera=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],camera=deepcopy(self.camera),backend='opengl',
            scene=self.scene_inputs,consumedEpochMs=self.clock())
        def produced(value):
            def clocks(node):
                if type(node) is dict:
                    for key,item in node.items():
                        if key.endswith('EpochMs'):node[key]=self.clock()
                        else:clocks(item)
                elif type(node) is list:
                    for item in node:clocks(item)
            clocks(value);value['processId']=42
        self.ctx.native.mutate=produced
        execute=self.ctx.files.execute
        def pull(session,operation,values):
            if values['remotePath'].endswith('/'+snapshot_scene.FILE):
                need(operation=='mobile: pullFile' and self.raw is not None)
                return base64.b64encode(self.raw.encode()).decode('ascii')
            return execute(session,operation,values)
        self.ctx.files.execute=pull
        def post(request,timeout):
            query=json.loads(request.data)
            if query.get('action')!=snapshot_scene.ACTION:return prior(request,timeout)
            need(timeout==5);snapshot_scene.command(query);self.sequence+=1;self.queries.append(deepcopy(query))
            clock=dict(epochMs=self.clock(),monotonicMs=self.clock()-1700000000000+1000)
            body=dict(iosSnapshotSceneVersion=1,requestId=query['commandId'],runId=query['runId'],instance='d'*32,
                sequence=self.sequence,processId=42,clockDomain='native-main-snapshot-scene',clockBefore=dict(clock),clockAfter=dict(clock),
                source=dict(complete=True,frame=deepcopy(self.frame)))
            if self.fault is not None:self.fault(body)
            self.raw=json.dumps(body,indent=1)+'\n';self.ctx.files.echo=json.dumps(query).encode()
            if self.lose:raise OSError('Actual modeled Actor query delivered, original return lost')
            return self.ctx.files
        patched=patch.object(feature_observation,'post_request',post);patched.start();case.addCleanup(patched.stop)

    def owner(self,index=1,*,historical=False):
        store=PrivateFeatureState(self.ctx.root/('ios-snapshot-actor-scene-witness-'+format(index,'04d')+'.json'))
        url=self.primary.capture.client().url+'/runs/'+RUN+'/'
        if historical:return SnapshotSceneWitnessOwner(store,self.ctx.lock,self.binding,RUN,index,url,historical=True)
        phase=PhaseFixtureReader(self.primary.capture.client(),RUN,'snapshots',epoch_ms=self.clock,monotonic=self.monotonic)
        native=NativeFeatureObservation(self.ctx.native.send,self.ctx.native.original,self.clock,self.ctx.native.guard,42,ios=True,
            monotonic=self.monotonic,sleep=self.primary.capture.sleep)
        return SnapshotSceneWitnessOwner(store,self.ctx.lock,self.binding,RUN,index,url,phase=phase,feature=self.ctx.feature,native=native,
            guard=lambda:self.ctx.good,epoch_ms=self.clock,monotonic=self.monotonic)

    @contextmanager
    def held(self,index=1,*,historical=False):
        with self.ctx.lock.held():yield self.owner(index,historical=historical)
