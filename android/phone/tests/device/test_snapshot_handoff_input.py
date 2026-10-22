"""One-send admission and unchanged Qt receipts with explicit OS/IO seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import unittest
from test_snapshot_controls import Boundary
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_handoff_input import SnapshotHandoffInput
from overte_phone_snapshot_ui import PhoneSnapshotControls

PATH='/data/user/0/io.github.noah_be.overte.phone/files/Snapshots/e2e-'+('a'*32)+'-capture.png'


class Handoff(Boundary):
    def __init__(self,action='share'):
        super().__init__();self.foreground=True;self.system=True;self.sent=[];self.admissions=[];self.admitted=set();self.receipt_fault=None
        self.controls=[dict(id='snapshot.'+action+'.'+hashlib.sha256(PATH.encode()).hexdigest(),token='d'*32,
            enabled=True,focused=False,inputReady=True,path=PATH)]
        io=self.io();original=io.capture();request=io._prepare(self.controls[0]['id'],'activate',reference=original)
        self.plan=dict(request=request,original=original)
        self.owner=dict(snapshotHandoffBindingVersion=1,runId='a'*32,handoffId='e'*32,instance='f'*32,sourceInstance='0'*32,
            processId=31,startedEpochMs=10000,deadlineEpochMs=70000)
    def admit(self,plan,owner):
        key=owner['handoffId']
        if key in self.admitted:return False
        self.admitted.add(key);self.admissions.append(deepcopy((plan,owner)));return True
    def deliver(self,command,planned=None):
        assert self.foreground and self.admissions and self.admissions[-1][0]['request']==command['request']
        self.sent.append(deepcopy(command));self.foreground=False
        if self.ignore:return
        request=command['request'];value={key:request[key] for key in ('schemaVersion','commandId','action','instance','generation','sequence')}
        value.update(processId=31,performed=True)
        if self.receipt_fault:self.receipt_fault(value)
        self.raw=json.dumps(value)
    def reader(self):return SnapshotHandoffInput(self.deliver,lambda:self.raw,lambda:self.epoch,lambda:self.foreground,lambda:self.system,
        31,self.owner,self.admit,monotonic=lambda:self.clock,sleep=self.sleep)


class SnapshotHandoffInputTests(unittest.TestCase):
    def test_actual_os_transition_keeps_one_original_input_receipt_separate_from_effects(self):
        for action in ('share','save'):
            with self.subTest(action=action):
                b=Handoff(action);reader=b.reader();receipt=reader.deliver(b.plan)
                self.assertFalse(b.foreground);self.assertEqual(1,len(b.sent));self.assertEqual(1,len(b.admissions))
                self.assertTrue(receipt['performed']);self.assertNotIn('saved',receipt);self.assertNotIn('shares',receipt)
                self.assertEqual(b.plan['request'],b.sent[0]['request'])
                with self.assertRaises(NativeUIError):reader.deliver(b.plan)
                self.assertEqual(1,len(b.sent))
    def test_reconstructed_sender_cannot_repeat_durably_issued_handoff(self):
        b=Handoff();b.reader().deliver(b.plan);b.foreground=True
        with self.assertRaises(NativeUIError):b.reader().deliver(b.plan)
        self.assertEqual(1,len(b.sent))
    def test_uncertain_missing_receipt_never_repeats_input(self):
        b=Handoff();b.ignore=True;reader=b.reader()
        with self.assertRaises(NativeUIError):reader.deliver(b.plan)
        self.assertEqual(1,len(b.sent));self.assertLessEqual(b.clock,5.1)
        b.foreground=True
        with self.assertRaises(NativeUIError):b.reader().deliver(b.plan)
        self.assertEqual(1,len(b.sent))
    def test_stale_foreign_non_export_or_expected_plan_is_rejected_before_admission(self):
        for fault in ('stale','path','control','token','instance','generation','sequence','pid','disabled','ready','desired'):
            with self.subTest(fault=fault):
                b=Handoff();value=deepcopy(b.plan)
                if fault=='stale':b.epoch+=1500
                elif fault=='path':value['original']['controls'][0]['path']='/tmp/foreign.png'
                elif fault=='control':value['request']['controlId']='snapshot.capture'
                elif fault in ('token','instance','generation'):value['request'][{'token':'controlToken'}.get(fault,fault)]='9'*32
                elif fault=='sequence':value['request']['sequence']+=1
                elif fault=='pid':value['original']['processId']=99
                elif fault=='disabled':value['original']['controls'][0]['enabled']=False
                elif fault=='ready':value['original']['controls'][0]['inputReady']=False
                else:value['request']['expectedSaved']=True
                with self.assertRaises(NativeUIError):b.reader().deliver(value)
                self.assertEqual([],b.sent);self.assertEqual([],b.admissions)
    def test_current_foreground_and_original_os_scope_are_mandatory(self):
        b=Handoff();b.foreground=False
        with self.assertRaises(NativeUIError):b.reader().deliver(b.plan)
        self.assertEqual([],b.sent)
        b=Handoff();b.system=False
        with self.assertRaises(NativeUIError):b.reader().deliver(b.plan)
        self.assertEqual(1,len(b.sent)) # No retry after the single uncertain write.
    def test_foreign_incomplete_or_expected_receipt_is_never_delivery(self):
        for field,value in (('commandId','9'*32),('instance','9'*32),('generation','9'*32),('sequence',2),
                ('processId',99),('performed',False),('action','save'),('expectedSaved',True)):
            with self.subTest(field=field):
                b=Handoff();b.receipt_fault=lambda row:row.update({field:value})
                with self.assertRaises(NativeUIError):b.reader().deliver(b.plan)
                self.assertEqual(1,len(b.sent))
    def test_slow_durable_admission_cannot_click_with_expired_lease_or_stale_plan(self):
        for fault in ('lease','plan'):
            with self.subTest(fault=fault):
                b=Handoff();reader=b.reader();admit=reader.admit
                def delay(value,owner):
                    result=admit(value,owner);b.epoch+=60000 if fault=='lease' else 1600;return result
                reader.admit=delay
                with self.assertRaises(NativeUIError):reader.deliver(b.plan)
                self.assertEqual([],b.sent);self.assertEqual(1,len(b.admissions))
    def test_readonly_receipt_recovery_sends_no_command_or_new_admission(self):
        b=Handoff();original=b.reader().deliver(b.plan);reader=b.reader()
        reader.send=lambda *_:self.fail('Recovery must not send')
        reader.admit=lambda *_:self.fail('Recovery must not admit')
        self.assertEqual(original,reader.observe(b.plan));self.assertEqual(1,len(b.sent))

    def test_final_os_guard_cannot_qualify_receipt_after_original_deadline(self):
        b=Handoff();reader=b.reader();calls=0
        def guard():
            nonlocal calls
            calls+=1
            if calls==3:b.epoch=reader.owner['deadlineEpochMs']
            return True
        reader.system_guard=guard
        with self.assertRaises(NativeUIError):reader.deliver(b.plan)
        self.assertEqual(1,len(b.sent))

    def test_real_factory_writes_only_fixed_normal_channel_after_foreground_admission(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from appium_adapter import PhoneAppiumAdapter
        b=Handoff();application=dict(processIdentity='31:1');adapter=PhoneAppiumAdapter.__new__(PhoneAppiumAdapter)
        adapter.candidate=object();guards=[];writes=[]
        def foreground():guards.append('foreground');return b.foreground
        adapter.normal_feature_runtime=lambda *_args,**_kwargs:(None,None,application,foreground,dict(sha256='a'*64))
        adapter.installed_identity=lambda _:dict(sha256='a'*64)
        adapter._snapshot_system_context=lambda *_args:SimpleNamespace(guard=lambda:b.system)
        adapter.target=lambda _:dict(appId='io.github.noah_be.overte.phone',capabilities={'appium:udid':'explicit-synthetic-only'})
        adapter.existing_session=lambda _:(None,'session',None)
        adapter.android_client_identity=lambda *_:dict(running=True,identity='31:1')
        def write(device,package,path,raw):
            self.assertTrue(b.foreground);self.assertTrue(b.admissions)
            writes.append((package,path));b.deliver(json.loads(raw))
        sdk=SimpleNamespace(write_debug_app_file=write,read_debug_app_file=lambda *_args,**_kwargs:b.raw,
            epoch_milliseconds=lambda _:b.epoch)
        with patch('appium_adapter.PhoneAdapter',return_value=SimpleNamespace(adb=sdk)):
            reader=adapter._snapshot_handoff_input('own',application,{},lambda:True,b.owner,b.admit)
            original=reader.deliver(b.plan)
        self.assertEqual([('io.github.noah_be.overte.phone',adapter.ANDROID_CLIENT_COMMAND)],writes)
        self.assertFalse(b.foreground);self.assertTrue(original['performed']);self.assertGreaterEqual(len(guards),3)

    def test_slow_source_and_expired_original_job_remain_red(self):
        b=Handoff();reader=b.reader();original=reader.read
        def slow():b.clock+=5;return original()
        reader.read=slow
        with self.assertRaises(NativeUIError):reader.deliver(b.plan)
        b=Handoff();b.owner['deadlineEpochMs']=b.epoch
        # Binding grammar rejects altered lifetime before any input.
        with self.assertRaises((RuntimeError,ValueError)):b.reader()


if __name__=='__main__':unittest.main()
