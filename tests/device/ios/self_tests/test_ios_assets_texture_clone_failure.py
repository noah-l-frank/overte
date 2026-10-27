"""Declared native allocation-failure stimulus through real host codecs.

The Python source model is explicit; no C++ exception, atomic or GPU executes.
Actual Python weak owners and a real MemoryError create the hidden-clone case.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import unittest
import weakref
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_texture_ownership as texture
from ios.self_tests.test_ios_assets_geometry_consumers import Holder
from ios.self_tests.test_ios_assets_model_origin import RUN
from ios.self_tests.test_ios_assets_texture_consumers import AssetsTextureConsumersTests


class AllocationFailure:
    def __deepcopy__(self,memo):raise MemoryError('declared native diagnostic scope-copy allocation failure')


class CloneFailureBoundary:
    """Native-source specification, not execution of Material.cpp."""
    def __init__(self):
        self.b=AssetsTextureConsumersTests().prepare();self.failed=False;self.deaths={}
        self.material=Holder();self.material.map=Holder();self.material.map.source=Holder()
        self.refs=[weakref.ref(self.material.map),weakref.ref(self.material.map.source)]
        self.b.mutate=self.observe

    def clone(self,scopes):
        clone=Holder();clone.map=self.material.map
        try:clone.scopes=deepcopy(scopes)
        except MemoryError:
            # Explicit native-boundary fail-closed expectation. The C++ sink
            # itself remains uncompiled and needs independent qualification.
            self.failed=True;clone.scopes=[]
        return clone

    def observe(self,packet):
        history=packet['source']['history']
        if self.failed:packet['source']['complete']=history['complete']=False
        for ref,row in zip(self.refs,history['textureOwnership']['nodes']):
            row['strongOwnersAlive']=ref() is not None
            if not row['strongOwnersAlive']:self.deaths.setdefault(row['id'],deepcopy(history['clock']))
            row['ownershipExpiryObserved']=deepcopy(self.deaths.get(row['id']))


class AssetsTextureCloneFailureTests(unittest.TestCase):
    def test_lost_clone_scopes_and_hidden_replacement_cannot_reuse_last_good_absence_authority(self):
        f=CloneFailureBoundary();reader=f.b.reader();first=reader.read(RUN);saved=deepcopy(first)
        clone=f.clone([AllocationFailure()]);self.assertEqual([],clone.scopes)
        clone.map=Holder();clone.map.source=Holder();hidden=weakref.ref(clone.map.source)
        f.material=None;gc.collect();current=reader.read(RUN)
        self.assertIsNotNone(hidden())
        self.assertEqual([False,False],[row['strongOwnersAlive'] for row in current['source']['history']['textureOwnership']['nodes']])
        self.assertIs(False,current['source']['complete']);self.assertEqual(current,reader.last)
        with self.assertRaises(NativeUIError):texture.consumers(current,f.b.row['id'])
        self.assertEqual(saved,first);self.assertIs(True,first['source']['complete'])

    def test_failure_before_first_query_stays_visible_after_new_good_publication(self):
        f=CloneFailureBoundary();failed=f.clone([AllocationFailure()]);reader=f.b.reader();first=reader.read(RUN)
        good=f.clone(['new legitimate scope']);self.assertEqual(['new legitimate scope'],good.scopes)
        second=reader.read(RUN)
        self.assertIs(False,first['source']['complete']);self.assertIs(False,second['source']['complete'])
        for packet in (first,second):
            with self.assertRaises(NativeUIError):texture.consumers(packet,f.b.row['id'])

    def test_successful_clone_keeps_original_sharing_groups_live_without_false_failure(self):
        f=CloneFailureBoundary();clone=f.clone(['original legitimate scope']);f.material=None;gc.collect()
        packet=f.b.reader().read(RUN);facts=texture.consumers(packet,f.b.row['id'])
        self.assertIs(True,packet['source']['complete']);self.assertFalse(f.failed)
        self.assertEqual([True,True],[row['strongOwnersAlive'] for row in facts['nodes']])
        self.assertFalse(facts['allKnownTextureOwnersGone']);self.assertIsNotNone(clone.map.source)
