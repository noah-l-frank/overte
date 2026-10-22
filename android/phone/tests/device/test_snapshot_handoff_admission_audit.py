"""Independent OS-input admission counterprobes over original Phone factories.

The Android SDK, native process and private IO are explicit synthetic seams.
No device or owner worktree is touched. No effect is inferred from a receipt.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_snapshot_handoff_input import Handoff
import test_feature_adapters as bound
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_system_context import SnapshotSystemContext,PRIMARY,RECEIVER_COMPONENT
from overte_phone_snapshot_documents_ui import SnapshotDocumentContext
from test_snapshot_system_context import BINDING,Source
from test_snapshot_documents_ui import Boundary as Documents,COMPONENT as DOCUMENT_COMPONENT


class SnapshotHandoffAdmissionAuditTests(unittest.TestCase):
    def test_original_lease_expiring_during_admission_prevents_the_single_write(self):
        b=Handoff();b.epoch=69960;b.clock=59.96
        io=b.io();original=io.capture();request=io._prepare(b.controls[0]['id'],'activate',reference=original)
        b.plan=dict(request=request,original=original);admit=b.admit
        def slow(value,owner):
            result=admit(value,owner);b.epoch+=50;b.clock+=.05;return result
        b.admit=slow
        with self.assertRaises(NativeUIError):b.reader().deliver(b.plan)
        self.assertEqual(1,len(b.admissions));self.assertEqual([],b.sent)

    def test_original_plan_becoming_stale_during_durable_admission_prevents_write(self):
        b=Handoff();admit=b.admit
        def slow(value,owner):
            result=admit(value,owner);b.epoch+=1600;b.clock+=1.6;return result
        b.admit=slow
        with self.assertRaises(NativeUIError):b.reader().deliver(b.plan)
        self.assertEqual([],b.sent)

    def test_original_lease_expiring_in_final_os_guard_cannot_qualify_receipt(self):
        b=Handoff();b.epoch=69960;b.clock=59.96
        io=b.io();original=io.capture();request=io._prepare(b.controls[0]['id'],'activate',reference=original)
        b.plan=dict(request=request,original=original);reader=b.reader();calls=[0]
        def system():
            calls[0]+=1
            if calls[0]==3:b.epoch+=100;b.clock+=.1
            return b.system
        reader.system_guard=system
        with self.assertRaises(NativeUIError):reader.deliver(b.plan)
        self.assertEqual(1,len(b.sent)) # Input was admitted while the lease lived.

    def test_actual_factory_rechecks_candidate_bytes_after_admission_before_write(self):
        fixture=bound.FeatureAdapterTests('test_existing_input_scope_admits_normal_file_input_without_parent_session_repair')
        fixture.setUp();self.addCleanup(fixture.doCleanups);fixture.read_only_boundaries()
        adapter=fixture.adapter
        _ui,_observe,application,_guard,_installed=adapter.normal_feature_runtime(bound.SELECTOR,read_only=True)
        b=Handoff();writes=[];admit=b.admit
        def replace(value,owner):
            result=admit(value,owner);fixture.fixture.adb.digest='0'*64;return result
        def write(device,package,path,raw):
            writes.append((package,path));b.deliver(json.loads(raw))
        # The actual lifecycle status still rehashes the installed APK, kernel
        # process and SDK session. Only component selection is synthetic here.
        def system():adapter._graphics_lifecycle_status(bound.SELECTOR,application);return True
        with (patch.object(adapter,'_snapshot_system_context',return_value=SimpleNamespace(guard=system)),
                patch.object(adapter,'android_client_identity',side_effect=lambda *_:dict(running=fixture.native.running,identity=fixture.native.identity)),
                patch.object(fixture.fixture.adb,'write_debug_app_file',side_effect=write,create=True),
                patch.object(fixture.fixture.adb,'read_debug_app_file',side_effect=lambda *_args,**_kwargs:b.raw)):
            reader=adapter._snapshot_handoff_input(bound.SELECTOR,application,{},lambda:True,b.owner,replace)
            with self.assertRaises((ValueError,RuntimeError)):reader.deliver(b.plan)
        self.assertEqual(1,len(b.admissions));self.assertEqual([],writes)


class SnapshotHandoffCompositionAuditTests(unittest.TestCase):
    def scope(self,b,action):
        source=Source()
        source.value.update(foreground=True,appState=4)
        source.component=PRIMARY+'/'+PRIMARY+'.MainActivity'
        resolution=Documents().resolve() if action=='save' else source.reader.chooser
        cls=SnapshotDocumentContext if action=='save' else SnapshotSystemContext
        source.reader=cls(BINDING,resolution,source.status,lambda:source.component,lambda:source.authorized,
            monotonic=lambda:b.clock)
        return source

    def sender(self,b,source,after):
        reader=b.reader();deliver=reader.send
        def send(command,planned):
            # Exactly the actual factory order: foreground -> narrow context
            # before write; unchanged receipt may be read under OS scope.
            source.reader.guard();deliver(command,planned)
            source.value.update(foreground=False,appState=3);source.component=after
        reader.send=send;reader.system_guard=source.reader.guard
        return reader

    def test_primary_to_exact_original_chooser_or_documents_uses_one_click(self):
        for action in ('share','save'):
            b=Handoff(action);source=self.scope(b,action)
            destination=DOCUMENT_COMPONENT if action=='save' else source.reader.chooser['component']
            reader=self.sender(b,source,destination)
            with self.subTest(action=action):
                original=reader.deliver(b.plan)
                self.assertEqual(1,len(b.sent));self.assertFalse(b.foreground)
                self.assertEqual(original,reader.observe(b.plan))
                self.assertEqual(1,len(b.sent));self.assertEqual(1,len(b.admissions))
                self.assertNotIn('saved',original);self.assertNotIn('shares',original)

    def test_foreign_os_window_or_changed_original_owner_never_qualifies_or_reissues(self):
        for action,fault in ((a,f) for a in ('share','save') for f in ('foreign','wrong-activity','wrong-kind','authority',*BINDING)):
            b=Handoff(action);source=self.scope(b,action)
            destination=DOCUMENT_COMPONENT if action=='save' else source.reader.chooser['component']
            reader=self.sender(b,source,destination);send=reader.send
            def mutate(command,planned):
                send(command,planned)
                if fault=='foreign':source.component='foreign.app/foreign.app.Window'
                elif fault=='wrong-activity':source.component=destination.split('/')[0]+'/foreign.Activity'
                elif fault=='wrong-kind':source.component=RECEIVER_COMPONENT if action=='save' else DOCUMENT_COMPONENT
                elif fault=='authority':source.authorized=False
                else:source.value['binding'][fault]=2 if fault=='generation' else 'foreign'
            reader.send=mutate
            with self.subTest(action=action,fault=fault):
                with self.assertRaises(NativeUIError):reader.deliver(b.plan)
                with self.assertRaises(NativeUIError):reader.observe(b.plan)
                with self.assertRaises(NativeUIError):reader.deliver(b.plan)
                self.assertEqual(1,len(b.sent));self.assertEqual(1,len(b.admissions))

    def test_lost_write_return_recovers_archived_receipt_without_retiming_or_resending(self):
        b=Handoff();source=self.scope(b,'share');reader=self.sender(b,source,source.reader.chooser['component'])
        send=reader.send
        def lost(command,planned):send(command,planned);raise OSError('synthetic lost write reply')
        reader.send=lost
        with self.assertRaises(NativeUIError):reader.deliver(b.plan)
        plan=deepcopy(b.plan);original=json.loads(b.raw)
        b.epoch+=2000;b.clock+=2 # Original widget plan now too old for new input.
        recovery=b.reader();recovery.system_guard=source.reader.guard
        recovery.send=lambda *_:self.fail('Readonly recovery cannot write')
        recovery.admit=lambda *_:self.fail('Readonly recovery cannot admit')
        recovery.foreground_guard=lambda:self.fail('OS recovery cannot request foreground admission')
        self.assertEqual(original,recovery.observe(plan));self.assertEqual(plan,b.plan)
        self.assertEqual(1,len(b.sent));self.assertEqual(1,len(b.admissions))
        b.foreground=True
        with self.assertRaises(NativeUIError):b.reader().deliver(plan)
        self.assertEqual(1,len(b.sent))

    def test_recovery_rejects_changed_original_receipt_and_real_expired_lease(self):
        for fault in ('pid','command','sequence','performed','expired','missing'):
            b=Handoff();b.reader().deliver(b.plan);original=json.loads(b.raw)
            if fault=='expired':b.epoch=b.owner['deadlineEpochMs']
            elif fault=='missing':b.raw=''
            else:
                key={'pid':'processId','command':'commandId','performed':'performed','sequence':'sequence'}[fault]
                original[key]={'pid':32,'command':'9'*32,'performed':False,'sequence':99}[fault]
                b.raw=json.dumps(original)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.reader().observe(b.plan)
            self.assertEqual(1,len(b.sent));self.assertEqual(1,len(b.admissions))

    def test_initial_expired_original_lease_and_denied_prewrite_scope_never_write(self):
        b=Handoff();b.epoch=69960;b.clock=59.96
        io=b.io();original=io.capture();request=io._prepare(b.controls[0]['id'],'activate',reference=original)
        b.plan=dict(request=request,original=original);b.epoch=70000
        with self.assertRaises(NativeUIError):b.reader().deliver(b.plan)
        self.assertEqual([],b.sent);self.assertEqual([],b.admissions)
        b=Handoff();source=self.scope(b,'share');source.authorized=False
        reader=self.sender(b,source,source.reader.chooser['component'])
        with self.assertRaises(NativeUIError):reader.deliver(b.plan)
        self.assertEqual([],b.sent);self.assertEqual(1,len(b.admissions))
        source.authorized=True
        with self.assertRaises(NativeUIError):reader.deliver(b.plan)
        self.assertEqual([],b.sent) # Issued admission remains uncertain, never replayed.

    def test_normal_receipt_plus_unchanged_passive_native_state_cannot_prove_save_or_share(self):
        from test_snapshots_measurements import saved_original,shared_original,ARM,RUN
        from overte_phone_snapshots_measurements import saved,shared
        for action in ('save','share'):
            b=Handoff(action);receipt=b.reader().deliver(b.plan)
            self.assertTrue(receipt['performed']);self.assertEqual(1,len(b.sent))
            # Explicit synthetic independent native/OS seams retain the actual
            # pre-input callback stream. A Qt click receipt cannot fill it.
            if action=='save':
                before,after,readback,acquired,captured=saved_original()
                after['snapshot']['source']['androidExport']=deepcopy(before['snapshot']['source']['androidExport'])
                with self.assertRaises(NativeUIError):saved(after['snapshot'],before['snapshot'],readback,acquired,captured,epoch=20000)
            else:
                before,after,readback,consumer,binding,acquired,captured=shared_original()
                after['snapshot']['source']['androidExport']=deepcopy(before['snapshot']['source']['androidExport'])
                with self.assertRaises(NativeUIError):shared(after['snapshot'],before['snapshot'],readback,consumer,binding,acquired,captured,run=RUN,arm=ARM,epoch=20000)

    def test_actual_readonly_factory_never_constructs_foreground_runtime_or_writes(self):
        from appium_adapter import PhoneAppiumAdapter
        b=Handoff();original=b.reader().deliver(b.plan);application=dict(processIdentity='31:1')
        adapter=PhoneAppiumAdapter.__new__(PhoneAppiumAdapter);adapter.candidate=object()
        adapter.normal_feature_runtime=lambda *_args,**_kwargs:self.fail('OS recovery cannot create foreground runtime')
        adapter._snapshot_system_context=lambda *_:SimpleNamespace(guard=lambda:b.system)
        adapter.target=lambda _:dict(appId=PRIMARY,capabilities={'appium:udid':'explicit-synthetic-only'})
        adapter.existing_session=lambda _:(None,'original',None)
        sdk=SimpleNamespace(read_debug_app_file=lambda *_args,**_kwargs:b.raw,epoch_milliseconds=lambda _:b.epoch,
            write_debug_app_file=lambda *_:self.fail('Readonly factory cannot write'))
        with patch('appium_adapter.PhoneAdapter',return_value=SimpleNamespace(adb=sdk)):
            reader=adapter._snapshot_handoff_input('own',application,{},lambda:True,b.owner,
                lambda *_:self.fail('Readonly recovery cannot admit'),read_only=True)
            self.assertEqual(original,reader.observe(b.plan))
        self.assertEqual(1,len(b.sent));self.assertEqual(1,len(b.admissions))


if __name__=='__main__':unittest.main()
