"""Unchanged common Journey over fresh real Emote host owners and originals.

Native/WDA/OS and candidate preflight are declared producer models. Pinned
phoneEmote.js callbacks, normal W3C/token inputs, UDP, HTTP witness, PNG bytes,
all typed terminal owners and canonical installed-source Stop gates are real.
This fixture does not bypass the intentionally closed area admission gate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
import json
from pathlib import Path
import time
from unittest.mock import patch
from adapters.native_feature_observation import need
from feature_journeys.engine import Journey
from feature_journeys.terminal import PROFILE
from feature_journeys.witness import Client
from ios.self_tests.emote_rooted_whole_end_fixture import WholeRootedEndFixture


class CommonEmoteJourneyFixture:
    def __init__(self,test,*,retain_originals=False):
        from ios.self_tests.emote_animation_fixture import bundled_frames
        from ios.self_tests import emote_script_vm_fixture as vm
        frames=bundled_frames();print(json.dumps(dict(emoteBundledLoadedFrames=frames)),flush=True)
        # Only this explicit fresh producer uses actual bundled loaded metadata.
        # Existing component models and all retained old originals stay intact.
        with patch.object(vm,'ActualEmoteVM',partial(vm.ActualEmoteVM,frame_counts=frames)):
            self.end=WholeRootedEndFixture(test,retain_originals=retain_originals)
        self.normal=self.end.normal;self.primary=self.normal.flow;self.actor=self.normal.actor.flow
        self.domain=self.normal.target.domain;self.report=None;self.operations=[]
        self.reader=Client(self.normal.target.client.url,'r'*64)
        # Polling after the seal must advance only the modeled host/OS clock;
        # no background Actor live work may resume after its sealed window.
        self.end.facades['primary'].sleep=self.domain.sleep
        scene_sleep=self.primary.sleep
        def sleep(seconds):
            if self.primary.lock._owner is None and self.primary.primary_lock._owner is None:
                status=self.primary.phase.status()
                if status['active'] and status['activations'][-1]['stimulus']['verb']=='cleanup':
                    self.actor.cleanup(dict(contractVersion=16,runId=self.primary.run))
                    self.domain.sleep(seconds);return
            scene_sleep(seconds)
        self.primary.sleep=sleep
        # The worker and its actual paired marker preparation start before the
        # common runner establishes its first fresh baseline barrier. Early
        # preparation publications keep their original preceding ticket.
        warm=dict(contractVersion=16,runId=self.primary.run,afterSequence=0)
        self.invoke('feature.emotes.observe',warm);self.actor.observe(warm)
        self.actor.sleep=self.normal.actor.target.domain.sleep
        self.journey=Journey('emotes',self.primary.run,self.primary.phase.fixture_url,
            invoke=self.invoke,witness=self.witness,activate=self.activate,read_artifact=self.read_artifact,
            image_policy=dict(screen=deepcopy(self.normal.target.policy)),continuity=self.continuity,
            monotonic=self.primary.monotonic,epoch_ms=self.primary.epoch_ms,sleep=self.domain.sleep,
            report=self.record,terminal_profile=PROFILE,retire_fixture=self.retire)
        artifacts=self.journey.artifacts
        def measured_artifacts(*args,**kwargs):
            try:return artifacts(*args,**kwargs)
            except (AssertionError,OSError,EOFError,SyntaxError) as error:
                print(json.dumps(dict(emoteCommonArtifactProblem=str(error))),flush=True);raise
        self.journey.artifacts=measured_artifacts

    def activate(self,ticket,verb='baseline',inputs=None):
        self.normal.target.ticket=ticket
        self.normal.target.server.journal.activate(self.primary.run,ticket,verb,inputs)
        # These are not prepared owners yet: select the original actual first
        # baseline challenge before any marker WAL or normal input is created.
        for role in self.end.roles.values():
            scope=role.parts['scope']
            if scope.previous is None and not scope.frames:scope.ticket=ticket

    def invoke(self,operation,call):
        kind=operation.rsplit('.',1)[-1];need(operation=='feature.emotes.'+kind)
        label=call.get('verb',call.get('stage',kind));started=time.monotonic();self.operations.append((kind,label))
        print(json.dumps(dict(emoteCommonOperation=kind,label=label)),flush=True)
        try:
            if kind=='terminal':return self.end.facades['primary'].terminal(call)
            need(kind in ('act','observe','cleanup'));result=getattr(self.primary,kind)(call)
            if kind=='observe':print(json.dumps(dict(emoteCommonPrimaryState=result['state'])),flush=True)
            if kind in ('act','observe'):
                # The independent worker keeps observing even when this common
                # row does not request peer evidence. It receives no expected
                # state and its actual HTTP publications keep their own ticket.
                peer=self.actor.observe(dict(contractVersion=16,runId=self.primary.run,afterSequence=0))
                print(json.dumps(dict(emoteCommonActorState=peer['state'])),flush=True)
            return result
        finally:
            print(json.dumps(dict(emoteCommonOperationDone=kind,label=label,seconds=round(time.monotonic()-started,6))),flush=True)

    def witness(self):
        # Actual independent worker work runs after every ordinary operation;
        # this callback only reads its original unfiltered HTTP journal.
        value=self.reader.request('/runs/'+self.primary.run)
        current=[row for row in value['entries'] if row['ticket']==value['ticket']]
        print(json.dumps(dict(emoteCommonWitnessEntries=len(current),
            firstAgeMs=None if not current else round(self.primary.epoch_ms()-current[0]['capturedEpochMs'],3),
            lastAgeMs=None if not current else round(self.primary.epoch_ms()-current[-1]['capturedEpochMs'],3))),flush=True)
        return value

    def continuity(self,_stage,_verb):
        sources=self.end.runtime._sources('primary');need(sources['check']() is not False)

    def read_artifact(self,name):
        need(type(name) is str);root=self.primary.root;path=root/name
        need(Path(name).name==name and path.resolve()==path and path.parent==root)
        from ios.adapters.emote_original_lease import EmoteOriginalLease
        before=path.stat();need(before.st_nlink==1 and 0<before.st_size<=12*1024*1024)
        raw=path.read_bytes();need(EmoteOriginalLease.signature(path.stat())==EmoteOriginalLease.signature(before));return raw

    def retire(self):self.reader.request('/runs/'+self.primary.run,method='DELETE')
    def record(self,value):self.report=deepcopy(value)
