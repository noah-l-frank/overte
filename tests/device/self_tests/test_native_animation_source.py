"""Original consumed-byte joins over controlled native metadata, never a client."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from adapters.native_animation_source import validate,model,pins,controlled,LIMIT,NAMES
from adapters.native_animation_history import clip as clip_packet
from adapters.normal_ui import NativeUIError

ROOT=Path(__file__).resolve().parents[3]


def source_for_clip(clip,*,consumed=19000,actual_name=None):
    """Synthetic parser/retarget boundary hashes real local bytes, not pin values."""
    name=actual_name or clip['url'].rsplit('/',1)[-1][:-4]
    raw=(ROOT/('scripts/system/assets/animations/'+name+'.fbx')).read_bytes()
    data=dict(animationDataVersion=1,instance=hashlib.sha256(('parsed:'+name).encode()).hexdigest()[:32],
        sourceUrlSha256=hashlib.sha256(clip['url'].encode()).hexdigest(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
        parser='fbx-full-v1',frames=clip['loadedFrames'],joints=75,parsedEpochMs=15010)
    return dict(animationSourceVersion=1,resourceInstance=hashlib.sha256(('resource:'+name).encode()).hexdigest()[:32],
        model=data,consumedEpochMs=consumed,blend='normal')


def sample(name='Waving',*,actual_name=None):
    value=dict(url='file:///actual/scripts/system/assets/animations/'+name+'.fbx',requestedUrl='file:///actual/scripts/system/assets/animations/'+name+'.fbx',
        frame=60.,firstFrame=0.,lastFrame=120.,framesPerSecond=60.,loop=False,loadedFrames=120,evaluatedEpochMs=20000,evaluationSequence=1,
        animationSourceVersion=1)
    value['assetSource']=source_for_clip(value,actual_name=actual_name);return value


class AnimationSourceTests(unittest.TestCase):
    def test_all_twelve_existing_resource_bytes_match_explicit_immutable_fixture_pins(self):
        original=pins();self.assertEqual(tuple(row['name'] for row in original['animations']),NAMES)
        for row in original['animations']:
            with self.subTest(name=row['name']):
                actual=(ROOT/row['sourcePath']).read_bytes()
                self.assertEqual(len(actual),row['bytes']);self.assertEqual(hashlib.sha256(actual).hexdigest(),row['sha256'])
                retained=subprocess.run(['git','show',original['sourceBase']+':'+row['sourcePath']],cwd=ROOT,capture_output=True,check=True).stdout
                self.assertEqual(actual,retained)
                value=sample(row['name']);clip_packet(value,epoch=20000)
                self.assertEqual(value['assetSource'],controlled(value,row['name'],20000))

    def test_correct_loaded_url_with_wrong_file_bytes_cannot_supply_named_animation_content(self):
        value=sample('Waving',actual_name='Cheering')
        self.assertEqual('file:///actual/scripts/system/assets/animations/Waving.fbx',value['url'])
        self.assertEqual(len((ROOT/'scripts/system/assets/animations/Cheering.fbx').read_bytes()),value['assetSource']['model']['bytes'])
        with self.assertRaises(NativeUIError):controlled(value,'Waving',20000)

    def test_actual_model_source_is_separate_from_requested_name_url_frame_count_and_receipt(self):
        for fault in ('missing','foreign-url','unknown-hash','wrong-size','frame-count','parser','blend','wrong-name'):
            value=sample();source=value['assetSource'];data=source['model']
            if fault=='missing':value['assetSource']=None
            elif fault=='foreign-url':data['sourceUrlSha256']='f'*64
            elif fault=='unknown-hash':data['sha256']='f'*64
            elif fault=='wrong-size':data['bytes']+=1
            elif fault=='frame-count':data['frames']+=1
            elif fault=='parser':data['parser']='fbx-skip-unused-curves-v1'
            elif fault=='blend':source['blend']='add-absolute'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):controlled(value,'Crying' if fault=='wrong-name' else 'Waving',20000)

    def test_closed_model_source_versions_types_limits_clocks_and_desired_fields_fail(self):
        value=sample()['assetSource']
        for edit in (dict(animationSourceVersion=True),dict(resourceInstance='bad'),dict(consumedEpochMs=True),dict(consumedEpochMs=20001),
            dict(consumedEpochMs=15000),dict(expectedSha256='f'*64),dict(model=1),dict(blend='requested')):
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):validate(value|edit,20000)
        for edit in (dict(animationDataVersion=True),dict(bytes=True),dict(bytes=0),dict(bytes=LIMIT+1),dict(frames=0),dict(joints=10001),
            dict(parsedEpochMs=20001),dict(sha256='F'*64),dict(sourceUrlSha256='bad'),dict(instance='bad'),dict(expectedBytes=1)):
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):model(value['model']|edit,20000)

    def test_generic_legacy_and_unknown_origins_are_observable_but_cannot_qualify_content(self):
        value=sample();legacy=deepcopy(value);legacy.pop('animationSourceVersion');legacy.pop('assetSource')
        clip_packet(legacy,epoch=20000)
        with self.assertRaises(NativeUIError):controlled(legacy,'Waving',20000)
        value['assetSource']=None;clip_packet(value,epoch=20000)
        with self.assertRaises(NativeUIError):controlled(value,'Waving',20000)

    def test_future_parse_consumption_and_numeric_boolean_native_versions_are_not_retimed(self):
        for fault in ('source-future','consumed-after-evaluation','outer-version','not-object','missing-source'):
            value=sample()
            if fault=='source-future':value['assetSource']['model']['parsedEpochMs']=20001
            elif fault=='consumed-after-evaluation':value['assetSource']['consumedEpochMs']=20001
            elif fault=='outer-version':value['animationSourceVersion']=True
            elif fault=='not-object':value['assetSource']=3
            else:value.pop('assetSource')
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):clip_packet(value,epoch=20000)

    def test_native_record_uses_exact_parser_input_and_original_model_before_normal_publication(self):
        source=(ROOT/'libraries/animation/src/AnimationCache.cpp').read_text()
        self.assertLess(source.index('FBXSerializer().read(_data'),source.index('animationDataObservation().record(hfmModel,_url,_data'))
        self.assertLess(source.index('animationDataObservation().record(hfmModel,_url,_data'),source.index('emit onSuccess(hfmModel)'))
        registry=(ROOT/'libraries/animation/src/AnimationDataObservation.h').read_text()
        self.assertIn('QCryptographicHash::hash(bytes,QCryptographicHash::Sha256)',registry)
        self.assertIn('std::weak_ptr<HFMModel>',registry);self.assertIn('model.get()==original',registry)
        self.assertNotIn('QFile',registry);self.assertNotIn('expected',registry)
        native=(ROOT/'libraries/animation/src/AnimClip.cpp').read_text()
        self.assertIn('networkAnim->featureSourceForModel(&animModel)',native)
        self.assertIn('if (_anim.empty()) { source.clear(); }',native)
        self.assertIn('{"animationSourceVersion",1}',native)


if __name__=='__main__':unittest.main()
