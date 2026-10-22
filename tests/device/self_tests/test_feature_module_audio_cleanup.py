"""Actual common module wiring: Audio exchanges once, other 13 areas retain PID."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with patch.dict(os.environ,{'OVERTE_DEVICE_ADAPTER_MANIFEST':'/unused/host-boundary.json','OVERTE_DEVICE_TARGET_SELECTOR':'synthetic-target','OVERTE_DEVICE_ARTIFACT_DIR':'/unused/host-artifacts'}):
    import module_support
from feature_journeys.scenarios import SCENARIOS
from feature_journeys.audio_cleanup import identity


class FeatureModuleAudioCleanupTests(unittest.TestCase):
    def module(self):
        path=Path(__file__).resolve().parents[1]/'modules/feature_journey.py'
        spec=importlib.util.spec_from_file_location('owned_feature_module_audio_cleanup',path);module=importlib.util.module_from_spec(spec)
        with patch.object(module_support,'module_main',lambda *_:None):spec.loader.exec_module(module)
        return module

    def execute(self,area,fault=None):
        module=self.module();state=dict(actual='123:456',reads=0,cleanups=0,guards=[])
        class Session:
            def feature_operation(self,_area,kind,fields):
                if kind=='cleanup':
                    state['cleanups']+=1
                    if area=='audio' and fault!='ignored' or fault=='other-area-switch':
                        state['actual']='456:789' if state['cleanups']==1 or fault!='second' else '789:123'
                return {'performed':True}
        class Client:
            def __init__(self,*_):pass
            def register(self,_):return 'a'*32,'http://127.0.0.1:1/feature-fixture/v1/runs/'+'a'*32+'/'
            def close(self):pass
            def observe(self):raise AssertionError('Unexpected journal request in the module wiring check')
            def activate(self,*_):pass
            def navigation_status(self):raise AssertionError('Unexpected navigation source read in the module wiring check')
        def process():
            state['reads']+=1
            if fault=='foreign' and state['cleanups']:return '999:999'
            return state['actual']
        def guard(value,*_):
            state['guards'].append(value)
            if value!=state['actual']:raise AssertionError('An independently read foreign OS process was adopted')
        class Journey:
            def __init__(self,*_,**kwargs):self.invoke,self.continuity=kwargs['invoke'],kwargs['continuity']
            def execute(self):
                for _ in range(2):
                    self.invoke('feature.'+area+'.cleanup',{});self.continuity('observe',None)
        with tempfile.TemporaryDirectory() as temporary:
            policy=Path(temporary)/'policy.json';policy.write_text(json.dumps({key:{} for key in SCENARIOS}))
            with patch.multiple(module,Client=Client,OverteSession=Session,Journey=Journey,prepare=lambda *_:None,
                    process_identity=process,assert_process=guard,assert_foreground=lambda *_:None),patch.dict(os.environ,{'OVERTE_E2E_FEATURE_IMAGE_POLICY':str(policy)}),patch.object(sys,'argv',['feature_journey.py','--area',area]):
                module.main()
        return state

    def test_all_14_actual_module_compositions_keep_existing_guards_and_audio_adopts_once(self):
        self.assertEqual(14,len(SCENARIOS))
        for area in SCENARIOS:
            with self.subTest(area=area):
                state=self.execute(area);self.assertEqual(2,state['cleanups'])
                self.assertEqual(['456:789']*2 if area=='audio' else ['123:456']*2,state['guards'])

    def test_other_13_areas_reject_replacement_process_during_cleanup(self):
        for area in set(SCENARIOS)-{'audio'}:
            with self.subTest(area=area),self.assertRaises(module_support.AssertionFailure):self.execute(area,'other-area-switch')

    def test_audio_ignored_restart_second_restart_and_foreign_identity_stay_red(self):
        for fault in ('ignored','second','foreign'):
            with self.subTest(fault=fault),self.assertRaises(module_support.AssertionFailure):self.execute('audio',fault)

    def test_missing_boolean_or_unbounded_os_identity_cannot_be_used(self):
        for value in (None,123,True,'','x'*161,'123\n456'):
            with self.subTest(value=value),self.assertRaises(AssertionError):identity('123:456',value,False)


if __name__=='__main__':unittest.main()
