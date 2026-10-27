"""Host-only History5 wire/weak-sharing models; native C++ is not executed."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import copy,deepcopy
import gc
import json
import subprocess
import unittest
import weakref
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_model_origin as origin,assets_texture_ownership as texture,assets_strong_release
from ios.self_tests.test_ios_assets_geometry_consumers import Holder
from ios.self_tests.test_ios_assets_model_origin import RUN,AssetsModelOriginRuntimeTests
from ios.self_tests.test_ios_assets_strong_consumers import AssetsStrongConsumersTests
from self_tests.test_native_feature_observation import probe_source


class AssetsTextureConsumersTests(unittest.TestCase):
    def prepare(self,epoch=None):
        b=AssetsStrongConsumersTests().prepare(epoch);history=b.state['history'];history['assetModelOriginHistoryVersion']=5
        born=dict(epochMs=b.epoch+10,monotonicMs=10)
        history['textureOwnership']=dict(assetModelTextureOwnershipVersion=1,revision=2,
            nodes=[dict(id=id_*32,kind=kind,born=deepcopy(born),strongOwnersAlive=True,ownershipExpiryObserved=None)
                for id_,kind in (('8','map'),('9','source'))],
            links=[dict(id='a'*32,geometryId='4'*32,materialSlot=0,channel=0,mapId='8'*32,sourceId='9'*32,
                born=deepcopy(born),lastObserved=deepcopy(born),revision=2)])
        return b

    def test_actual_independent_map_and_source_holders_outlive_material(self):
        b=self.prepare();material=Holder();material.map=Holder();material.map.source=Holder()
        external_map=material.map;external_source=material.map.source
        refs=[weakref.ref(material.map),weakref.ref(material.map.source)];dead={}
        def observe(packet):
            history=packet['source']['history']
            for ref,row in zip(refs,history['textureOwnership']['nodes']):
                row['strongOwnersAlive']=ref() is not None
                if not row['strongOwnersAlive']:dead.setdefault(row['id'],deepcopy(history['clock']))
                row['ownershipExpiryObserved']=deepcopy(dead.get(row['id']))
        b.mutate=observe;reader=b.reader();first=reader.read(RUN);saved=deepcopy(first)
        del material;gc.collect();second=reader.read(RUN)
        self.assertFalse(texture.consumers(second,b.row['id'])['allKnownTextureOwnersGone'])
        del external_map;gc.collect();third=reader.read(RUN)
        self.assertEqual([False,True],[row['strongOwnersAlive'] for row in texture.consumers(third,b.row['id'])['nodes']])
        del external_source;gc.collect();last=reader.read(RUN);facts=texture.consumers(last,b.row['id'])
        self.assertTrue(facts['allKnownTextureOwnersGone'])
        for key in ('decoderCompletionAvailable','destructorCompletionAvailable','gpuCompletionAvailable','resourceRetirementAvailable'):
            self.assertIs(False,facts[key])
        self.assertEqual(saved,first)

    def test_old_empty_and_unlinked_inventories_do_not_establish_texture_absence(self):
        b=AssetsStrongConsumersTests().prepare()
        with self.assertRaises(NativeUIError):texture.consumers(b.reader().read(RUN),b.row['id'])
        for fault in ('empty','unlinked','map-only'):
            b=self.prepare();inventory=b.state['history']['textureOwnership']
            if fault=='empty':inventory.update(nodes=[],links=[],revision=0)
            elif fault=='unlinked':inventory['links']=[]
            else:inventory['nodes'].pop();inventory['links'][0]['sourceId']=''
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):texture.consumers(b.reader().read(RUN),b.row['id'])

    def test_invalid_membership_identity_clocks_and_limits_are_rejected(self):
        for fault in ('unknown6','bool-version','parent','slot','channel','source-kind','dangling','empty-map',
                'sentinel','duplicate-edge','future','backwards','alive-int','missing-death','live-death',
                'node-cap','link-cap','revision-cap','link-revision'):
            b=self.prepare();history=b.state['history'];inventory=history['textureOwnership'];row=inventory['links'][0];node=inventory['nodes'][0]
            if fault=='unknown6':history['assetModelOriginHistoryVersion']=6
            elif fault=='bool-version':inventory['assetModelTextureOwnershipVersion']=True
            elif fault=='parent':row['geometryId']='f'*32
            elif fault=='slot':row['materialSlot']=1
            elif fault=='channel':row['channel']=True
            elif fault=='source-kind':inventory['nodes'][1]['kind']='map'
            elif fault=='dangling':row['sourceId']='f'*32
            elif fault=='empty-map':row['mapId']=''
            elif fault=='sentinel':row['channel']=-1
            elif fault=='duplicate-edge':inventory['links'].append(dict(deepcopy(row),id='b'*32))
            elif fault=='future':node['born']['epochMs']+=100000
            elif fault=='backwards':row['lastObserved']['monotonicMs']-=1
            elif fault=='alive-int':node['strongOwnersAlive']=1
            elif fault=='missing-death':node['strongOwnersAlive']=False
            elif fault=='live-death':node['ownershipExpiryObserved']=deepcopy(node['born'])
            elif fault=='node-cap':inventory['nodes']=[dict(deepcopy(node),id=format(index,'032x')) for index in range(257)]
            elif fault=='link-cap':inventory['links']=[dict(deepcopy(row),id=format(index,'032x')) for index in range(513)]
            elif fault=='revision-cap':inventory['revision']=texture.REVISION_LIMIT+1
            else:row['revision']=inventory['revision']+1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.reader().read(RUN)

    def test_weak_expiry_and_link_history_cannot_be_rewritten(self):
        for fault in ('drop-node','drop-link','resurrect','change-death','source-rebind','born','clock','revision','same-revision-clock','rollback'):
            b=self.prepare();inventory=b.state['history']['textureOwnership'];node=inventory['nodes'][0]
            node.update(strongOwnersAlive=False,ownershipExpiryObserved=deepcopy(node['born']))
            reader=b.reader();first=reader.read(RUN);row=inventory['links'][0]
            if fault=='drop-node':inventory['nodes'].pop()
            elif fault=='drop-link':inventory['links'].pop()
            elif fault=='resurrect':node.update(strongOwnersAlive=True,ownershipExpiryObserved=None)
            elif fault=='change-death':node['ownershipExpiryObserved']['epochMs']+=1
            elif fault=='source-rebind':row['sourceId']=''
            elif fault=='born':row['born']['epochMs']+=1
            elif fault=='clock':row['lastObserved']['monotonicMs']-=1
            elif fault=='revision':inventory['revision']-=1
            elif fault=='same-revision-clock':row['lastObserved']['epochMs']+=1
            else:b.state['history'].update(assetModelOriginHistoryVersion=4);b.state['history'].pop('textureOwnership')
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(first,reader.last)

    def test_new_shared_map_source_edges_append_and_same_group_mutation_advances_revision(self):
        b=self.prepare();reader=b.reader();first=reader.read(RUN);inventory=b.state['history']['textureOwnership'];row=inventory['links'][0]
        inventory['links'].append(dict(deepcopy(row),id='b'*32,channel=1,revision=3));inventory['revision']=3
        second=reader.read(RUN);self.assertEqual(2,len(texture.consumers(second,b.row['id'])['nodes']))
        row.update(revision=4,lastObserved=dict(epochMs=b.epoch+11,monotonicMs=11));inventory['revision']=4
        third=reader.read(RUN);self.assertEqual(4,texture.consumers(third,b.row['id'])['revision'])
        self.assertEqual(1,len(first['source']['history']['textureOwnership']['links']))

    def test_actual_clone_and_replacement_keep_old_weak_groups_separate(self):
        b=self.prepare();material=Holder();material.map=Holder();material.map.source=Holder();clone=copy(material)
        external_source=material.map.source
        refs=[weakref.ref(material.map),weakref.ref(material.map.source)];deaths={}
        def observe(packet):
            history=packet['source']['history']
            for ref,row in zip(refs,history['textureOwnership']['nodes']):
                row['strongOwnersAlive']=ref() is not None
                if not row['strongOwnersAlive']:deaths.setdefault(row['id'],deepcopy(history['clock']))
                row['ownershipExpiryObserved']=deepcopy(deaths.get(row['id']))
        b.mutate=observe;reader=b.reader();first=reader.read(RUN)
        material.map=Holder();material.map.source=Holder();refs.extend([weakref.ref(material.map),weakref.ref(material.map.source)])
        inventory=b.state['history']['textureOwnership'];born=dict(epochMs=b.epoch+24,monotonicMs=24)
        inventory['nodes'].extend([dict(id=id_*32,kind=kind,born=deepcopy(born),strongOwnersAlive=True,ownershipExpiryObserved=None)
            for id_,kind in (('c','map'),('d','source'))])
        inventory['links'].append(dict(deepcopy(inventory['links'][0]),id='e'*32,mapId='c'*32,sourceId='d'*32,
            born=deepcopy(born),lastObserved=deepcopy(born),revision=3));inventory['revision']=3
        second=reader.read(RUN);self.assertEqual(4,len(texture.consumers(second,b.row['id'])['nodes']))
        del clone;gc.collect();third=reader.read(RUN)
        self.assertEqual([False,True,True,True],[row['strongOwnersAlive'] for row in texture.consumers(third,b.row['id'])['nodes']])
        del material;gc.collect();fourth=reader.read(RUN)
        self.assertFalse(texture.consumers(fourth,b.row['id'])['allKnownTextureOwnersGone'])
        del external_source;gc.collect();last=reader.read(RUN)
        self.assertTrue(texture.consumers(last,b.row['id'])['allKnownTextureOwnersGone'])
        self.assertEqual(2,len(first['source']['history']['textureOwnership']['nodes']))

    def test_expiry_before_the_previous_actual_alive_sample_is_refused(self):
        b=self.prepare();reader=b.reader();first=reader.read(RUN);inventory=b.state['history']['textureOwnership']
        inventory['nodes'][0].update(strongOwnersAlive=False,ownershipExpiryObserved=deepcopy(inventory['nodes'][0]['born']))
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual(first,reader.last)

    def test_actual_probe_preserves_history_five_without_absence_selectors_or_replay(self):
        b=self.prepare();packet=b.reader().read(RUN);query=b.queries[-1]
        for key in ('mapId','sourceId','retire','gpuComplete'):
            with self.assertRaises(NativeUIError):origin.command(dict(query,**{key:'wanted'}))
        program="""const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const packet=PACKET;let calls=0,files=[];
const Test={featureIOSAssetsModelOrigin:q=>{calls++;return {...packet,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||JSON.stringify(files[0].v.source)!==JSON.stringify(packet.source))throw Error('texture ownership changed or getter replayed');
if(files[0].v.source.history.assetModelOriginHistoryVersion!==5||files[0].v.source.resourceRetirementAvailable!==false)throw Error('wrong profile or invented retirement');
""".replace('PACKET',json.dumps(packet)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_literal_history_four_mesh_fact_is_explicitly_preserved_but_release_one_refuses_five(self):
        b=self.prepare();packet=b.reader().read(RUN)
        self.assertEqual(2,len(origin.strong_consumers(packet,b.row['id'])['consumers']))
        lineage=dict(readerId=b.row['id'],sha256=b.row['sha256'],bytes=b.row['bytes'],processId=packet['processId'],runId=RUN)
        with self.assertRaises(NativeUIError):assets_strong_release.strong_history(packet,[packet],lineage)

    def test_empty_material_snapshot_is_readable_but_not_positive_texture_evidence(self):
        b=self.prepare();inventory=b.state['history']['textureOwnership'];row=inventory['links'][0]
        inventory.update(nodes=[],revision=1);row.update(channel=-1,mapId='',sourceId='',revision=1)
        packet=b.reader().read(RUN)
        self.assertEqual(-1,packet['source']['history']['textureOwnership']['links'][0]['channel'])
        with self.assertRaises(NativeUIError):texture.consumers(packet,b.row['id'])


class AssetsTextureConsumersRuntimeTests(AssetsModelOriginRuntimeTests):
    def test_history_five_uses_actual_canonical_afc_and_native_clock_carrier(self):
        launches=self.f.launches;b=self.b;prepared=AssetsTextureConsumersTests().prepare(b.epoch)
        b.state['history']=deepcopy(prepared.state['history']);b.row=b.state['history']['downloads'][0]
        packet=self.reader().read(RUN);facts=texture.consumers(packet,b.row['id'])
        self.assertFalse(facts['allKnownTextureOwnersGone']);self.assertEqual(1,len(self.afc))
        self.assertEqual(launches,self.f.launches);self.assertEqual(2,len(facts['nodes']))
