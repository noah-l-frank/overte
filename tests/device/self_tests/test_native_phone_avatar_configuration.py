"""Real reader/resource joins at synthetic native boundaries; no client execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from adapters.native_phone_avatar_configuration import NativePhoneAvatarConfiguration,command,controlled,CONFIGURED,LOADED,RESOURCE_LIMIT
from adapters.native_avatar_render import EMPTY_SHA256
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import pinned_resource
from self_tests.test_native_avatar_render import Boundary as AvatarBoundary
from self_tests.test_native_feature_observation import probe_source


def resource(name,path):
    data=pinned_resource(name)
    return dict(resourcePath=path,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


class Boundary(AvatarBoundary):
    def __init__(self):
        super().__init__()
        self.configuration=dict(phoneAvatarConfigurationVersion=1,modelInstance=self.avatar['modelInstance'],rigId=self.avatar['rigId'],
            configured=dict(present=True,urlSha256='1'*64,bundledResource=resource('avatar-a.fst',CONFIGURED)),
            loadedGeometry=dict(instance=self.avatar['geometry']['instance'],source=dict(present=True,
                urlSha256=self.avatar['geometry']['sourceSha256'],bundledResource=resource('mannequin/mannequin.fbx',LOADED))),
            boomLength=1.5,pinchZoomEnabled=False)

    def send(self,request):
        if request['action']!='phone-avatar-configuration-observe':return super().send(request)
        self.commands.append(deepcopy(request))
        if self.ignored:return
        self.sequence+=1;self.epoch+=1
        self.sample=dict(schemaVersion=1,requestId=request['commandId'],instance='f'*32,sequence=self.sequence,processId=31,
            requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=deepcopy(self.configuration))
        if self.edit:self.edit(self.sample)

    def reader(self,**options):
        return NativePhoneAvatarConfiguration(self.send,self.original,lambda:self.epoch,lambda:self.okay,31,
            monotonic=lambda:self.clock,sleep=self.sleep,**options)

    def pair(self):
        config=self.reader().read()
        avatar=super().reader().read()
        return config,avatar


class AvatarConfigurationTests(unittest.TestCase):
    def test_actual_preference_boom_and_bundled_bytes_are_observed_without_requested_values(self):
        b=Boundary();value=b.reader().read()
        self.assertEqual(b.sample,value);self.assertEqual(b.configuration,value['source'])
        self.assertEqual({'schemaVersion','commandId','action'},set(b.commands[0]))
        self.assertEqual(3654465,value['source']['loadedGeometry']['source']['bundledResource']['bytes'])

    def test_both_resources_join_independent_render_originals_and_repository_pins(self):
        b=Boundary();config,avatar=b.pair();self.assertEqual(b.configuration,controlled(config,avatar))
        self.assertEqual(2,len(b.commands))

    def test_unloaded_or_external_models_remain_observable_without_claiming_controlled_content(self):
        for kind in ('unloaded','external-config','external-loaded','empty'):
            b=Boundary()
            if kind=='unloaded':b.configuration['loadedGeometry']=None
            elif kind=='external-config':b.configuration['configured']['bundledResource']=None
            elif kind=='external-loaded':b.configuration['loadedGeometry']['source']['bundledResource']=None
            else:b.configuration['configured']=dict(present=False,urlSha256=EMPTY_SHA256,bundledResource=None)
            config,avatar=b.pair()
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):controlled(config,avatar)

    def test_loaded_url_aliases_keep_raw_hash_and_cannot_borrow_canonical_render_identity(self):
        raw='qrc:////meshes/mannequin/mannequin.fbx';normalized='qrc:/meshes/mannequin/mannequin.fbx'
        b=Boundary();digest=hashlib.sha256(raw.encode()).hexdigest()
        b.configuration['loadedGeometry']['source']['urlSha256']=digest;b.avatar['geometry']['sourceSha256']=digest
        pair=b.pair();self.assertEqual(digest,controlled(*pair)['loadedGeometry']['source']['urlSha256'])
        pair[0]['source']['loadedGeometry']['source']['urlSha256']=hashlib.sha256(normalized.encode()).hexdigest()
        with self.assertRaises(NativeUIError):controlled(*pair)

    def test_requested_values_legacy_versions_platform_aliases_and_mutations_are_refused(self):
        valid=dict(schemaVersion=1,commandId='a'*32,action='phone-avatar-configuration-observe')
        self.assertEqual(valid,command(valid))
        for edit in (dict(schemaVersion=True),dict(commandId='ios-'+'a'*32),dict(expectedBoom=3),dict(avatarUrl='fixture'),
                dict(action='phone-avatar-configuration-set')):
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):command(valid|edit)
        b=Boundary()
        with self.assertRaises(NativeUIError):b.reader(ios=True).read()
        self.assertEqual([],b.commands)

    def test_bounds_types_and_missing_or_extra_source_facts_fail(self):
        for edit in (dict(phoneAvatarConfigurationVersion=True),dict(pinchZoomEnabled=1),dict(boomLength=.49),dict(boomLength=25.1),
                dict(boomLength=float('nan')),dict(rigId=True),dict(modelInstance='bad'),dict(expectedLoaded=True)):
            b=Boundary();b.configuration.update(edit)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):b.reader().read()

    def test_resource_metadata_is_exact_bounded_and_cannot_report_empty_urls_as_files(self):
        for edit in (dict(resourcePath='meshes/foreign.fst'),dict(bytes=0),dict(bytes=RESOURCE_LIMIT+1),dict(bytes=True),
                dict(sha256='wrong'),dict(expectedDigest='1'*64)):
            b=Boundary();b.configuration['configured']['bundledResource'].update(edit)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):b.reader().read()
        b=Boundary();b.configuration['configured'].update(present=False,urlSha256=EMPTY_SHA256)
        with self.assertRaises(NativeUIError):b.reader().read()

    def test_wrong_resource_bytes_digests_or_loaded_render_identity_never_qualify(self):
        for kind in ('digest','size','model','rig','geometry','url','birth','pid'):
            b=Boundary();config,avatar=b.pair()
            if kind=='digest':config['source']['configured']['bundledResource']['sha256']='0'*64
            elif kind=='size':config['source']['loadedGeometry']['source']['bundledResource']['bytes']-=1
            elif kind=='model':avatar['source']['modelInstance']='1'*32
            elif kind=='rig':avatar['source']['rigId']+=1
            elif kind=='geometry':avatar['source']['geometry']['instance']='1'*32
            elif kind=='url':avatar['source']['geometry']['sourceSha256']='1'*64
            elif kind=='birth':avatar['instance']='1'*32
            else:avatar['processId']+=1
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):controlled(config,avatar)

    def test_changed_repository_pins_are_not_silently_accepted(self):
        b=Boundary();pair=b.pair()
        with patch('feature_journeys.fixtures.pinned_resource',return_value=b'foreign'),self.assertRaises(NativeUIError):controlled(*pair)

    def test_ignored_missing_and_foreign_results_remain_unavailable(self):
        for kind in ('ignore','foreign','unavailable','missing'):
            b=Boundary()
            if kind=='ignore':b.ignored=True
            elif kind=='foreign':b.edit=lambda value:value.update(requestId='b'*32)
            elif kind=='unavailable':b.edit=lambda value:value.update(available=False)
            else:b.edit=lambda value:value.pop('source')
            reader=b.reader()
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):reader.read()
            self.assertIsNone(reader.last);self.assertLessEqual(b.reads,51)

    def test_old_birth_process_cursors_and_request_times_are_refused(self):
        for edit in (dict(instance='a'*32),dict(processId=32),dict(sequence=1),dict(requestedEpochMs=1,capturedEpochMs=1)):
            b=Boundary();reader=b.reader();first=reader.read();b.edit=lambda value:value.update(edit)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):reader.read()
            self.assertEqual(first,reader.last)

    def test_frozen_clock_cannot_hide_slow_decode_copy_or_final_guard(self):
        for kind in ('read','copy','guard'):
            b=Boundary();reader=b.reader()
            if kind=='read':
                def slow_read():b.clock+=5.1;return b.original()
                reader.original=slow_read
            elif kind=='guard':
                calls=[0]
                def guard():
                    calls[0]+=1
                    if calls[0]==4:b.clock+=1.6
                    return True
                reader.guard=guard
            with self.subTest(kind=kind):
                if kind=='copy':
                    def slow_copy(value):b.clock+=1.6;return deepcopy(value)
                    with patch('adapters.native_avatar_render.deepcopy',side_effect=slow_copy),self.assertRaises(NativeUIError):reader.read()
                else:
                    with self.assertRaises(NativeUIError):reader.read()
                self.assertIsNone(reader.last)

    def test_historical_restore_never_queries_relabels_or_retimes_originals(self):
        b=Boundary();reader=b.reader();frames=[reader.read(),reader.read()];again=b.reader();sent=len(b.commands)
        again.restore(frames);self.assertEqual(sent,len(b.commands));self.assertEqual(frames[-1],again.last)
        self.assertGreater(again.read()['sequence'],frames[-1]['sequence'])
        with self.assertRaises(NativeUIError):b.reader().restore(list(reversed(frames)))

    def test_real_probe_forwards_original_once_and_never_fills_missing_hook(self):
        program=r'''
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
let calls=[],files=[];
const original={requestId:"a".repeat(32),capturedEpochMs:17000,source:{originalResource:true}};
const Test={phoneAvatarConfigurationObservation:c=>{calls.push(c);return original;},saveObject:(v,n)=>files.push({v,n})};
SOURCE
const c={schemaVersion:1,commandId:"a".repeat(32),action:"phone-avatar-configuration-observe"};
applyAndroidControlCommand(c);applyAndroidControlCommand(c);
if(calls.length!==1||files.length!==1||files[0].v!==original||files[0].n!=="phone-avatar-configuration.json")throw Error("original replaced/repeated");
for(const extra of [{expectedBoom:3},{avatarUrl:"wanted"}])applyAndroidControlCommand({...c,commandId:"b".repeat(32),...extra});
if(calls.length!==1)throw Error("requested result admitted");
delete Test.phoneAvatarConfigurationObservation;
applyAndroidControlCommand({...c,commandId:"c".repeat(32)});
if(files.length!==2||files[1].v.available!==false||original.capturedEpochMs!==17000)throw Error("missing hook green/retimed");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
