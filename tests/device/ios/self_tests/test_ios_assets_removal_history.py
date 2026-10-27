"""Validated native origin2/3 compatibility for the existing removal predicate.

These are pure predicate cases, without normal input, file-owner qualification,
a native parser, renderer or device. The connected flow remains separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_model_origin as origin
from ios.adapters.assets_model_removal import OwnedAssetsModelRemoval
from ios.self_tests.test_ios_assets_model_origin import Boundary,RUN
from ios.self_tests import test_ios_create_state as create


class AssetsRemovalHistoryTests(unittest.TestCase):
    def owner(self,version):
        b=Boundary();b.state['history']['assetModelOriginHistoryVersion']=version;b.row['resourceObjectAlive']=True
        if version==3:b.state['history']['geometries']=[dict(id='4'*32,readerId=b.row['id'],mappingIds=[],kind='resource',
            born=dict(epochMs=b.epoch+9,monotonicMs=9),alive=True,destructionObserved=None)]
        first=b.reader().read(RUN)
        before=create.version2(create.packet());create.add_model(before);create.version2(before)
        b.state['models']=[];b.state['tree'].update(entities=[],totalEntities=0,revisionBefore=2,revisionAfter=2)
        b.row['resourceAlive']=False;last=b.reader().read(RUN)
        origin.original(first);origin.original(last)
        after=create.version2(create.packet());after['source']['tree']=deepcopy(last['source']['tree'])
        work=dict(source=dict(entityLifetimes=dict(complete=True,entities=[dict(id=create.ID,destroyed=True,models=[dict(destroyed=True)])])),requestId='ios-'+'7'*32)
        frames={1:dict(originals=dict(createAfter=before)),2:dict(originals=dict(createAfter=after,origin=last,work=work))}
        owner=object.__new__(OwnedAssetsModelRemoval);owner.model=SimpleNamespace(state=dict(creation=dict(proof=dict(entityId=create.ID))))
        owner.parsed=SimpleNamespace(state=dict(sourceIndex=1),frame=lambda _:dict(originals=dict(origin=first)))
        owner.sources=SimpleNamespace(state=dict(frames=[dict(index=1),dict(index=2)]),_cached=[frames[1],frames[2]],originals=SimpleNamespace(expand=lambda x:x))
        owner.state=dict(baseline=1,observations=[2],inputs=[dict(controlId='create.delete',command=dict(commandId='actual-owned-delete'))])
        return owner,frames
    def test_literal_history_two_and_validated_three_retain_identical_original_cache_responsibility(self):
        for version in (2,3):
            owner,frames=self.owner(version);original=deepcopy(frames);observed=owner.removed()
            self.assertEqual(original,frames);self.assertEqual('actual-owned-delete',observed['inputCommandId'])
            self.assertEqual([dict(id='1'*32,originalLeaseAlive=False,objectAlive=True,hfmAlive=True)],observed['resources'])
            self.assertFalse(observed['resourceRetirementAvailable'])
    def test_legacy_without_qobject_or_unknown_versions_cannot_supply_known_resource_absence(self):
        for version in (1,4,True,2.0):
            owner,frames=self.owner(2);frames[2]['originals']['origin']['source']['history']['assetModelOriginHistoryVersion']=version
            with self.subTest(version=version),self.assertRaises(NativeUIError):owner.removed()
    def test_same_version_without_actual_model_death_or_expected_resource_membership_is_not_removal(self):
        for version in (2,3):
            for fault in ('entity-still-present','model-still-alive','missing-original-resource'):
                owner,frames=self.owner(version)
                if fault=='entity-still-present':frames[2]['originals']['createAfter']['source']['tree']=deepcopy(frames[1]['originals']['createAfter']['source']['tree'])
                elif fault=='model-still-alive':frames[2]['originals']['work']['source']['entityLifetimes']['entities'][0]['models'][0]['destroyed']=False
                else:frames[2]['originals']['origin']['source']['history']['downloads']=[]
                with self.subTest(version=version,fault=fault),self.assertRaises(NativeUIError):owner.removed()
