"""Actual weak holder copies at a declared native boundary; no native build."""
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
from ios.self_tests.test_ios_assets_model_origin import Boundary,AssetsModelOriginRuntimeTests,RUN
from self_tests.test_native_feature_observation import probe_source


class Holder:pass


class Geometry:
    def __init__(self,hfm):self.token=Holder();self.hfm=hfm;self.material=Holder()
    def __del__(self):
        # Explicit counterpart of the native first-member token: actual fields
        # release before the token. The source itself owns only weak refs.
        self.material=None;self.hfm=None;self.token=None


class AssetsGeometryConsumersTests(unittest.TestCase):
    def prepare(self):
        b=Boundary();b.state['history']['assetModelOriginHistoryVersion']=3;b.row['resourceObjectAlive']=True
        b.state['history']['geometries']=[dict(id='4'*32,readerId=b.row['id'],mappingIds=[],kind='resource',
            born=dict(epochMs=b.epoch+9,monotonicMs=9),alive=True,destructionObserved=None)]
        return b
    def test_geometry_copy_retains_actual_hfm_after_original_lease_and_cached_qobject_die(self):
        b=self.prepare();lease=Holder();hfm=Holder();resource=Holder();resource.geometry=Geometry(hfm);copied=Geometry(hfm)
        weaks=dict(lease=weakref.ref(lease),object=weakref.ref(resource),hfm=weakref.ref(hfm))
        rows=[(weakref.ref(resource.geometry.token),deepcopy(b.state['history']['geometries'][0])),
              (weakref.ref(copied.token),dict(deepcopy(b.state['history']['geometries'][0]),id='5'*32,kind='copy'))]
        observed={}
        def current(packet):
            history=packet['source']['history'];history['geometries']=[];row=history['downloads'][0]
            row.update(resourceAlive=weaks['lease']() is not None,resourceObjectAlive=weaks['object']() is not None,parsedModelAlive=weaks['hfm']() is not None)
            for token,original in rows:
                value=deepcopy(original);value['alive']=token() is not None
                if not value['alive']:observed.setdefault(value['id'],deepcopy(history['clock']))
                value['destructionObserved']=deepcopy(observed.get(value['id']));history['geometries'].append(value)
        b.mutate=current;reader=b.reader();first=reader.read(RUN);baseline=deepcopy(first)
        del lease;del hfm;gc.collect();second=reader.read(RUN)
        facts=source.geometry_consumers(second,b.row['id']);self.assertFalse(facts['originalLeaseAlive']);self.assertTrue(facts['resourceObjectAlive'])
        self.assertFalse(facts['allKnownGeometryDead']);self.assertTrue(facts['hfmAlive'])
        del resource;gc.collect();third=reader.read(RUN);facts=source.geometry_consumers(third,b.row['id'])
        self.assertFalse(facts['resourceObjectAlive']);self.assertTrue(facts['hfmAlive']);self.assertFalse(facts['allKnownGeometryDead'])
        self.assertEqual([False,True],[row['alive'] for row in facts['geometries']])
        old_death=deepcopy(facts['geometries'][0]['destructionObserved'])
        del copied;gc.collect();fourth=reader.read(RUN);facts=source.geometry_consumers(fourth,b.row['id'])
        self.assertTrue(facts['allKnownGeometryDead']);self.assertFalse(facts['hfmAlive']);self.assertFalse(facts['resourceRetirementAvailable'])
        self.assertEqual(old_death,facts['geometries'][0]['destructionObserved']);self.assertEqual(baseline,first)
    def test_legacy_or_missing_known_geometry_cannot_become_an_empty_retirement_inventory(self):
        for version in (1,2):
            b=Boundary();b.state['history']['assetModelOriginHistoryVersion']=version
            if version==2:b.row['resourceObjectAlive']=False
            packet=b.reader().read(RUN)
            with self.subTest(version=version),self.assertRaises(NativeUIError):source.geometry_consumers(packet,b.row['id'])
        b=self.prepare();b.state['history']['geometries']=[];packet=b.reader().read(RUN)
        with self.assertRaises(NativeUIError):source.geometry_consumers(packet,b.row['id'])
    def test_foreign_duplicate_untyped_oversized_or_impossible_geometry_history_is_refused(self):
        for fault in ('foreign-reader','mapping','duplicate','bool','born-before-queue','future-death','missing-death','live-death','overflow','kind'):
            b=self.prepare();history=b.state['history'];row=history['geometries'][0]
            if fault=='foreign-reader':row['readerId']='f'*32
            elif fault=='mapping':row['mappingIds']=[b.row['id']]
            elif fault=='duplicate':history['geometries'].append(deepcopy(row))
            elif fault=='bool':row['alive']=1
            elif fault=='born-before-queue':row['born']=dict(epochMs=b.epoch+1,monotonicMs=1)
            elif fault=='future-death':row.update(alive=False,destructionObserved=dict(epochMs=b.epoch+100000,monotonicMs=100000))
            elif fault=='missing-death':row['alive']=False
            elif fault=='live-death':row['destructionObserved']=dict(epochMs=b.epoch+10,monotonicMs=10)
            elif fault=='overflow':history['geometries']=[dict(deepcopy(row),id=format(i,'032x')) for i in range(129)]
            else:row['kind']='requested-success'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.reader().read(RUN)
    def test_geometry_disappearance_reordering_changed_birth_death_or_resurrection_cannot_rewrite_prefix(self):
        for fault in ('drop','reorder','birth','reader','mapping','kind','resurrection','death','rollback'):
            b=self.prepare();row=b.state['history']['geometries'][0]
            if fault=='reorder':b.state['history']['geometries'].append(dict(deepcopy(row),id='6'*32,kind='copy'))
            if fault in ('resurrection','death'):row.update(alive=False,destructionObserved=dict(epochMs=b.epoch+10,monotonicMs=10))
            reader=b.reader();first=reader.read(RUN)
            if fault=='drop':b.state['history']['geometries']=[]
            elif fault=='reorder':b.state['history']['geometries'].reverse()
            elif fault=='birth':row['born']['epochMs']+=1
            elif fault=='reader':row['id']='7'*32
            elif fault=='mapping':row['kind']='copy'
            elif fault=='kind':row['kind']='mapping-resource'
            elif fault=='resurrection':row.update(alive=True,destructionObserved=None)
            elif fault=='death':row['destructionObserved']['epochMs']+=1
            else:b.state['history']['assetModelOriginHistoryVersion']=2;b.state['history'].pop('geometries')
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(first,reader.last)
    def test_actual_probe_preserves_new_lifetime_rows_once_without_requested_geometry_selectors(self):
        b=self.prepare();packet=b.reader().read(RUN);query=b.queries[-1]
        for key in ('geometryId','readerId','retire','alive'):
            with self.assertRaises(NativeUIError):source.command(dict(query,**{key:'wanted'}))
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const packet=PACKET;let calls=0,files=[];
const Test={featureIOSAssetsModelOrigin:q=>{calls++;return {...packet,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||JSON.stringify(files[0].v.source)!==JSON.stringify(packet.source))throw Error('geometry source changed or replayed');
if(files[0].v.source.history.assetModelOriginHistoryVersion!==3||files[0].v.source.resourceRetirementAvailable!==false)throw Error('wrong lifetime profile');
'''.replace('PACKET',json.dumps(packet)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


class AssetsGeometryRuntimeTests(AssetsModelOriginRuntimeTests):
    def test_history_three_uses_actual_canonical_native_clock_and_afc_carrier(self):
        launches=self.f.launches;b=self.b;b.state['history']['assetModelOriginHistoryVersion']=3;b.row['resourceObjectAlive']=True
        b.state['history']['geometries']=[dict(id='4'*32,readerId=b.row['id'],mappingIds=[],kind='copy',
            born=dict(epochMs=b.epoch+9,monotonicMs=9),alive=True,destructionObserved=None)]
        packet=self.reader().read(RUN);facts=source.geometry_consumers(packet,b.row['id'])
        self.assertFalse(facts['allKnownGeometryDead']);self.assertEqual(1,len(self.afc))
        self.assertLess(facts['nativeEpochMs'],100000);self.assertEqual(launches,self.f.launches)
