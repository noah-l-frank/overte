"""Pure declared-source TextureRelease1 facts, without new input or native code."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import unittest
import weakref
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_texture_release as release,assets_texture_ownership as texture
from ios.adapters import assets_strong_release as strong
from ios.self_tests.test_ios_assets_geometry_consumers import Holder
from ios.self_tests.test_ios_assets_model_origin import RUN
from ios.self_tests.test_ios_assets_texture_consumers import AssetsTextureConsumersTests


class AssetsTextureReleaseFactsTests(unittest.TestCase):
    def packets(self):
        b=AssetsTextureConsumersTests().prepare();reader=b.reader();first=reader.read(RUN)
        lineage=dict(readerId=b.row['id'],sha256=b.row['sha256'],bytes=b.row['bytes'],processId=42,runId=RUN)
        return b,reader,first,lineage

    def test_actual_independent_source_refuses_absence_after_original_map_is_gone(self):
        b=AssetsTextureConsumersTests().prepare();map_holder=Holder();map_holder.source=Holder();independent=map_holder.source
        refs=[weakref.ref(map_holder),weakref.ref(map_holder.source)];dead={}
        def observe(packet):
            history=packet['source']['history']
            for ref,row in zip(refs,history['textureOwnership']['nodes']):
                row['strongOwnersAlive']=ref() is not None
                if not row['strongOwnersAlive']:dead.setdefault(row['id'],deepcopy(history['clock']))
                row['ownershipExpiryObserved']=deepcopy(dead.get(row['id']))
        b.mutate=observe;reader=b.reader();first=reader.read(RUN)
        lineage=dict(readerId=b.row['id'],sha256=b.row['sha256'],bytes=b.row['bytes'],processId=42,runId=RUN)
        del map_holder;gc.collect();second=reader.read(RUN)
        original,observed=release.texture_history(first,[second],lineage)
        self.assertFalse(observed[0]['allKnownTextureOwnersGone'])
        self.assertEqual([False,True],[row['strongOwnersAlive'] for row in observed[0]['nodes']])
        del independent;gc.collect();last=reader.read(RUN);saved=deepcopy((first,second,last))
        original,observed=release.texture_history(first,[second,last],lineage)
        self.assertTrue(observed[-1]['allKnownTextureOwnersGone'])
        for key in ('decoderCompletionAvailable','destructorCompletionAvailable','gpuCompletionAvailable','resourceRetirementAvailable'):
            self.assertFalse(observed[-1][key])
        self.assertEqual(saved,(first,second,last));self.assertTrue(original['nodes'][0]['strongOwnersAlive'])
        # Texture-only facts cannot replace the independently still-live
        # original mesh/material inventory required by the final composition.
        _,mesh=strong._texture_strong_history(first,[last],lineage)
        self.assertFalse(mesh[0]['allKnownStrongOwnersGone'])

    def test_positive_original_same_link_map_and_source_are_required(self):
        for fault in ('map-dead','source-dead','legacy4','no-source'):
            b=AssetsTextureConsumersTests().prepare();history=b.state['history'];inventory=history['textureOwnership']
            if fault in ('map-dead','source-dead'):
                row=inventory['nodes'][fault=='source-dead']
                row.update(strongOwnersAlive=False,ownershipExpiryObserved=deepcopy(row['born']))
            elif fault=='legacy4':history['assetModelOriginHistoryVersion']=4;history.pop('textureOwnership')
            else:inventory['nodes'].pop();inventory['links'][0]['sourceId']=''
            reader=b.reader();first=reader.read(RUN);last=reader.read(RUN)
            lineage=dict(readerId=b.row['id'],sha256=b.row['sha256'],bytes=b.row['bytes'],processId=42,runId=RUN)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):release.texture_history(first,[last],lineage)

    def test_foreign_body_reader_process_run_or_incompatible_profile_cannot_supply_ownership(self):
        for fault in ('sha','bytes','reader','pid','run','later4','empty-packets','too-many'):
            b,reader,first,lineage=self.packets();last=reader.read(RUN);packets=[last]
            if fault=='sha':lineage['sha256']='f'*64
            elif fault=='bytes':lineage['bytes']+=1
            elif fault=='reader':lineage['readerId']='f'*32
            elif fault=='pid':lineage['processId']=43
            elif fault=='run':lineage['runId']='b'*32
            elif fault=='later4':last['source']['history']['assetModelOriginHistoryVersion']=4;last['source']['history'].pop('textureOwnership')
            elif fault=='empty-packets':packets=[]
            else:packets=[last]*9
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):release.texture_history(first,packets,lineage)

    def test_later_link_to_an_older_actual_shared_group_preserves_global_identity(self):
        b=AssetsTextureConsumersTests().prepare();history=b.state['history'];inventory=history['textureOwnership']
        other=deepcopy(b.row);other['id']='f'*32;history['downloads'].append(other)
        parent=dict(deepcopy(history['geometries'][0]),id='e'*32,readerId=other['id']);history['geometries'].append(parent)
        history['consumerOwnership']['rows'].append(dict(deepcopy(history['consumerOwnership']['rows'][1]),id='b'*32,geometryId=parent['id']))
        older=[dict(deepcopy(row),id=id_*32) for row,id_ in zip(inventory['nodes'],('c','d'))]
        inventory['nodes']=older+inventory['nodes']
        inventory['links'].append(dict(deepcopy(inventory['links'][0]),id='e'*32,geometryId=parent['id'],mapId='c'*32,sourceId='d'*32,revision=1))
        reader=b.reader();first=reader.read(RUN);born=b.stamp()
        inventory['links'].append(dict(deepcopy(inventory['links'][0]),id='f'*32,mapId='c'*32,sourceId='d'*32,
            born=deepcopy(born),lastObserved=deepcopy(born),revision=3));inventory['revision']=3
        last=reader.read(RUN);lineage=dict(readerId=b.row['id'],sha256=b.row['sha256'],bytes=b.row['bytes'],processId=42,runId=RUN)
        original,observed=release.texture_history(first,[last],lineage)
        self.assertEqual(['8'*32,'9'*32],[row['id'] for row in original['nodes']])
        self.assertEqual(['c'*32,'d'*32,'8'*32,'9'*32],[row['id'] for row in observed[0]['nodes']])
        self.assertEqual(4,len(last['source']['history']['textureOwnership']['nodes']))

    def test_original_first_expiry_and_complete_registry_are_not_replaced_by_later_samples(self):
        for fault in ('first-expiry','resurrect','lost-link','stale-revision','old-clock'):
            b,reader,first,lineage=self.packets();death=b.stamp()
            for row in b.state['history']['textureOwnership']['nodes']:
                row.update(strongOwnersAlive=False,ownershipExpiryObserved=deepcopy(death))
            second=reader.read(RUN);third=reader.read(RUN);inventory=third['source']['history']['textureOwnership'];row=inventory['nodes'][0]
            if fault=='first-expiry':row['ownershipExpiryObserved']['epochMs']+=1
            elif fault=='resurrect':row.update(strongOwnersAlive=True,ownershipExpiryObserved=None)
            elif fault=='lost-link':inventory['links']=[]
            elif fault=='stale-revision':inventory['revision']-=1
            else:third=deepcopy(first)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):release.texture_history(first,[second,third],lineage)
