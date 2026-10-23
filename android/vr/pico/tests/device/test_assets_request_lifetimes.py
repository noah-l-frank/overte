"""Actual outer/mapping/asset request deaths across original Cancel/Home windows."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import test_assets_entity_resources as resources_module
import test_assets_entity_effect as entity_module
import test_assets_cancel_effects as effects
from adapters.pico4.assets_request_lifetimes import validate_history,require_retired,replay_originals
from adapters.native_feature_observation import decode
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import pack,unpack,canonical,MAX_RAW,MAX_FRAMES


class AssetsRequestLifetimesTests(unittest.TestCase):
    make=entity_module.AssetsEntityEffectTests.make
    cancel_phase=entity_module.AssetsEntityEffectTests.cancel_phase
    pointers=entity_module.AssetsEntityEffectTests.pointers
    inputs=entity_module.AssetsEntityEffectTests.inputs
    model_snapshot=entity_module.AssetsEntityEffectTests.model_snapshot
    exercise=entity_module.AssetsEntityEffectTests.exercise
    @classmethod
    def setUpClass(cls):
        cls.build=tempfile.TemporaryDirectory(prefix='pico-assets-request-life-build-')
        cls.binary,cls.environment,cls.args=effects.compile_ui(cls.build.name,persistent_tablet=True,original_server=True,original_model=True,original_entity=True,original_resources=True,request_lifetimes=True)
        independent=Path(cls.build.name)/'independent';independent.mkdir()
        cls.reader_binary,cls.reader_environment=effects.compile_source(independent)
    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def setUp(self):
        entity_module.AssetsEntityEffectTests.setUp(self)
        self.lifetime_frames=[];self.lifetime_originals=[];self.cancel_quiet=[];self.home_quiet=[]
        self.lifetime_store=PrivateFeatureState(self.path/'request-lifetimes.json');self.life_disk=None
    def preserve(self):
        resources_module.AssetsEntityResourcesTests.preserve(self)
        destination=os.environ.get('OVERTE_ASSETS_EFFECTS_EVIDENCE')
        if destination and hasattr(self,'lifetime_store') and self.lifetime_store.read() is not None:
            PrivateFeatureState(Path(destination).resolve(strict=True)/(self._testMethodName+'-request-lifetimes.json')).write(self.lifetime_store.read(),None)
    def save_lifetimes(self):
        value=dict(assetsRequestLifetimesHostEvidenceVersion=1,binding=deepcopy(self.binding),runId=self.run,
            originals=pack(self.lifetime_originals),cancelQuiet=deepcopy(self.cancel_quiet),homeQuiet=deepcopy(self.home_quiet),
            observerSha256=hashlib.sha256((Path(__file__).resolve().parents[5]/'tests/device/native/AssetsRequestLifetimes.h').read_bytes()).hexdigest())
        self.lifetime_store.write(value,self.life_disk);self.life_disk=deepcopy(value)
    def check(self,retired=False):
        actual=self.lifetime_store.read();self.assertEqual(canonical(self.life_disk),canonical(actual))
        self.assertIs(type(actual['assetsRequestLifetimesHostEvidenceVersion']),int);self.assertEqual(1,actual['assetsRequestLifetimesHostEvidenceVersion'])
        container=self.resources_store.read()['raw'] if hasattr(self,'resources_store') else None
        restored=replay_originals(unpack(actual['originals']),container)
        self.assertEqual(canonical(self.lifetime_frames),canonical(restored))
        if retired:return require_retired(restored,self.host.process.pid,self.run,self.resource_original['resources'])
        return validate_history(restored,self.host.process.pid,self.run)
    def snapshot(self,label=None):
        started=time.monotonic();epoch=self.host.epoch_milliseconds();command=dict(action='host-original-resource-lifetimes',runId=self.run)
        raw=self.host.request(command);value=decode(raw)
        self.lifetime_originals.append(dict(command=command,raw=raw,sha256=hashlib.sha256(raw.encode()).hexdigest()))
        self.lifetime_frames.append(deepcopy(value))
        if label=='cancel':self.cancel_quiet.append(value['sequence'])
        if label=='home':self.home_quiet.append(value['sequence'])
        self.save_lifetimes();self.check(retired=label is not None)
        self.assertLessEqual(time.monotonic()-started,1.5);self.assertTrue(epoch<=value['capturedEpochMs']<=self.host.epoch_milliseconds())
        return value
    def mappings(self):
        result=effects.AssetsCancelEffectsTests.mappings(self)
        if not self.lifetime_frames:self.snapshot()
        return result
    def entity_snapshot(self):
        result=resources_module.AssetsEntityResourcesTests.entity_snapshot(self)
        if hasattr(self,'resource_original') and not getattr(self,'imported_lifetimes',False):
            self.imported_lifetimes=True
            for index,frame in enumerate(self.resource_original['requestLifetimeOriginals']):
                self.lifetime_originals.append(dict(containerSha256=hashlib.sha256(self.resource_disk['raw'].encode()).hexdigest(),field='requestLifetimeOriginals',index=index))
                self.lifetime_frames.append(deepcopy(frame))
            self.save_lifetimes();self.check()
        return result
    def home_owner(self):
        entity_module.AssetsEntityEffectTests.home_owner(self);record=self.home.record
        def observed_record():
            value=record();self.snapshot('home');self.home.freshness();return value
        self.home.record=observed_record
    def exercise_cancel_home(self,baseline):
        sample=self.owner.sample
        def observed_sample():
            value=sample()
            if self.store.read()['phase']=='canceling':self.snapshot('cancel')
            return value
        with patch.object(self.owner,'sample',side_effect=observed_sample):
            counts,raw=resources_module.AssetsEntityResourcesTests.exercise_cancel_home(self,baseline)
        for sequences in (self.cancel_quiet,self.home_quiet):
            frames=[frame for frame in self.lifetime_frames if frame['sequence'] in sequences]
            self.assertGreaterEqual(frames[-1]['capturedEpochMs']-frames[0]['capturedEpochMs'],3000)
            self.assertTrue(all(0<after['capturedEpochMs']-before['capturedEpochMs']<=500 for before,after in zip(frames,frames[1:])))
        # Persist raw originals once. Embedded birth originals already live in
        # the unchanged byte packet; references and transient decoded DTOs are
        # not another physical full-frame archive. Count every original event.
        counts+=len(self.lifetime_frames);raw+=len(canonical(self.lifetime_originals))
        return counts,raw
    def test_actual_original_request_births_child_deaths_and_unmodified_cancel_home_quiet(self):
        self.exercise(True);final=self.check(True);self.assertEqual(9,len(final['objects']))
        self.assertEqual(3,sum(row['kind']=='mapping' for row in final['objects']));self.assertEqual(3,sum(row['kind']=='asset' for row in final['objects']))
        self.assertTrue(all(row['sameThreadAsResource']==(row['kind']=='resource' or getattr(self,'expected_child_same_thread',False)) for row in final['objects']))
        original=deepcopy(self.lifetime_store.read()) # Durable real originals precede counter mutation.
        for counter in ('booleanVersion','missingChild','deadWithoutBirth'):
            values=deepcopy(self.lifetime_frames)
            if counter=='booleanVersion':values[-1]['assetsRequestLifetimesVersion']=True
            if counter=='missingChild':
                missing=next(row['id'] for row in values[-1]['objects'] if row['kind']=='mapping')
                for frame in values:frame['objects']=[row for row in frame['objects'] if row['id']!=missing]
            if counter=='deadWithoutBirth':
                for frame in values:
                    for row in frame['objects']:
                        if row['kind']!='resource':row['alive']=False;row['firstObservedAbsentEpochMs']=row['firstObservedEpochMs']
            with self.subTest(counter=counter),self.assertRaises(NativeUIError):require_retired(values,self.host.process.pid,self.run,self.resource_original['resources'])
        self.assertEqual(original,self.lifetime_store.read())


if __name__=='__main__':unittest.main()
