"""Actual Python sharing holders at an explicit native-source model boundary.

No C++ compiler, native parser, destructor, graphics backend or GPU runs here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import json
import subprocess
import unittest
import weakref
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_model_origin as source
from ios.self_tests.test_ios_assets_geometry_consumers import Holder
from ios.self_tests.test_ios_assets_model_origin import RUN,Boundary,AssetsModelOriginRuntimeTests
from self_tests.test_native_feature_observation import probe_source


class AssetsStrongConsumersTests(unittest.TestCase):
    def prepare(self,epoch=None):
        b=Boundary() if epoch is None else Boundary(epoch);history=b.state['history']
        b.row['resourceObjectAlive']=True
        history['geometries']=[dict(id='4'*32,readerId=b.row['id'],mappingIds=[],kind='resource',
            born=dict(epochMs=b.epoch+9,monotonicMs=9),alive=True,destructionObserved=None)]
        history['assetModelOriginHistoryVersion']=4
        geometry=history['geometries'][0]
        history['consumerOwnership']=dict(assetModelConsumerOwnershipVersion=1,rows=[
            dict(id=id_*32,geometryId=geometry['id'],kind=kind,slot=0,
                born=dict(epochMs=b.epoch+10,monotonicMs=10),strongOwnersAlive=True,ownershipExpiryObserved=None)
            for id_,kind in (('6','mesh'),('7','material'))])
        return b

    def test_external_mesh_and_material_holders_survive_geometry_death(self):
        b=self.prepare();geometry=Holder();geometry.mesh=Holder();geometry.material=Holder()
        external_mesh=geometry.mesh;external_material=geometry.material
        token=weakref.ref(geometry);weaks=[weakref.ref(geometry.mesh),weakref.ref(geometry.material)]
        deaths={}
        def observe(packet):
            history=packet['source']['history'];parent=history['geometries'][0]
            parent['alive']=token() is not None
            if not parent['alive']:deaths.setdefault('geometry',deepcopy(history['clock']))
            parent['destructionObserved']=deepcopy(deaths.get('geometry'))
            for ref,row in zip(weaks,history['consumerOwnership']['rows']):
                row['strongOwnersAlive']=ref() is not None
                if not row['strongOwnersAlive']:deaths.setdefault(row['id'],deepcopy(history['clock']))
                row['ownershipExpiryObserved']=deepcopy(deaths.get(row['id']))
        b.mutate=observe;reader=b.reader();first=reader.read(RUN);original=deepcopy(first)
        del geometry;gc.collect();second=reader.read(RUN)
        self.assertTrue(source.geometry_consumers(second,b.row['id'])['allKnownGeometryDead'])
        self.assertFalse(source.strong_consumers(second,b.row['id'])['allKnownStrongOwnersGone'])
        del external_material;gc.collect();third=reader.read(RUN)
        self.assertEqual([True,False],[row['strongOwnersAlive'] for row in source.strong_consumers(third,b.row['id'])['consumers']])
        death=deepcopy(third['source']['history']['consumerOwnership']['rows'][1]['ownershipExpiryObserved'])
        del external_mesh;gc.collect();fourth=reader.read(RUN);facts=source.strong_consumers(fourth,b.row['id'])
        self.assertTrue(facts['allKnownStrongOwnersGone']);self.assertFalse(facts['destructorCompletionAvailable'])
        self.assertFalse(facts['resourceRetirementAvailable']);self.assertEqual(original,first)
        self.assertEqual(death,fourth['source']['history']['consumerOwnership']['rows'][1]['ownershipExpiryObserved'])

    def test_old_or_empty_original_ownership_cannot_establish_mesh_owner_absence(self):
        b=self.prepare();b.state['history']['consumerOwnership']['rows']=[]
        with self.assertRaises(NativeUIError):source.strong_consumers(b.reader().read(RUN),b.row['id'])
        for version in (1,2,3):
            b=self.prepare();history=b.state['history'];history['assetModelOriginHistoryVersion']=version;history.pop('consumerOwnership')
            if version<3:history.pop('geometries')
            if version<2:b.row.pop('resourceObjectAlive')
            with self.subTest(version=version),self.assertRaises(NativeUIError):source.strong_consumers(b.reader().read(RUN),b.row['id'])

    def test_invalid_membership_types_clocks_and_capacity_are_refused(self):
        for fault in ('parent','kind','slot-bool','slot-negative','alive-int','duplicate','future-born','early-born','live-expiry','missing-expiry','overflow','version'):
            b=self.prepare();inventory=b.state['history']['consumerOwnership'];row=inventory['rows'][0]
            if fault=='parent':row['geometryId']='f'*32
            elif fault=='kind':row['kind']='gpu-fence'
            elif fault=='slot-bool':row['slot']=True
            elif fault=='slot-negative':row['slot']=-1
            elif fault=='alive-int':row['strongOwnersAlive']=1
            elif fault=='duplicate':inventory['rows'].append(deepcopy(row))
            elif fault=='future-born':row['born']['monotonicMs']=100000
            elif fault=='early-born':row['born']['monotonicMs']=0
            elif fault=='live-expiry':row['ownershipExpiryObserved']=deepcopy(row['born'])
            elif fault=='missing-expiry':row['strongOwnersAlive']=False
            elif fault=='overflow':inventory['rows']=[dict(deepcopy(row),id=format(index,'032x')) for index in range(257)]
            else:inventory['assetModelConsumerOwnershipVersion']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.reader().read(RUN)

    def test_append_only_rows_and_original_expiry_are_immutable(self):
        for fault in ('drop','reorder','parent','kind','slot','born','expiry','resurrection','rollback'):
            b=self.prepare();inventory=b.state['history']['consumerOwnership'];row=inventory['rows'][0]
            row.update(strongOwnersAlive=False,ownershipExpiryObserved=deepcopy(row['born']))
            reader=b.reader();first=reader.read(RUN)
            if fault=='drop':inventory['rows'].pop()
            elif fault=='reorder':inventory['rows'].reverse()
            elif fault=='parent':row['geometryId']='f'*32
            elif fault=='kind':row['kind']='material'
            elif fault=='slot':row['slot']=1
            elif fault=='born':row['born']['epochMs']+=1
            elif fault=='expiry':row['ownershipExpiryObserved']['epochMs']+=1
            elif fault=='resurrection':row.update(strongOwnersAlive=True,ownershipExpiryObserved=None)
            else:b.state['history']['assetModelOriginHistoryVersion']=3;b.state['history'].pop('consumerOwnership')
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(first,reader.last)

    def test_new_material_ownership_is_an_additional_record_not_a_rewritten_slot(self):
        b=self.prepare();reader=b.reader();first=reader.read(RUN)
        rows=b.state['history']['consumerOwnership']['rows'];old=deepcopy(rows[1])
        rows.append(dict(deepcopy(old),id='8'*32,born=dict(epochMs=b.epoch+11,monotonicMs=11)))
        second=reader.read(RUN);facts=source.strong_consumers(second,b.row['id'])
        self.assertEqual(3,len(facts['consumers']));self.assertEqual(old,facts['consumers'][1])
        self.assertEqual(2,len(first['source']['history']['consumerOwnership']['rows']))

    def test_actual_probe_keeps_ownership_bytes_without_a_requested_absence_selector(self):
        b=self.prepare();packet=b.reader().read(RUN);query=b.queries[-1]
        for key in ('meshId','materialId','strongOwnersAlive','retire'):
            with self.assertRaises(NativeUIError):source.command(dict(query,**{key:'wanted'}))
        program="""const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const packet=PACKET;let calls=0,files=[];
const Test={featureIOSAssetsModelOrigin:q=>{calls++;return {...packet,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||JSON.stringify(files[0].v.source)!==JSON.stringify(packet.source))throw Error('ownership changed or getter replayed');
if(files[0].v.source.history.assetModelOriginHistoryVersion!==4||files[0].v.source.resourceRetirementAvailable!==false)throw Error('wrong ownership profile');
""".replace('PACKET',json.dumps(packet)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


class AssetsStrongConsumersRuntimeTests(AssetsModelOriginRuntimeTests):
    def test_history_four_uses_actual_canonical_afc_and_native_clock_carrier(self):
        launches=self.f.launches;b=self.b;prepared=AssetsStrongConsumersTests().prepare(b.epoch)
        b.state['history']=deepcopy(prepared.state['history']);b.row=b.state['history']['downloads'][0]
        packet=self.reader().read(RUN);facts=source.strong_consumers(packet,b.row['id'])
        self.assertFalse(facts['allKnownStrongOwnersGone']);self.assertEqual(1,len(self.afc))
        self.assertEqual(launches,self.f.launches);self.assertEqual(2,len(facts['consumers']))
