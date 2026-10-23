"""Actual independent host owners composed under the whole Actor coordinator."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.native_script_files import NativeScriptFiles
from ios.adapters.emote_feature import IOSEmoteFeature
from ios.adapters.emote_restoration_frames import IOSEmoteRestorationFrames
from ios.adapters.emote_runtime import IOSEmoteRuntime
from ios.self_tests.emote_active_actor_fixture import ActiveActorFixture,ACTOR
from ios.self_tests.marker_entities_fixture import EntityDomain
from ios.self_tests.test_ios_emote_sources import BINDING,RUN
from ios.self_tests.test_ios_pointer_state import NativePointerBoundary
from ios.self_tests.emote_keys_fixture import KeyDomain
from self_tests.test_native_script_files import Boundary as FileBoundary


class WholeActorFixture:
    def __init__(self,test,primary,*,feature_type=IOSEmoteFeature):
        a=self.target=ActiveActorFixture(test,primary.target,defer_setup=True);d,s=a.domain,a.scope
        self.primary=primary;self.entities=EntityDomain(test,s,d);self.pointer=NativePointerBoundary()
        self.keys=KeyDomain(s,d,binding=ACTOR,role='actor')
        def tick():d.time+=.001;self.pointer.now=d.epoch();return self.pointer.now
        self.pointer.tick=tick;self.pointer.now=d.epoch()
        start=d.start
        def launched():start();d.paint()
        d.start=launched
        files=FileBoundary(a.root);files.root=d.files.root;self.files=files
        def file_send(query):
            d.sleep(.001);files.send(query);files.sample.update(processId=42,requestedEpochMs=d.epoch(),capturedEpochMs=d.epoch())
        s.files.native=NativeScriptFiles(file_send,files.read,d.epoch,lambda:True,42,ios=True,monotonic=lambda:d.time,sleep=d.sleep)
        current=self
        class Runtime(IOSEmoteRuntime):
            def state_path(_self,selector):
                need(selector in ('primary','actor'));return (primary.target.root if selector=='primary' else a.root)/'session.json'
            def _existing(_self,selector):return primary.runtime._existing(selector)
            def _sources(_self,selector):
                if selector=='primary':return primary.runtime._sources('primary')
                need(selector=='actor');result=a.runtime_sources('actor');observer=result['observer']
                observer.create_entities=lambda _:current.entities.reader
                def pointer(_clock):
                    reader=current.pointer.reader();reader.monotonic=lambda:d.time;return reader
                observer.pointer_state=pointer;observer.world_web_keys=lambda _:current.keys.reader();observer.geometry=current.keys.geometry;return result
            def _emote_sources(_self,selector,client,run,role,root,lock):
                need(selector=='primary' and run==RUN and role=='actor' and root==a.root/'primary-sdk-originals' and lock is primary.target.lock)
                return a.sources
            def _avatar_receive(_self,selector):need(selector=='actor');return a.receive_reader()
            @contextmanager
            def existing_input_session(_self,selector):need(selector=='actor');yield
        self.runtime=object.__new__(Runtime);self.runtime.adapter=primary.runtime.adapter
        a.runtime._sources=self.runtime._sources
        self.restoration=IOSEmoteRestorationFrames(self.runtime,'actor',s,a.root,a.lock,epoch_ms=s.epoch_ms,monotonic=s.monotonic,sleep=s.sleep)
        self.parts=dict(own=self.runtime._sources('actor'),primary=self.runtime._sources('primary'),sources=a.sources,scope=s,
            peers=a.peers,samples=a.samples,observer=a.observer,restoration=self.restoration)
        class Flow(feature_type):
            def components(_self):
                need(_self.state is not None and _self.state['binding']==ACTOR and _self.state['primaryBinding']==BINDING
                    and _self.state['phaseInstance']==a.phase.previous['instance'])
                return current.parts
        self.flow=Flow(self.runtime,'actor',a.client,RUN,'actor',a.root,a.policy,primary_selector='primary',
            epoch_ms=s.epoch_ms,monotonic=s.monotonic,sleep=s.sleep)
        self.flow.lock=a.lock;self.flow.primary_lock=primary.target.lock
