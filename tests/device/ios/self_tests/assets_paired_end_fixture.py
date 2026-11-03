"""One fresh actual normal Assets graph plus declared SDK/OS end boundaries.

No physical candidate/device/server/native compiler is exercised. Original QML,
staged marker JS, file/inode/raw/PNG owners, independent peer parser objects,
actual installed metadata and shared once-only end/CAS codecs execute.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import threading
from unittest.mock import patch
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from ios.self_tests import assets_upload_fixture,assets_image_combined_fixture,assets_image_removal_fixture
import uuid
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_feature_observation import need
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.assets_end_selection import select
from ios.adapters.assets_selected_runtime import SelectedAssetsRuntime
from ios.adapters.assets_paired_end import AssetsPairedLocalEnd
from ios.adapters.assets_model_removal import OwnedAssetsModelRemoval
from ios.adapters.assets_peer_owner import OwnedAssetsPeer
from ios.self_tests.assets_paired_end_sdk_fixture import SDKModels
from ios.self_tests.assets_paired_end_boundary_fixture import CombinedImageFixture,SelectedSceneEndpoint,PrimarySceneEndpoint
from ios.self_tests.assets_picker_fixture import RUN,TICKET,URL


class Fixture:
    def __init__(self,test,*,fault=''):
        self.test=test;self.roots={};self.locks={}
        for role in ('primary','actor'):
            directory=tempfile.TemporaryDirectory();test.addCleanup(directory.cleanup)
            root=Path(directory.name);root.chmod(0o700);self.roots[role]=root
            self.locks[role]=ScriptSourceLock(root/'script-feature-sources.lock')
        for role in ('actor','primary'):
            context=self.locks[role].held();context.__enter__();test.addCleanup(context.__exit__,None,None,None)
        self.sdk=SDKModels(test,self.roots,self.locks);self.sdk.fault=fault;self.sdk.install_transport(test)
        self.server=make_server('r'*64,'a'*64,adapter_token='d'*64);self.server.journal.clock=self.sdk.epoch
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):need(self.server.journal.register('assets')==RUN)
        self.server.journal.activate(RUN,TICKET,'baseline',{})
        self.thread=threading.Thread(target=lambda:self.server.serve_forever(poll_interval=.01),daemon=True);test.addCleanup(self.stop_server);self.thread.start()
        self.client=Client('http://127.0.0.1:'+str(self.server.server_address[1])+'/feature-fixture/v1','d'*64)
        self.url=self.client.url+'/runs/'+RUN+'/'
        # Choose fresh inputs BEFORE owner births; never rewrite an old source.
        for module in (assets_upload_fixture,assets_image_combined_fixture,assets_image_removal_fixture):test.enterContext(patch.object(module,'URL',self.url))
        self.phase=PhaseFixtureReader(self.client,RUN,'assets',epoch_ms=self.sdk.epoch,monotonic=self.sdk.monotonic)
        self.roles={role:dict(target=role,artifactRoot=str(root)) for role,root in self.roots.items()}
        self.selected=select(self.sdk.runtime,RUN,self.url,TICKET,self.roles,self.locks,phase=self.phase)
        self.runtime=SelectedAssetsRuntime(self.sdk.adapter,self.selected,phase=self.phase,monotonic=self.sdk.monotonic,epoch_ms=self.sdk.epoch)
        # All source classes, selected pair and both original lock objects are
        # chosen before any normal Files/Scene/Marker/native/image owner birth.
        self.image=CombinedImageFixture(test,self.roots['primary'],selected=self.selected,lock=self.locks['primary'])
        f=self.image.f;b=f.boundary;self.sdk.boundary=b
        parsed=self.image.parsed
        self.primary_endpoint=PrimarySceneEndpoint(f,parsed,self.roots['primary'],'primary',selected=self.selected,lock=self.locks['primary'])
        self.peer_primary=SelectedSceneEndpoint(f,parsed,self.roots['primary'],'actor-primary',selected=self.selected,lock=self.locks['primary'])
        self.actor_endpoint=SelectedSceneEndpoint(f,parsed,self.roots['actor'],'actor',selected=self.selected,lock=self.locks['actor'])
        for endpoint in (self.primary_endpoint,self.peer_primary,self.actor_endpoint):test.addCleanup(endpoint.close)
        self.sdk.actor_endpoint=self.actor_endpoint
        self.primary_scene=self.primary_endpoint.owner();self.primary_scene.reserve();self.primary_scene.capture(self.primary_scene.epoch_ms())
        self.peer=OwnedAssetsPeer(parsed,self.peer_primary.owner(),self.actor_endpoint.owner(),
            PrivateFeatureState(self.roots['actor']/('ios-assets-peer-'+RUN+'.json')),self.locks['actor'])
        self.peer.reserve();self.peer.observe()
        # Canonical four-owner runtime factory and genuine current raw codecs;
        # these records keep their actual held resources, not fabricated zeros.
        self.four=self.runtime._assets_image_lifetime_sources('primary',RUN,self.locks['primary'])
        for key in ('image_lifecycle_sources','image_processing_sources','image_storage_sources','image_pool_sources'):
            owner=self.four[key];owner.reserve();owner.capture(self.sdk.epoch())
        request='ios-'+uuid.uuid4().hex;self.sample,self.pixels=self.image.sample(request);self.policy=self.pixels.regions()
        self.sample.capture(TICKET,self.image.scope.epoch_ms());self.sample.qualify(self.policy)
        self.image.attach_removal()
        self.removal=OwnedAssetsModelRemoval(parsed,PrivateFeatureState(f.path('model-removal')),lock=self.locks['primary'])
        self.removal.reserve();self.removal.remove();self.removal.close_context();self.removal.close_parent_clients();f.baked_tree.close_clients()
        self.image.marker.cleanup()
        backend=f.normal_parts['backend']
        f_runtime=self.runtime
        first=f_runtime._assets_backend_checkpoint(backend,'paired-end-restore-first',TICKET)
        need(backend.quiescent_baseline(first));b.sleep(3.1)
        last=f_runtime._assets_backend_checkpoint(backend,'paired-end-restore-last',TICKET)
        need(backend.quiescent_baseline(last) and backend.restore('paired-end-restore-first','paired-end-restore-last') is not None)
        # Exact source requirements do not become relaxed when a native/cache
        # resource remains alive. The historical raw graph deliberately keeps
        # all those actual objects and old positive flags until independent end.
        self.tx=AssetsPairedLocalEnd(self.runtime,self.selected,self.locks)

    def stop_server(self):
        if self.thread.is_alive():self.server.shutdown()
        self.server.server_close()
        if self.thread.ident is not None:self.thread.join(timeout=2)
        need(not self.thread.is_alive())
    def freeze(self):
        self.server.journal.activate(RUN,uuid.uuid4().hex,'cleanup',{});self.server.journal.close(RUN)
        return self.tx.freeze(self.phase.status())
    def reopen_end(self):
        from ios.adapters.assets_end_selection import archive
        selected=archive(self.sdk.runtime,RUN,self.url,TICKET,self.roles,self.locks)
        runtime=SelectedAssetsRuntime(self.sdk.adapter,selected,monotonic=self.sdk.monotonic,epoch_ms=self.sdk.epoch)
        self.selected,self.runtime=selected,runtime;self.tx=AssetsPairedLocalEnd(runtime,selected,self.locks)
    def step_end(self):return self.tx.advance()
    def complete(self):
        for attempt in range(128):
            if self.step_end():return self.tx.completed()
            self.image.f.boundary.sleep(.1)
        need(False)
    def counts(self):
        return dict(stops=list(self.sdk.stops),sdk=deepcopy(self.sdk.calls),native=deepcopy(self.sdk.native_queries),
            input=deepcopy(self.image.f.boundary.inputs),server=deepcopy(self.image.f.requests))
