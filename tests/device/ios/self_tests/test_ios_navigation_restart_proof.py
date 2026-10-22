"""Original full candidate/PID/kernel DTOs; kernel and app are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters.navigation_restart_proof import validate, OWNERS
from ios.self_tests.test_ios_graphics_restart_proof import receipt as candidate_receipt


class NavigationRestartProofTests(unittest.TestCase):
    def setUp(self):self.owners=['/owned/'+name for name in OWNERS]
    def receipt(self):
        value=candidate_receipt();value['input']['ownerFiles']=list(self.owners);return value

    def test_original_candidate_birth_and_old_kernel_absence_are_preserved_without_retiming(self):
        value=self.receipt();before=deepcopy(value);proof=validate(value,self.owners)
        self.assertEqual(before,value);self.assertEqual(value,proof)
        self.assertEqual(42,proof['exit']['queryProcessId']);self.assertEqual(43,proof['native']['processId'])
        self.assertIsNone(proof['input']['scriptHandoff'])

    def test_foreign_sibling_old_owner_or_self_reported_file_list_does_not_authorize_worlds_transfer(self):
        for fault in ('foreign-directory','graphics-owner','swapped-roles','relative','parent'):
            value=self.receipt()
            if fault=='foreign-directory':value['input']['ownerFiles']=['/other/'+name for name in OWNERS]
            elif fault=='graphics-owner':value['input']['ownerFiles'][0]='/owned/ios-graphics-scene.json'
            elif fault=='swapped-roles':value['input']['ownerFiles'][1:]=reversed(value['input']['ownerFiles'][1:])
            elif fault=='relative':value['input']['ownerFiles']=[name for name in OWNERS]
            else:value['input']['ownerFiles']=['/owned/../other/'+name for name in OWNERS]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):validate(value,self.owners)
            with self.subTest(selfReported=fault),self.assertRaises(NativeUIError):
                validate(value,value['input']['ownerFiles']) if fault!='foreign-directory' else validate(value,self.owners)

    def test_changed_candidate_session_generation_or_actual_source_cannot_cross_restart(self):
        faults=[lambda v:v['input']['newBinding'].update(artifactSha256='0'*64),
            lambda v:v['input']['newBinding'].update(sourceRevision='0'*40),
            lambda v:v['input']['newBinding'].update(sessionId='foreign-session'),
            lambda v:v['input']['newBinding'].update(generation=2),
            lambda v:v['native'].update(instance=v['oldNative']['instance']),
            lambda v:v['input'].update(phase='launch-issued'),
            lambda v:v['input']['newNative']['lifecycle'].update(launches=1)]
        for fault in faults:
            value=self.receipt();fault(value)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):validate(value,self.owners)

    def test_unproven_old_death_source_counter_or_epoch_is_never_restart_success(self):
        faults=[lambda v:v['exit'].update(presence='present',nativeResult=0,nativeError=0,errorSymbol='NONE'),
            lambda v:v['exit'].update(presence='unknown',nativeResult=-1,nativeError=1,errorSymbol='EPERM'),
            lambda v:v['exit'].update(queryProcessId=44),
            lambda v:v['native'].update(requestedEpochMs=v['oldNative']['capturedEpochMs']-1),
            lambda v:v['exit'].update(instance=v['oldNative']['instance'])]
        for fault in faults:
            value=self.receipt();fault(value)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):validate(value,self.owners)
