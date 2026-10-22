"""Actual existing Python/JS dispatch with explicit synthetic Qt/AFC boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from ios.adapters import feature_observation, avatar_renderers, avatar_social_http, people_model
from ios.self_tests import test_ios_avatar_renderers as render_tests
from ios.self_tests import test_ios_avatar_social_http as http_tests
from ios.self_tests import test_ios_people_model as people_tests
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests.test_ios_location_bookmarks import Boundary as Clocks
from self_tests.test_native_feature_observation import Boundary as ClockBoundary, probe_source

RUN='a'*32


class SourceBoundary(Clocks):
    def __init__(self,prototype):super().__init__(None);self.prototype=prototype
    def original(self):
        self.clock+=.001;value=deepcopy(self.prototype);self.sequence+=1
        value.update(requestId=self.requests[-1]['commandId'],runId=self.requests[-1]['runId'],sequence=self.sequence)
        value['clockBefore']=self.clocks();self.clock+=.001;value['clockAfter']=self.clocks()
        self.last=deepcopy(value);return json.dumps(value)


class AvatarTransportTests(unittest.TestCase):
    def transport(self,module,prototype,factory):
        native=Native();clock=ClockBoundary();source=SourceBoundary(prototype);observer=native.observer()
        observer.monotonic=lambda:source.clock;observer.sleep=source.sleep;observer.epoch_ms=lambda:9000
        def stamp(value):
            source.native_clock();epoch=source.epoch()
            value.update(processId=42,capturedEpochMs=epoch,requestedEpochMs=epoch,animation={},animationFence={})
        clock.mutate=stamp
        def post(request,timeout):
            query=native.fixture.set_client_command(json.loads(request.data));native.commands.append(deepcopy(query))
            native.echo=json.dumps(query).encode()
            (clock if query['action']=='feature-native-observe' else source).send(query)
            return native
        def execute(session,operation,values):
            self.assertEqual('native-session',session);self.assertEqual('mobile: pullFile',operation)
            path=values['remotePath'];native.reads.append(path);prefix='@org.example.client:documents/owned-results/'
            self.assertIn(path,(prefix+'feature-native-observation.json',prefix+module.FILE))
            original=clock.original() if path.endswith('/feature-native-observation.json') else source.original()
            return base64.b64encode(original.encode()).decode()
        with patch.object(feature_observation,'post_request',side_effect=post),patch.object(native,'execute',side_effect=execute):
            reader=getattr(observer,factory)();result=reader.read(RUN)
        self.assertEqual(source.last,result);self.assertEqual(3,len(native.reads))
        self.assertEqual(['feature-native-observe',module.ACTION,'feature-native-observe'],[item['action'] for item in native.commands])
        self.assertEqual(3,len({item['commandId'] for item in native.commands}))
        self.assertNotEqual(9000,result['clockAfter']['epochMs'])
        self.assertLess(reader.acquisition['nativeRequestedEpochMs'],result['clockBefore']['epochMs'])
        self.assertGreater(reader.acquisition['nativeAfterEpochMs'],result['clockAfter']['epochMs'])
        return result

    def test_renderer4_retains_original_remote_external_pose_and_bounds_through_native_clock_HTTP_AFC(self):
        original=render_tests.packet();result=self.transport(avatar_renderers,original,'avatar_renderers')
        self.assertEqual(4,result['iosAvatarRenderersVersion'])
        self.assertEqual(original['source']['avatars'][1]['externalPose'],result['source']['avatars'][1]['externalPose'])
        self.assertIsNone(result['source']['avatars'][1]['rigPose'])
        self.assertEqual(original['source']['avatars'][1]['bounds'],result['source']['avatars'][1]['bounds'])

    def test_social_http_retains_real_provider_joinable_original_event_history(self):
        logic=http_tests.SocialHttpTests();logic.setUp()
        result=self.transport(avatar_social_http,logic.value,'avatar_social_http')
        self.assertEqual(logic.value['events'],result['events'])
        self.assertEqual(logic.status['history'][0],logic.consumed(result)['http'])

    def test_people_model_uses_fixed_original_native_source_and_no_host_epoch_substitution(self):
        original=people_tests.packet();result=self.transport(people_model,original,'people_model')
        self.assertEqual(original['source'],result['source'])

    def test_probe_calls_once_preserves_originals_and_never_forges_unavailable_sources(self):
        for module,method,key in ((avatar_renderers,'featureIOSAvatarRenderers','source'),
                (avatar_social_http,'featureIOSAvatarSocialHttp','events'),(people_model,'featureIOSPeopleModel','source')):
            program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=0,files=[];const original={requestId:'ios-'+'e'.repeat(32),original:'untouched-native-original'};
const Test={METHOD:c=>{calls++;return original;},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'ios-'+'e'.repeat(32),action:'ACTION',runId:'a'.repeat(32)};
applyClientCommand(c);applyClientCommand(c);
if(calls!==1||files[0].v!==original||files[0].name!=='FILE')throw Error('Original replaced or repeated');
for(const extra of [{response:'success'},{connected:true},{joints:[]},{schemaVersion:true}]){
 applyClientCommand({...c,...extra,commandId:'ios-'+'f'.repeat(32)});
}if(calls!==1)throw Error('Wanted effect admitted');
delete Test.METHOD;applyClientCommand({...c,commandId:'ios-'+'f'.repeat(32)});
if(files[1].v.status!=='unavailable'||files[1].v.KEY)throw Error('Missing source invented');
'''.replace('SOURCE',probe_source()).replace('METHOD',method).replace('ACTION',module.ACTION).replace('FILE',module.FILE).replace('KEY',key)
            result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
            with self.subTest(source=module.ACTION):self.assertEqual(0,result.returncode,result.stderr)

    def test_remote_hook_captures_real_external_copy_after_received_joint_interpolation(self):
        root=Path(__file__).resolve().parents[4]
        rig=(root/'libraries/animation/src/Rig.cpp').read_text()
        start=rig.index('void Rig::computeExternalPoses(');end=rig.index('\nvoid Rig::computeAvatarBoundingCapsule',start)
        original=rig[start:end]
        self.assertLess(original.index('_externalPoseSet = _internalPoseSet;'),original.index('_e2eExternalPose.copied('))
        self.assertLess(original.index('QWriteLocker writeLock(&_externalPoseSetLock);'),original.index('_e2eExternalPose.copied('))
        remote=(root/'interface/src/avatar/OtherAvatar.cpp').read_text()
        self.assertLess(remote.index('copyJointsFromJointData(_jointData)'),remote.index('computeExternalPoses(rootTransform)'))
        observation=(root/'tests/device/native/IOSAvatarRenderersObservation.h').read_text()
        self.assertIn('model->getRig().e2eExternalPoseObservation()',observation)


if __name__=='__main__':unittest.main()
