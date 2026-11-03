"""Fresh combined normal Assets/Create/Marker/Image and independent peer model.

This is a producer composition selected before the first owner/capture. It
never imports a primary observation into the peer, copies old frame facts or
releases cached resources as adapter cleanup. Native/Qt/parser/GPU are models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
from types import SimpleNamespace
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.adapters.assets_baked_tree import OwnedAssetsBakedTree
from unittest.mock import patch
from adapters.native_feature_observation import need
from ios.adapters.assets_selected_profile import SelectedAssetsFiles,SelectedAssetsScene
from ios.self_tests import assets_upload_fixture as upload
from ios.self_tests import assets_geometry_release_fixture as geometry
from ios.self_tests import assets_image_removal_fixture as image
from ios.self_tests import assets_peer_fixture as peer
from ios.self_tests import assets_baked_tree_fixture as baked
from ios.self_tests.assets_reply_fixture import RUN,TICKET,URL
from ios.self_tests.assets_image_pool_flow_fixture import Boundary as PoolBoundary,Fixture as PoolFixture
from ios.self_tests.assets_paired_model_delivery_fixture import DeliveredModel,GeometryDelivery,Scene


class DomainEntities(dict):
    """Publish only actual normal controller writes/deletes to a second store."""
    def __init__(self,remote,scene):super().__init__();self.remote,self.scene=remote,scene
    def __setitem__(self,identity,entity):
        super().__setitem__(identity,entity);self.remote.receive(identity,deepcopy(entity.properties))
    def pop(self,identity,*default):
        existed=identity in self;value=super().pop(identity,*default)
        if existed:self.scene.remove(identity);self.remote.removed(identity)
        return value
    def __delitem__(self,identity):
        super().__delitem__(identity);self.scene.remove(identity);self.remote.removed(identity)


class PeerWorld(peer.PeerWorld):
    def removed(self,identity):
        # The actual domain message deletes the peer's entity/model. A model
        # resource cache is a different real owner and is deliberately retained.
        need(identity in self.entities and identity in self.models)
        self.deliveries.append(dict(id=identity,event='removed'))
        self.entities.pop(identity);self.models.pop(identity);self.entity_revision+=1


class Boundary(PoolBoundary,image.Boundary,baked.Boundary):
    MODEL_TYPE=DeliveredModel
    AUTO_MODEL_DELIVERY=True
    AUTO_SCENE_ALLOCATION=True
    def __init__(self,directory):
        self.model_deliveries={};self.scene=Scene()
        super().__init__(directory);need(not self.entities and not self.models)
        self.peer=PeerWorld(self);self.entities=DomainEntities(self.peer,self.scene)
    def consume(self,identity,entity):
        # The normal QML API already created this real entity. Existing loader
        # boundaries produce the actual downloaded body and Geometry/HFM first.
        super().consume(identity,entity)
        actual=self.models[identity]
        delivery=GeometryDelivery(identity,entity,actual,self.origin_rows[identity])
        self.model_deliveries[identity]=delivery
        if self.AUTO_MODEL_DELIVERY:self.deliver_model(identity)
    def deliver_model(self,identity):
        model=self.model_deliveries[identity].complete()
        if self.AUTO_SCENE_ALLOCATION:self.allocate_model_scene(identity)
        return model
    def allocate_model_scene(self,identity):
        need(identity in self.entities);self.scene.add(identity,self.models[identity])


class ParsedFixture(PoolFixture,baked.Fixture):
    boundary_type=Boundary
    def __init__(self,directory,*,selected,lock):
        # Exact existing lock object nests real ownership rather than creating
        # a second lock instance with the same path or returning a no-op scope.
        def canonical(path):
            need(path.parent==directory and path.name in ('assets.lock','script-feature-sources.lock'))
            lock.assert_held();return lock
        with (patch.object(upload,'ScriptSourceLock',side_effect=canonical),
              patch.object(geometry,'ScriptSourceLock',side_effect=canonical),
              patch.object(upload,'OwnedAssetsFiles',partial(SelectedAssetsFiles,selection=selected))):
            super().__init__(directory)
        need(self.lock is lock and self.files.selection is selected)
        self.boundary.peer.resolve_model=self.resolve_model

    def prepared(self):
        # Fresh actual normal upload/bake/import goes through the existing
        # canonical operation recipe, not seeded-prefix parsed test setup.
        self.boundary.reads.resource='asset-stand.fbx';parts=self.parts()
        runtime=IOSAssetsRuntime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:None),monotonic=self.boundary.monotonic)
        with patch('adapters.asset_backend_client.build_opener',return_value=self):
            runtime._assets_upload_model_bytes('declared-existing-parts',RUN,'primary',self.files.url,TICKET,self.lock,self.backend.config,parts=parts)
        self.normal_parts=parts
        return parts['model'],parts['baking']


class CombinedImageFixture(image.Fixture):
    def __init__(self,test,directory,*,selected,lock):
        # Same existing marker-before-model constructor order. The canonical
        # fresh upload recipe already reserves/observes Parsed exactly once;
        # reuse that actual owner instead of reserving its nonempty WAL again.
        self.f=ParsedFixture(directory,selected=selected,lock=lock);test.addCleanup(self.f.close)
        test.enterContext(patch('adapters.asset_backend_client.build_opener',return_value=self.f))
        template=image.MarkerScopeTests();template.root=directory;template.lock=self.f.lock
        scope=template.owner(binding=self.f.files.binding)
        scope.run,scope.role,scope.namespace,scope._version=RUN,'primary','assets',3;scope.fixture_url,scope.ticket=image.URL,TICKET
        scope.store=PrivateFeatureState(directory/image.marker_name('primary','assets'));scope.previous=scope.store.read();scope.guard=lambda:self.f.boundary.live
        scope.files=image.OwnedCreateMarkerFiles(None,scope.marker_store('files'),scope.binding)
        scope.originals=image.IOSCreateOriginals(directory,scope.binding,RUN,'primary',scope.guard,scope.storage_intent,kind='inputs',namespace='assets-marker')
        self.scope=scope;self.domain=image.Domain(scope,self.f.boundary);self.f.boundary.marker_domain=self.domain
        self.marker=image.OwnedAssetsMarker(scope,PrivateFeatureState(directory/('ios-assets-marker-'+RUN+'-primary.json')))
        self.marker.reserve();self.marker.prepare()
        self.model,self.baking=self.f.prepared();self.parsed=self.f.normal_parts['parsed']
        need(self.parsed.model is self.model and self.parsed.baking is self.baking and self.parsed.state['phase']=='observed')
        self.proof=self.parsed.observe()  # Actual unchanged cold/current reader, no expected result.
        # The original parsed backend input exists before normal server Delete.
        # Independent loaded local/peer cache resources remain genuine owners.
        tree=OwnedAssetsBakedTree(self.parsed,PrivateFeatureState(self.f.path('baked-tree')),lock=self.f.lock)
        self.f.baked_tree=tree;tree.reserve();tree.browse();tree.rename();tree.delete();tree.deletion()
        self.model.usage.close_clients();self.image_sources=None


class SelectedSceneEndpoint(peer.SceneEndpoint):
    def __init__(self,*args,selected,lock,**kwargs):
        # The real selected role binding is chosen before owner()/FIRST query.
        self.selected=selected
        role=kwargs.get('role',args[3] if len(args)>3 else None);need(role in ('primary','actor','actor-primary'))
        target_role='actor' if role=='actor' else 'primary'
        kwargs.setdefault('pid',int(selected.context['roles'][target_role]['binding']['processIdentity']))
        def canonical(path):need(path==lock.path);lock.assert_held();return lock
        with patch.object(peer,'ScriptSourceLock',side_effect=canonical):super().__init__(*args,**kwargs)
        target_role='actor' if self.role=='actor' else 'primary'
        info=selected.context['roles'][target_role]
        need(self.root==lock.path.parent and self.pid==int(info['binding']['processIdentity']))
        self.binding=deepcopy(info['binding']);self.lock=lock
    def owner(self):
        # Reuse the exact reader assembly, changing only the explicitly selected
        # Scene2 parent owner constructor; no packet/result/verdict is replaced.
        with patch.object(peer,'AssetsSceneSources',partial(SelectedAssetsScene,selection=self.selected)):
            return super().owner()


class PrimarySceneEndpoint(SelectedSceneEndpoint):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);need(self.role=='primary' and not self.queries)
        self.world=self.boundary
