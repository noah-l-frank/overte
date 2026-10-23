"""Strict V1/V2 admission and final clocks; all native/GUI/Account seams modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.native_navigation_environment import validate,continuation
from adapters.normal_ui import NativeUIError
from self_tests.test_navigation_origin import Model,RUN


class NavigationEnvironmentTests(unittest.TestCase):
    def setUp(self):
        stage=tempfile.TemporaryDirectory();self.addCleanup(stage.cleanup);self.model=Model(Path(stage.name))
    def reader(self):
        model=self.model;reader=model.reader();original=reader.send
        def send(request):
            original(request);value=model.packet;value['navigationEnvironmentVersion']=2;value['accountServer']=model.effective
            value['settings']=dict(navigationSettingsEntriesVersion=1,instance='a'*32,capturedEpochMs=model.epoch(),selectedPresent=model.present,
                selectedType='url' if model.present else 'absent',rawSettingsSha256='c'*64,otherSettingsSha256=model.other,handlesAbsent=True)
            value['ui'].update(open=True,ready=True)
        reader.send=send;return reader
    @staticmethod
    def check(value):
        return validate(value,dict(schemaVersion=1,commandId=value['commandId'],runId=RUN,action='feature-navigation-environment'),123,value['capturedEpochMs'])
    def test_v1_original_remains_readable_but_native_birth_cannot_silently_change_version(self):
        old=self.model.reader().read(RUN);self.check(old);new=self.reader().read(RUN);self.check(new)
        with self.assertRaises(NativeUIError):continuation(old,new)
    def test_v2_runtime_account_typed_raw_identity_and_closed_ui_consistency_are_strict(self):
        original=self.reader().read(RUN)
        changes=[lambda v:v.update(accountServer='https://foreign.invalid/server'),
            lambda v:v['account']['observation'].update(endpointSha256='f'*64),
            lambda v:v['settings'].update(handlesAbsent=1),lambda v:v['settings'].update(navigationSettingsEntriesVersion=True),
            lambda v:v['settings'].update(selectedType='absent'),lambda v:v['settings'].update(otherSettingsSha256='f'*64),
            lambda v:v['settings'].update(capturedEpochMs=v['capturedEpochMs']+1),lambda v:v['ui'].update(open=False,ready=True),
            lambda v:v['ui'].update(open=False,ready=False)]
        for change in changes:
            value=deepcopy(original);change(value)
            with self.subTest(change=change),self.assertRaises(NativeUIError):self.check(value)
        closed=deepcopy(original);closed['ui'].update(open=False,ready=False,loginPageAlive=False,passwordEmpty=None,serverDraftSha256=None,serverFocused=None)
        self.check(closed);self.assertEqual(original['settings']['rawSettingsSha256'],closed['settings']['rawSettingsSha256'])
    def test_final_native_guard_clock_jump_refuses_before_retaining_a_success(self):
        reader=self.reader();calls=[];offset=[0]
        def guard():
            calls.append(True)
            if len(calls)==4:offset[0]=2000
            return True
        reader.guard=guard;reader.clock_ms=lambda:self.model.epoch()+offset[0]
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual(2000,offset[0]);self.assertIsNone(reader.last)
        self.assertEqual(20000,self.model.packet['capturedEpochMs'])
    def test_slow_final_copy_cannot_borrow_frozen_native_clock(self):
        reader=self.reader();reader.clock_ms=lambda:20000;original=deepcopy;changed=[]
        def copy(value):
            result=original(value)
            if type(value) is dict and value.get('navigationEnvironmentVersion')==2 and not changed:
                self.model.clock+=2;changed.append(True)
            return result
        with patch('adapters.native_navigation_environment.deepcopy',side_effect=copy),self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertTrue(changed);self.assertIsNone(reader.last);self.assertEqual(20000,self.model.packet['capturedEpochMs'])
    def test_returned_value_does_not_mutate_retained_continuation(self):
        reader=self.reader();value=reader.read(RUN);digest=hashlib.sha256(json.dumps(reader.last,sort_keys=True).encode()).hexdigest()
        value['settings']['instance']='f'*32;value['account']['observation']['events'].append({})
        self.assertEqual(digest,hashlib.sha256(json.dumps(reader.last,sort_keys=True).encode()).hexdigest());reader.read(RUN)


if __name__=='__main__':unittest.main()
