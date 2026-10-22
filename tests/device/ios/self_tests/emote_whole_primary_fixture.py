"""Whole primary owner over real host originals and modeled SDK/native sources.

The component assembly seam reuses actual owners; it returns no feature facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
from adapters.native_script_files import NativeScriptFiles
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_feature_observation import need
from ios.adapters.emote_actions import IOSEmoteActions
from ios.adapters.emote_feature import IOSEmoteFeature
from ios.adapters.emote_restoration_frames import IOSEmoteRestorationFrames
from ios.adapters.emote_runtime import IOSEmoteRuntime
from ios.self_tests.emote_active_observer_fixture import ActiveObserverFixture
from ios.self_tests.emote_active_actor_fixture import ACTOR
from ios.self_tests.emote_normal_w3c_fixture import normal_tablet
from ios.self_tests.emote_pointer_fixture import PointerDomain
from ios.self_tests.emote_keys_fixture import KeyDomain
from ios.self_tests.marker_entities_fixture import EntityDomain
from ios.self_tests.test_ios_emote_sources import BINDING,RUN
from ios.self_tests.test_ios_installed_code import InstalledCodeTests
from self_tests.test_native_script_files import Boundary as FileBoundary


class WholePrimaryFixture:
    def __init__(self,test):
        f=self.target=ActiveObserverFixture(test,defer_setup=True);d,s=f.domain,f.scope
        self.pointer=PointerDomain(test,s,d);self.entities=EntityDomain(test,s,d);self.keys=KeyDomain(s,d)
        start=d.start
        def launched():start();d.paint()
        d.start=launched
        deliver=f.native.deliver
        def dispatched(query):
            self.pointer.boundary.touch('touch-begin',position=[80,48])
            result=deliver(query)
            self.pointer.boundary.touch('touch-end',position=[80,48]);return result
        f.native.deliver=dispatched;self.w3c,self.normal=normal_tablet(f,pointer=self.pointer.boundary)
        files=FileBoundary(f.root);files.root=d.files.root;self.files=files
        def file_send(query):
            d.sleep(.001);files.send(query);files.sample.update(requestedEpochMs=d.epoch(),capturedEpochMs=d.epoch())
        s.files.native=NativeScriptFiles(file_send,files.read,d.epoch,lambda:True,31,ios=True,monotonic=lambda:d.time,sleep=d.sleep)
        self.installed=InstalledCodeTests();self.installed.setUp();test.addCleanup(self.installed.doCleanups)
        self.installed.scope={key:value for key,value in ACTOR.items() if key!='processIdentity'}
        self.installed.binding=self.installed.make();self.installed.active()
        self.primary_installed=InstalledCodeTests();self.primary_installed.setUp();test.addCleanup(self.primary_installed.doCleanups)
        installation=self.primary_installed;installation.scope={key:value for key,value in BINDING.items() if key!='processIdentity'}
        installation.process['pid']=31;installation.native.clock_source['processId']=31
        installation.native.mutate=lambda value:value.update(processId=31)
        from ios.adapters.bundle_observation import NativeBundleObservation
        n=installation.native
        installation.reader=NativeBundleObservation(n.send,n.original,lambda:True,31,lambda:dict(n.clock_source),
            monotonic=lambda:n.clock,sleep=n.sleep)
        installation.binding=installation.make();installation.active()
        current=self
        class Runtime(IOSEmoteRuntime):
            def state_path(_self,selector):
                need(selector in ('primary','actor'));return f.root/'session.json' if selector=='primary' else current.installed.store.path.with_name('session.json')
            def _sources(_self,selector):
                need(selector=='primary');result=f.runtime_sources('owned');observer=result['observer']
                observer.create_entities=lambda _:current.entities.reader
                observer.pointer_state=lambda _:current.pointer.owner().pointer
                observer.world_web_keys=lambda _:current.keys.reader();observer.geometry=current.keys.geometry
                result.update(client=current.w3c,session=BINDING['sessionId']);return result
            def _existing(_self,selector):
                need(selector in ('primary','actor'))
                installation=current.primary_installed if selector=='primary' else current.installed
                scope=deepcopy(installation.scope)
                return None,scope['sessionId'],dict(sessionId=scope['sessionId']),{},scope
            def _emote_sources(_self,selector,client,run,role,root,lock):
                need(selector=='primary' and run==RUN and role=='primary' and root==f.root and lock is f.lock)
                return f.sources
            def _emote_actions(_self,selector,sources):
                need(selector=='primary' and sources is f.sources)
                return IOSEmoteActions(PrivateFeatureState(f.root/'ios-emote-inputs.json'),sources,current.normal)
            @contextmanager
            def existing_input_session(_self,selector):
                need(selector=='primary');yield
        self.runtime=object.__new__(Runtime);self.runtime.adapter=SimpleNamespace(_binding=lambda selector,*_args:(current.primary_installed if selector=='primary' else current.installed).make())
        self.restoration=IOSEmoteRestorationFrames(self.runtime,'primary',s,f.root,f.lock,epoch_ms=s.epoch_ms,monotonic=s.monotonic,sleep=s.sleep)
        self.parts=dict(own=self.runtime._sources('primary'),primary=self.runtime._sources('primary'),sources=f.sources,scope=s,
            peers=None,samples=f.samples,observer=f.observer,restoration=self.restoration)
        class Flow(IOSEmoteFeature):
            def components(_self):
                need(_self.state is not None and _self.state['binding']==BINDING and _self.state['phaseInstance']==f.phase.previous['instance'])
                return current.parts
        self.flow=Flow(self.runtime,'primary',f.client,RUN,'primary',f.root,f.policy,actor_selector='actor',
            epoch_ms=s.epoch_ms,monotonic=s.monotonic,sleep=s.sleep)
        # All actual child owners share this exact SDK serialization instance.
        self.flow.lock=self.flow.primary_lock=f.lock

    def call(self,verb,**inputs):return self.target.activate(verb,**inputs)
