"""Actual one-context JS/W3C/PNG and original native/rendered/keyed owners.

Native Qt/SDK/GPU/file/key sources are declared models selected before birth.
No old frame, clock, view, payload or original is retimed or relabeled.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
from adapters.native_feature_observation import need
from adapters.native_script_files import NativeScriptFiles
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.emote_callback_retirement import IOSEmoteCallbackRetirementObserver,IOSEmoteCallbackNativeRetirement
from ios.adapters.emote_callback_scene import IOSEmoteCallbackRenderedRetirement,IOSEmoteCallbackKeyedRetirement
from ios.adapters.emote_cleanup import IOSEmoteCleanup
from ios.adapters.emote_file_receipts import IOSEmoteFileReceipts
from ios.adapters.emote_restoration_frames import IOSEmoteRestorationFrames
from ios.adapters.emote_rooted_quiet import refresh
from ios.self_tests import emote_callback_observer_fixture as fixture
from ios.self_tests.emote_pointer_fixture import PointerDomain
from ios.self_tests.emote_keys_fixture import KeyDomain
from ios.self_tests.marker_entities_fixture import EntityDomain
from self_tests.test_native_script_files import Boundary as FileBoundary
from unittest.mock import patch


class CallbackSceneFixture:
    def __init__(self,test):
        self.test=test;frames=fixture.bundled_frames()
        with (patch.object(fixture.vm_fixture,'ActualEmoteVM',partial(fixture.vm_fixture.ActualEmoteVM,frame_counts=frames)),
              patch.object(fixture.active_fixture,'ActualVMRig',partial(fixture.active_fixture.ActualVMRig,pose_profile='requested-clip')),
              patch.object(fixture.marker_fixture.MarkerScopeTests,'owner',fixture.rooted),
              patch.object(fixture.active_fixture.native_fixture,'RunningDomain',fixture.RootedMarkerDomain),
              patch.object(fixture.active_fixture,'IOSEmoteSamples',fixture.IOSEmoteCallbackSamples),
              patch.object(fixture.active_fixture,'IOSEmoteObserver',IOSEmoteCallbackRetirementObserver)):
            # This is a NEW source graph. Initial PNG occurs before its first
            # marker baseline/ordinary input, with the final callback producer
            # already selected by the actual virtual constructor dispatch.
            self.t=fixture.CallbackActiveFixture(test,defer_setup=True)
        t=self.t;self.root,self.scope,self.domain,self.lock=t.root,t.scope,t.domain,t.lock
        self.pointer_domain=PointerDomain(test,self.scope,self.domain);self.pointers=self.pointer_domain.owner();self.pointers.capture()
        self.key_domain=KeyDomain(self.scope,self.domain);self.keys=self.key_domain.owner();self.keys.capture()
        self.entity_domain=EntityDomain(test,self.scope,self.domain);self.entities=self.entity_domain.owner();self.entities.capture()
        t.w3c,t.normal=fixture.normal_tablet(t,pointer=self.pointer_domain.boundary)
        self.frames=IOSEmoteRestorationFrames(t.f.runtime,'owned',self.scope,self.root,self.lock,
            epoch_ms=self.scope.epoch_ms,monotonic=self.scope.monotonic,sleep=self.scope.sleep)
        self.initial=self.frames.capture('initial')
        self.scope.prepare();self.domain.paint();self.scope.admit_rendered()
        # Native file response clock is selected before its FIRST original;
        # the base producer still derives bytes/absence from the actual staged
        # disk directory. This hook never changes an already returned carrier.
        self.file_boundary=FileBoundary(self.root);self.file_boundary.root=self.domain.files.root
        def clocked(packet):
            packet['processId']=self.scope.pid
            packet['requestedEpochMs']=packet['capturedEpochMs']=self.domain.epoch()
        self.file_boundary.mutate=clocked
        def send(query):self.domain.sleep(.001);self.file_boundary.send(query)
        self.file_reader=NativeScriptFiles(send,self.file_boundary.read,self.domain.epoch,lambda:True,self.scope.pid,ios=True,
            monotonic=self.scope.monotonic,sleep=self.scope.sleep)
        self.files=IOSEmoteFileReceipts(PrivateFeatureState(self.root/'ios-emote-primary-native-files.json'),self.root,self.scope.binding,
            self.scope.run,self.scope.role,self.lock,lambda:True,native=self.scope.native,files=self.file_reader,
            epoch_ms=self.scope.epoch_ms,monotonic=self.scope.monotonic)
        with t.trace_consumer.held():self.first=t.observer.observe(0)
        self.first_original=t.observer.original(t.observer.state['records'][-1])
        self.native=self.rendered=self.keyed=None;self.native_ref=self.rendered_ref=self.keyed_ref=None

    def action(self,verb,**inputs):
        t=self.t;t.actions.act(t.activate(verb,**inputs));ref=t.actions.state['current']['before']
        if verb in ('play','sit','override'):t.native.sleep(.25)
        return dict(index=ref['revision'],sha256=ref['sha256'])

    def play_cancel(self):
        barrier=self.action('play',name='Crying');playing=self.t.observer.observe(self.first['sequence'],input_barrier=barrier)
        need(playing['state']['override'])
        barrier=self.action('cancel');restored=self.t.observer.observe(playing['sequence'],input_barrier=barrier)
        need(not restored['state']['override']);return restored

    def cleanup_inputs(self):
        t=self.t
        # Same original input-episode recipe as Feature.cleanup_inputs. These
        # callbacks validate BEFORE ordinary close, so they must not claim the
        # later retired/chooser-absent state. The actual retired4 proof remains
        # after close/DELETE/Scope cleanup and fresh drain originals below.
        actions=type(t.actions)(t.actions.store,t.sources,t.normal)
        rows=actions.state['history']+([actions.state['current']] if actions.state['current'] is not None else [])
        def state(frame):
            need(t.observer.state['baseline'] is not None)
            latest=next((row for row in reversed(rows) if row['before'] is not None
                and row['call']['verb'] in ('play','sit','override')),None)
            if latest is not None:
                barrier=dict(index=latest['before']['revision'],sha256=latest['before']['sha256'])
                before=t.observer.decoder.source(barrier)
                if frame['group']['native']['animation']['history']['overrideSequence']>before['group']['native']['animation']['history']['overrideSequence']:
                    t.observer.recover_owned_episode(barrier,frame)
            ticket=t.phase.previous['activations'][-1]['ticket']
            proof=t.observer.proof(frame,ticket)
            return t.observer.decoder.state(frame,proof,ticket)
        def owned(frame):state(frame);return True
        def restored(frame):need(state(frame)['override'] is False);return True
        return IOSEmoteCleanup(PrivateFeatureState(self.root/'ios-emote-cleanup-inputs.json'),t.sources,t.normal,
            validate_owned=owned,validate_restored=restored)

    def cleanup(self):
        t=self.t;t.activate('cleanup');self.cleanup_owner=self.cleanup_inputs();self.cleanup_owner.close()
        t.samples.drain();self.scope.cleanup()
        refresh(self.scope,self.pointers,self.keys,clock=self.scope.monotonic,sleep=self.scope.sleep)
        self.entities.capture();self.entities.closed(self.scope)
        self.files.capture('absent',self.scope.state['fileOwnership'])
        self.current=self.frames.capture('cleanup')
        self.public=t.observer.observe(len(t.observer.state['records']),retired=True)
        self.observation=t.observer.original(t.observer.state['records'][-1])
        self.pointers.capture();self.keys.capture()
        self.original=dict(observation=self.observation,sources=t.sources.store.read(),peers=None,scope=self.scope.snapshot(),
            fileReceipts=self.files.store.read(),sampleOwners=deepcopy(self.observation['sampleOwners']),
            inputOwners=dict(cleanup=self.cleanup_owner.store.read(),actions=t.actions.store.read(),background=None),
            entities=self.entities.store.read(),pointers=self.pointers.store.read())
        self.native=IOSEmoteCallbackNativeRetirement(PrivateFeatureState(self.root/'callback-native4.json'),self.root,self.scope.binding,self.scope.binding,
            self.scope.run,self.scope.role,t.phase.fixture_url,t.phase.previous['instance'],self.lock,self.lock,t.policy,
            dict(sources=t.sources.store.path,peers=None,files=self.files.store.path,entities=self.entities.store.path,pointers=self.pointers.store.path),lambda:True)
        self.native_ref=self.native.retain(self.original)
        self.rendered=IOSEmoteCallbackRenderedRetirement(PrivateFeatureState(self.root/'callback-rendered4.json'),self.native,self.frames)
        self.rendered_ref=self.rendered.retain(dict(nativeReference=self.native_ref,frames=self.frames.store.read(),initialReference=self.initial,currentReference=self.current))
        self.keyed=IOSEmoteCallbackKeyedRetirement(PrivateFeatureState(self.root/'callback-keyed4.json'),self.rendered,self.keys)
        self.keyed_ref=self.keyed.retain(dict(renderedReference=self.rendered_ref,keys=self.keys.store.read()))
        return self.keyed_ref
