"""Declared native callback/scene boundary with real Geometry/HFM membership.

No parser, renderer, native executable, device, transport or whole flow runs.
The original paired end case separately exercises normal QML and its raw WAL.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import base64
import hashlib
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests.assets_paired_model_delivery_fixture import DeliveredModel,GeometryDelivery,Scene


class Holder:pass


class AssetsPairedModelDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.entity=SimpleNamespace(properties=dict(modelURL='atp:/actual-owned/stand.fbx'))
        self.model=DeliveredModel();hfm=Holder();geometry=Holder()
        geometry.hfm=hfm;geometry.token=Holder();geometry.mesh=Holder();geometry.material=Holder()
        self.model.geometry=geometry;self.model.origin_hfm=hfm
        raw=b'Original loader-boundary bytes, no requested success flag'
        self.original=dict(id='d'*32,kind='model',requestedUrl=self.entity.properties['modelURL'],
            effectiveUrl='atp:'+hashlib.sha256(raw).hexdigest(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
            base64=base64.b64encode(raw).decode(),readerKnown=True,modelKnown=True,invokeAccepted=True)
        self.original.update({key:dict(epochMs=1900000000000+index,monotonicMs=index) for index,key in enumerate(
            ('received','readerCreated','runEntered','queued','invokeReturned','deliveryEntered','deliveryReturned','runReturned'),1)})
        self.scene=Scene()
    def delivery(self,original=None):return GeometryDelivery('actual-created-entity',self.entity,self.model,self.original if original is None else original)

    def test_actual_delivered_geometry_and_allocated_scene_items_supply_separate_loaded_and_added_states(self):
        delivery=self.delivery();self.assertFalse(self.model.loaded);self.assertFalse(self.model.added)
        actual=delivery.complete();self.assertIs(self.model,actual);self.assertTrue(actual.loaded);self.assertFalse(actual.added)
        self.assertIs(actual.geometry,actual.render_geometry);self.assertIs(actual.origin_hfm,actual.render_geometry.hfm)
        self.assertEqual(self.original,actual.download)
        self.scene.add('actual-created-entity',actual);self.assertTrue(actual.added)
        self.assertEqual(['scene-item-allocated'],[row['kind'] for row in self.scene.events])
        self.scene.remove('actual-created-entity');self.assertFalse(actual.added);self.assertTrue(actual.loaded)
        self.assertEqual(['scene-item-allocated','scene-item-removed'],[row['kind'] for row in self.scene.events])

    def test_withheld_callback_cannot_become_loaded_from_repeated_getter_or_scene_ack(self):
        delivery=self.delivery();before=deepcopy(delivery.original)
        for _ in range(16):
            self.assertFalse(self.model.loaded);self.assertFalse(self.model.added)
            with self.assertRaises(NativeUIError):self.scene.add('actual-created-entity',self.model)
        self.assertFalse(delivery.completed);self.assertEqual(before,delivery.original);self.assertEqual({},self.scene.items)
        self.assertIsNone(self.model.render_geometry)

    def test_delivered_hfm_without_actual_scene_allocation_stays_unadded(self):
        self.delivery().complete();before=self.model.render_geometry
        for _ in range(16):self.assertTrue(self.model.loaded);self.assertFalse(self.model.added)
        self.assertIs(before,self.model.render_geometry);self.assertEqual([],self.scene.events)
        self.scene.add('actual-created-entity',self.model);self.assertTrue(self.model.added)

    def test_foreign_original_body_or_incomplete_delivery_refuses_before_model_or_scene_change(self):
        for name in ('hash','size','body','foreign-url','not-accepted','not-returned'):
            value=deepcopy(self.original)
            if name=='hash':value['sha256']='0'*64
            elif name=='size':value['bytes']+=1
            elif name=='body':value['base64']=base64.b64encode(b'foreign actual body').decode()
            elif name=='foreign-url':value['requestedUrl']='atp:/foreign/model.fbx'
            elif name=='not-accepted':value['invokeAccepted']=False
            else:value['deliveryReturned']=None
            with self.subTest(name=name),self.assertRaises(NativeUIError):self.delivery(value)
            self.assertIsNone(self.model.render_geometry);self.assertEqual({},self.scene.items)

    def test_changed_geometry_or_hfm_before_real_callback_cannot_adopt_old_delivery(self):
        delivery=self.delivery();old=self.model.geometry.hfm;self.model.geometry.hfm=Holder()
        with self.assertRaises(NativeUIError):delivery.complete()
        self.assertFalse(self.model.loaded);self.assertFalse(delivery.completed);self.assertEqual({},self.scene.items)
        self.model.geometry.hfm=old;self.model.geometry=Holder()
        with self.assertRaises(NativeUIError):delivery.complete()
        self.assertIsNone(self.model.render_geometry)

    def test_duplicate_delivery_or_wrong_entity_scene_allocation_cannot_repeat_or_rebind(self):
        delivery=self.delivery();delivery.complete()
        with self.assertRaises(NativeUIError):delivery.complete()
        with self.assertRaises(NativeUIError):self.scene.add('foreign-entity',self.model)
        self.assertEqual({},self.scene.items);self.scene.add('actual-created-entity',self.model)
        before=deepcopy(self.scene.events)
        with self.assertRaises(NativeUIError):self.scene.add('actual-created-entity',self.model)
        self.assertEqual(before,self.scene.events)
