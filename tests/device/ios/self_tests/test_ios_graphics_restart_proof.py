"""Original iOS restart source join; never a launch ACK or PID-change verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.normal_ui import NativeUIError
from ios.adapters.graphics_restart_proof import validate
from ios.self_tests.test_ios_graphics_measurements import native,NATIVE
from self_tests.test_completed_frame_lease import BINDING


def receipt():
    before=native(1,0);after=native(2,100);after.update(instance='e'*32,processId=43)
    after['lifecycle']=dict(backgrounds=1,activations=2,launches=2)
    old=dict(pid=42,instance=before['instance'],lifecycle=deepcopy(before['lifecycle']))
    new=dict(pid=43,instance=after['instance'],lifecycle=deepcopy(after['lifecycle']))
    plan=dict(restartInputVersion=1,componentOnly=False,oldBinding=deepcopy(BINDING),oldNative=old,phase='observed',
        newBinding=BINDING|dict(processIdentity='43'),newNative=new,ownerFiles=['/owned/scene.json','/owned/primary.json','/owned/actor.json'],scriptHandoff=None)
    exited=dict(processPresenceVersion=1,commandId='ios-'+'f'*32,instance=after['instance'],sequence=1,processId=43,queryProcessId=42,
        requestedEpochMs=NATIVE+110,capturedEpochMs=NATIVE+110,presence='absent',nativeResult=-1,nativeError=3,errorSymbol='ESRCH')
    return dict(input=plan,oldNative=before,native=after,exit=exited)


class RestartProofTests(unittest.TestCase):
    def test_actual_numeric_ios_pid_birth_counters_settings_and_kernel_absence_are_required(self):
        value=receipt();self.assertEqual(value,validate(value));self.assertNotIn(':',value['input']['newBinding']['processIdentity'])
        self.assertGreater(value['native']['capturedEpochMs'],value['oldNative']['capturedEpochMs'])

    def test_launch_ack_reused_birth_unproven_exit_or_changed_settings_cannot_qualify(self):
        faults=[lambda v:v['input'].update(phase='launch-issued'),lambda v:v['native'].update(instance=v['oldNative']['instance']),
            lambda v:v['input']['newNative']['lifecycle'].update(launches=1),lambda v:v['native']['graphics'].update(hazeSetting=True),
            lambda v:v['exit'].update(presence='present',nativeResult=0,nativeError=0,errorSymbol='NONE'),
            lambda v:v['exit'].update(presence='unknown',nativeResult=-1,nativeError=1,errorSymbol='EPERM'),
            lambda v:v['native'].update(requestId='0'*32),lambda v:v['input']['newBinding'].update(artifactSha256='0'*64),
            lambda v:v['input']['newBinding'].update(processIdentity='43:1700000000000')]
        for fault in faults:
            value=receipt();fault(value)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):validate(value)

    def test_changed_session_generation_target_and_foreign_old_pid_are_rejected(self):
        for key,value in (('generation',2),('sessionId','foreign-session'),('targetFingerprint','0'*64)):
            candidate=receipt();candidate['input']['newBinding'][key]=value
            with self.subTest(key=key),self.assertRaises(NativeUIError):validate(candidate)
        candidate=receipt();candidate['exit']['queryProcessId']=44
        with self.assertRaises(NativeUIError):validate(candidate)


if __name__=='__main__':unittest.main()
