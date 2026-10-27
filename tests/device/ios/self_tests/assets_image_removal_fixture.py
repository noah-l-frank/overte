"""Fresh normal marker -> Model -> normal Delete ordering on one entity tree.

The original marker baseline is acquired before any Model import. Its old
cleanup invariant therefore remains unchanged after the owned Model is really
removed. Qt/parser/raster are declared models; original QML, staged JavaScript,
input/WAL/raw/PNG files and independent weak objects execute.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import uuid
from types import SimpleNamespace
import weakref
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import canonical
from ios.adapters.assets_marker_owner import OwnedAssetsMarker
from ios.adapters.create_marker_files import OwnedCreateMarkerFiles
from ios.adapters.create_marker_scope import marker_name
from ios.adapters.create_originals import IOSCreateOriginals
from ios.self_tests import assets_image_combined_fixture as combined
from ios.self_tests import assets_model_removal_fixture as removal
from ios.self_tests.assets_reply_fixture import RUN,TICKET,URL
from ios.self_tests.test_ios_create_marker_scope import MarkerScopeTests
from ios.self_tests.create_product_controls_fixture import ProductControls


class Product(removal.Product):
    def delete(self):
        identity=self.selected()['id'];super().delete()
        rows=[row for _weak,row in self.b.marker_domain.entity_rows if row['id']==identity]
        assert len(rows)==1
        self.b.marker_domain.entity_event('removed',rows[0])


class Boundary(combined.CombinedBoundary,removal.Boundary):
    marker_domain=None
    def exchange(self,value):
        before=set(self.model_birth_rows);result=super().exchange(value)
        if self.marker_domain is not None:
            for identity in set(self.model_birth_rows)-before:
                row=deepcopy(self.model_birth_rows[identity]);self.marker_domain.entity_event('inserted',row)
                self.marker_domain.entity_rows.append((weakref.ref(self.entities[identity]),row))
        return result
    def state(self,request_id=None):
        value=super().state(request_id)
        if self.marker_domain is not None:self.marker_domain.include_marker(value)
        # This fresh controller model reports its actual current visible roots,
        # including the ordinary Home close. It never rewrites saved packets.
        product=self.create_product
        value['source']['tabletShown']=self.host_state['pageAlive'] or (product is not None and any(
            not row['destroyed'] and row.get('visible',False) and row.get('active',False) for row in product.roots)) or (
            self.marker_domain is not None and self.marker_domain.io.qt.opened)
        return value
    def attach_create(self):
        self.create_product=Product(self)
        self.create_widgets=ProductControls(SimpleNamespace(product=self.create_product,domain=SimpleNamespace(time=0)),self.normal_instance)


class ParsedFixture(combined.ParsedFixture):boundary_type=Boundary


class Domain(combined.CombinedMarkerDomain):
    def attach_readers(self,scope):
        super().attach_readers(scope)
        # One fresh host producer for Marker/Model/image acquisition. The
        # native producer keeps its original independent5000ms offset.
        scope.epoch_ms=lambda:self.driver.clock()+5000
    def current(self):return self.driver.state()
    def include_marker(self,value):
        source=value['source'];entities=source['entities'];tree=source['tree']
        if self.running:
            row=deepcopy(self.marker);row.update(createdEpochUs=row['lastEditedEpochUs'],shape='',modelURL='',textures='',locked=False,
                lastEditedBy=source['localSessionId'],model={},voxels={})
            entities.append(row);raw=canonical(row)
            tree['entities'].append(dict(id=row['id'],hostType=row['hostType'],ready=True,createdEpochUs=row['createdEpochUs'],
                lastEditedEpochUs=row['lastEditedEpochUs'],lastEditedAfterEpochUs=row['lastEditedEpochUs'],semanticBytes=len(raw),semanticSha256=hashlib.sha256(raw).hexdigest()))
        entities.sort(key=lambda row:row['id']);tree['entities'].sort(key=lambda row:row['id']);tree['totalEntities']=len(entities)
        revision=self.driver.entity_revision+(0 if self.worker is None else 1 if self.running else 2)
        tree.update(revisionBefore=revision,revisionAfter=revision)
        source['tabletShown']=source['tabletShown'] or self.io.qt.opened


class Fixture(combined.Fixture):
    def __init__(self,test,directory):
        self.f=ParsedFixture(directory);test.addCleanup(self.f.close)
        test.enterContext(patch('adapters.asset_backend_client.build_opener',return_value=self.f))
        template=MarkerScopeTests();template.root=directory;template.lock=self.f.lock
        scope=template.owner(binding=self.f.files.binding)
        scope.run,scope.role,scope.namespace,scope._version=RUN,'primary','assets',3;scope.fixture_url,scope.ticket=URL,TICKET
        scope.store=PrivateFeatureState(directory/marker_name('primary','assets'));scope.previous=scope.store.read();scope.guard=lambda:self.f.boundary.live
        scope.files=OwnedCreateMarkerFiles(None,scope.marker_store('files'),scope.binding)
        scope.originals=IOSCreateOriginals(directory,scope.binding,RUN,'primary',scope.guard,scope.storage_intent,kind='inputs',namespace='assets-marker')
        self.scope=scope;self.domain=Domain(scope,self.f.boundary);self.f.boundary.marker_domain=self.domain
        self.marker=OwnedAssetsMarker(scope,PrivateFeatureState(directory/('ios-assets-marker-'+RUN+'-primary.json')))
        self.marker.reserve();self.marker.prepare()
        self.model,self.baking=self.f.prepared();self.parsed=self.f.parsed(self.model,self.baking);self.parsed.reserve();self.proof=self.parsed.observe()
        self.model.usage.close_clients();self.image_sources=None
    def attach_removal(self):self.f.boundary.attach_create()
    def sample(self,request):
        owner,source=super().sample(request)
        assert owner.previous is None and owner.state is None
        owner.epoch_ms=lambda:self.f.boundary.clock()+5000
        return owner,source


class RemovalImageSources(combined.ImageSources):
    def __init__(self,fixture):
        self.present_policy=None
        super().__init__(fixture);self.gpu=RemovalImageGpu(self)
    def regions(self):
        if self.f.proof['entityId'] in self.b.entities:
            policy=super().regions();self.present_policy=deepcopy(policy);return policy
        # This is only a proposed crop from the actual earlier mesh. It never
        # supplies a current model, bounds observation, pixel or image verdict.
        assert self.present_policy is not None
        return deepcopy(self.present_policy)


class RemovalImageGpu:
    """Existing native model per ticket, one actual service sequence/clock.

    Matches FeatureCompletedFrames request-local retired/holder state. Old
    slots remain owned; a new read cannot bypass their undrained callbacks.
    """
    def __init__(self,source):
        self.source=source;self.slots={};self.last=None;self.sequence=0;self.frame=0
    def drained(self,slot):
        return slot.request is None or (slot.retired and not slot.gpu_pending and not (
            slot.held and (slot.no_fence or slot.clock<slot.callback_due)))
    def send(self,query):
        request=query['requestId']
        if request not in self.slots:
            slot=combined.ImageGpu(self.source)
            original=slot.fault
            def decorate(value,slot=slot,original=original):
                original(value)
                if 'renderTrace' in value.get('source',{}):value['source']['renderTrace']['frameId']=slot.original_frame_id
            slot.fault=decorate;self.slots[request]=slot
        slot=self.slots[request];self.last=slot;slot.sequence=self.sequence
        if query['operation']=='read' and slot.request is None:
            # The real source refuses a second active/undrained acquisition.
            # Do not reset or discard another request's retained World state.
            assert all(other is slot or self.drained(other) for other in self.slots.values())
            self.frame+=1;slot.frame_index=self.frame;slot.original_frame_id=uuid.uuid4().hex
        slot.send(query);self.sequence=slot.sequence
    def original(self):
        self.last.sequence=self.sequence;raw=self.last.original();self.sequence=self.last.sequence;return raw
