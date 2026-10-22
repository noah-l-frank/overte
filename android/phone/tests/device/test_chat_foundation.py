"""Run the mandatory original text module over explicit host native seams.

The original shared adapter, session contracts and module execute. The transport,
OS/foreground and probe producers are synthetic; no ADB/device operation runs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
with patch.dict(os.environ,OVERTE_DEVICE_ADAPTER_MANIFEST='/unused/host.json',OVERTE_DEVICE_TARGET_SELECTOR='synthetic-chat',OVERTE_DEVICE_ARTIFACT_DIR='/tmp'):
    import module_support
    from overte_session import OverteSession
from self_tests import test_native_text_binding as boundary
from self_tests.test_vertical_locomotion import snapshot
from feature_journeys.scenarios import FOUNDATIONS


def execute_foundation(case,fault=None):
    original=boundary.NativeTextBindingTests();original.setUp()
    try:
        spec=importlib.util.spec_from_file_location('chat_original_text_module',ROOT/'tests/device/modules/text_input.py')
        module=importlib.util.module_from_spec(spec)
        with patch.object(module_support,'module_main',lambda *_:None):spec.loader.exec_module(module)
        session=object.__new__(OverteSession);session.timeout_seconds=.02;session.poll_seconds=.001;session._last_sample_sequence=None
        samples=[];reports=[];calls=[];guards=[]
        def operation(name,fields):
            calls.append(name)
            if name=='probe.snapshot':
                result=snapshot();result['sampleSequence']=len(samples)+1
                if samples and fault=='world-drift':result['avatar']['position']['x']+=1
                samples.append(result);return result
            if name=='text.type':
                if fault=='input-ack-only':return {'performed':True}
                return original.adapter.android_type_text(original.client,'session',original.target,fields)
            action={'text.focus':'focus','text.snapshot':'snapshot','text.dismiss':'dismiss'}[name]
            result=original.adapter.android_text_state(original.client,'session',original.target,action)
            return result if action=='snapshot' else {'performed':True}
        if fault=='missing-keyboard':original.bad={'snapshot':dict(schemaVersion=1,value='',focused=True,submittedCount=0,keyboardVisible=None)}
        with patch.multiple(module,OverteSession=lambda:session,process_identity=lambda:'host-process:original',
                assert_process=lambda identity,*_:guards.append(identity),assert_foreground=lambda *_:None,
                write_json=lambda name,value:reports.append((name,value))),patch('overte_session.operation',side_effect=operation),patch('overte_session.write_json',side_effect=lambda name,value:reports.append((name,value))):
            module.main()
        case.assertEqual(['text-input'],FOUNDATIONS['chat']);case.assertEqual(['host-process:original'],guards)
        case.assertEqual(['probe.snapshot','text.focus','text.snapshot','text.type','text.snapshot','text.dismiss','text.snapshot','probe.snapshot'],calls)
        case.assertEqual('Overte E2E äöü',original.value);case.assertEqual(['67','66'],original.keycodes)
        case.assertFalse(original.focused);case.assertEqual(5,len(reports));case.assertEqual(2,len(samples))
    finally:original.doCleanups()


class ChatFoundationTests(unittest.TestCase):
    def test_original_mandatory_module_uses_unicode_submit_native_keyboard_and_world_isolation(self):execute_foundation(self)
    def test_input_ack_and_missing_keyboard_cannot_satisfy_original_module(self):
        for fault in ('input-ack-only','missing-keyboard'):
            with self.subTest(fault=fault),self.assertRaises((module_support.AssertionFailure,RuntimeError)):execute_foundation(self,fault)
    def test_actual_probe_world_drift_prevents_foundation_success(self):
        with self.assertRaises(module_support.AssertionFailure):execute_foundation(self,'world-drift')


if __name__=='__main__':unittest.main()
