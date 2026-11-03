"""Declared normal Geometry delivery and scene allocation for paired models.

This models the native boundaries, not a native parser or renderer. Actual
normal QML creates the entity; existing loader callbacks create Geometry/HFM
holders and their original downloaded bytes. Getter reads never make progress.
Loaded state derives from delivered Geometry, and scene state from allocated
items. No test supplies an expected loaded/added flag or result DTO.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import weakref
from adapters.native_feature_observation import need


class Scene:
    """Actual host item membership; independent weak refs avoid extra owners."""
    def __init__(self):self.items={};self.sequence=0;self.events=[]
    def contains(self,identity,model):
        item=self.items.get(identity)
        return item is not None and item['model']() is model and item['geometry']() is model.render_geometry
    def add(self,identity,model):
        need(identity not in self.items and model.loaded and model.entity_id==identity and model.scene is None)
        geometry=model.render_geometry
        need(geometry.mesh is not None and geometry.material is not None and geometry.token is not None)
        self.sequence+=1
        self.items[identity]=dict(itemId=self.sequence,model=weakref.ref(model),geometry=weakref.ref(geometry))
        model.scene=self
        self.events.append(dict(kind='scene-item-allocated',entityId=identity,itemId=self.sequence))
    def remove(self,identity):
        item=self.items.pop(identity,None)
        if item is not None:
            self.events.append(dict(kind='scene-item-removed',entityId=identity,itemId=item['itemId']))


class DeliveredModel:
    """Counterpart of Model::isLoaded and actual addToScene membership."""
    def __init__(self):
        self.geometry=self.render_geometry=None;self.entity_id=None;self.scene=None;self.failure=None;self.download=None
    @property
    def loaded(self):return self.render_geometry is not None and self.render_geometry.hfm is not None
    @property
    def added(self):return self.scene is not None and self.scene.contains(self.entity_id,self)
    @property
    def failed(self):return self.failure is not None


class GeometryDelivery:
    """A pending actual callback owns its already-created geometry/body only."""
    def __init__(self,identity,entity,model,original):
        need(type(model) is DeliveredModel and model.entity_id is None and model.render_geometry is None)
        geometry=model.geometry
        need(geometry is not None and geometry.hfm is not None and geometry.hfm is model.origin_hfm
            and geometry.token is not None and geometry.material is not None and geometry.mesh is not None)
        need(original['kind']=='model' and original['requestedUrl']==entity.properties['modelURL']
            and original['readerKnown'] and original['modelKnown'] and original['invokeAccepted'] is True
            and all(original[key] is not None for key in ('received','readerCreated','runEntered','queued',
                'invokeReturned','deliveryEntered','deliveryReturned','runReturned')))
        raw=base64.b64decode(original['base64'],validate=True)
        need(raw and len(raw)==original['bytes'] and hashlib.sha256(raw).hexdigest()==original['sha256'])
        self.identity,self.model,self.geometry,self.hfm=identity,weakref.ref(model),weakref.ref(geometry),weakref.ref(geometry.hfm)
        self.original=deepcopy(original);self.completed=False
    def complete(self):
        need(not self.completed);model,geometry=self.model(),self.geometry()
        need(model is not None and geometry is not None and self.hfm() is not None
            and geometry is model.geometry and geometry.hfm is self.hfm() is model.origin_hfm
            and model.render_geometry is None and model.entity_id is None)
        model.render_geometry=geometry;model.entity_id=self.identity;model.download=deepcopy(self.original)
        self.completed=True;return model
