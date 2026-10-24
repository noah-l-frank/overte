"""Actual typed standalone SDK with the separate unadvertised Source owner factory."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import NativeFeatureObservation
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from ios.adapters import world_web_source,world_web_dom,world_web_work,world_web_geometry,world_web_keys,emote_world,pointer_state,create_entities
from ios.adapters.native_geometry import OriginalGeometry
from ios.adapters.world_web_sources import WorldWebSources
from ios.self_tests.world_web_source_boundary import SDK as SourceBoundary,RUN,EPOCH,URL


class SDK(SourceBoundary):
    def owner(self,store,lock,*,historical=False):
        if not hasattr(self,'native_send'):self.native.mutate=self.clock_packet
        clock=NativeFeatureObservation(getattr(self,'native_send',self.native.send),self.native.original,self.tick,lambda:True,self.pid,ios=True,monotonic=lambda:self.time,sleep=self.sleep)
        readers=dict(native=clock)
        def now():return clock.read(clock.sequence)['capturedEpochMs']
        for name,cls in (('ledger',world_web_source.IOSWorldWebSource),('document',world_web_dom.IOSWorldWebDOM),('world',emote_world.IOSEmoteWorld),
                         ('geometry',world_web_geometry.IOSWorldWebGeometry),('work',world_web_work.IOSWorldWebWork),('keys',world_web_keys.IOSWorldWebKeys),
                         ('pointer',pointer_state.IOSPointerState),('entities',create_entities.IOSCreateEntities)):
            readers[name]=cls(lambda q,name=name:self.send(name,q),lambda name=name:self.original(name),now,lambda:True,self.pid,monotonic=lambda:self.time,sleep=self.sleep)
        if getattr(self,'use_snapshot',False):
            from ios.self_tests.world_web_snapshot_fixture import SnapshotNative
            from ios.adapters.world_web_snapshot import IOSWorldWebSnapshot
            if getattr(self,'use_whole_snapshot',False):
                from ios.self_tests.world_web_whole_snapshot_fixture import WholeSnapshotNative as SnapshotNative
                from ios.adapters.world_web_whole_snapshot import IOSWorldWebWholeSnapshot as IOSWorldWebSnapshot
            from ios.adapters.world_web_surfaces import IOSWorldWebSurfaces
            from ios.self_tests.world_web_surfaces_fixture import CacheOriginals
            if not hasattr(self,'surface_cache'):
                self.surface_cache=CacheOriginals(clock_ms=self.tick,monotonic_ms=lambda:round(self.time*1000),pid=self.pid)
                self.surface_cache.reserve()
            readers['surfaces']=IOSWorldWebSurfaces(lambda q:self.send('surfaces',q),lambda:self.original('surfaces'),now,lambda:True,self.pid,monotonic=lambda:self.time,sleep=self.sleep)
            from ios.adapters.web_closures import IOSWebClosures
            readers['closures']=IOSWebClosures(lambda q:self.send('closures',q),lambda:self.original('closures'),now,lambda:True,self.pid,monotonic=lambda:self.time,sleep=self.sleep)
            if not hasattr(self,'snapshot_native'):self.snapshot_native=SnapshotNative(self,autodocument=True)
            readers['snapshot']=IOSWorldWebSnapshot(self.snapshot_native.send,self.snapshot_native.raw,now,lambda:True,self.pid,monotonic=lambda:self.time,sleep=self.sleep)
        readers['uikit']=OriginalGeometry(lambda q:self.send('uikit',q),lambda:self.original('uikit'),now,lambda:True,monotonic=lambda:self.time,sleep=self.sleep)
        readers['widgets']=self.native_widget(clock)
        client=object.__new__(Client);client.url=getattr(self,'fixture_url',URL).split('/runs/')[0];client.request=self.phase
        phase=PhaseFixtureReader(client,self.run,'world-web',epoch_ms=getattr(self,'host_epoch',self.epoch),monotonic=lambda:self.time)
        return WorldWebSources(store,lock,self.binding,self.run,getattr(self,'role','primary'),lambda:True,phase=phase,readers=readers,historical=historical,
            epoch_ms=getattr(self,'host_epoch',self.epoch),monotonic=lambda:self.time)
