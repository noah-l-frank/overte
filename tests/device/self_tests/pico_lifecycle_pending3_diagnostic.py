"""Actual Pending3 original owner, original host/FS/OFD and declared Qt/SDK.

No eighth normal action, independent Actor join or complete Lifecycle claim.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import os
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_background_owner import PicoLifecycleBackground
from adapters.pico4.lifecycle_namespace_bill import LifecycleNamespaceBill
from adapters.pico4.lifecycle_source_raw import LifecycleSourceRaw4,LifecycleSourceRawHistory4
from adapters.pico4.lifecycle_pending import PicoLifecyclePending
from adapters.pico4.lifecycle_pending_read import body_original
from adapters.script_journey.history import unpack
from self_tests.pico_lifecycle_host_model import OriginalHostModel
from self_tests.test_pico_lifecycle_chat import LifecycleChatTests
from self_tests.test_pico_lifecycle_background_owner import LifecycleBackgroundOwnerTests
from self_tests.test_pico_lifecycle_pending import LifecyclePendingTests


class LifecyclePending3FamilyTests(unittest.TestCase):
    BACKGROUND_STATE_LAYOUT=None
    BACKGROUND_QUIET_PERIOD=None
    def test_born_host_controls_advance_real_clock_and_keep_the_existing_exact_reference_contract(self):
        import time
        from adapters.token_chat_ui import same_reference
        context=OriginalHostModel();widgets=context.chat();widgets.panel=True
        before=widgets.capture();time.sleep(.005);after=widgets.capture()
        self.assertEqual(context.pid,before['scope']['processId'])
        self.assertGreater(after['scope']['elapsedMs'],before['scope']['elapsedMs'])
        same_reference(before,after,'chat.input')

    def fixture(self):
        self.context=OriginalHostModel()
        import json,tempfile
        from pathlib import Path
        (Path(tempfile.gettempdir())/'pending3-born-host-config.json').write_text(json.dumps(dict(
            actualHostIdentity=self.context.host,actualNativeModelPid=self.context.pid,
            processIdentity=self.context.process_identity,originMonotonic=self.context.origin,
            bornEpochMs=self.context.created_epoch,backgroundStateLayout=4 if self.BACKGROUND_STATE_LAYOUT is None else self.BACKGROUND_STATE_LAYOUT,
            rawLayout=4,pendingReadProfile=1,pendingOwnerLayout=3,uiLayout=2,fieldBindingVersion=1,
            pendingWireVersion=1,maximumPendingBodyBytes=32768,maximumWireBytes=36864,
            maximumOriginalReads=512,maximumOriginalParts=512,maximumGlobalBytes=16*1024*1024,
            maximumRootBytes=65536,outerOwningSeconds=120,nativeExchangeSeconds=5,
            sourceAcquisitionSeconds=1.5,pendingActionSeconds=20,quietSeconds=3,
            cadenceSeconds=.25,maximumNativeHistoryGapSeconds=.5,
            nativeAndQt='Declared host models; host PID/start/clocks/kernel filesystem are actual'),indent=2)+'\n')
        self.chat=LifecycleChatTests();self.chat.setUp(model_context=self.context);self.addCleanup(self.chat.doCleanups)
        self.chat.owner.open_chat();self.chat.owner.focus_chat();self.chat.owner.type_chat()
        self.background=LifecycleBackgroundOwnerTests();background=self.background
        def expanded():
            owners=[self.chat.fixture.owner,self.chat.joined,self.chat.joined.world,self.chat.joined.back,self.chat.owner]
            owners.extend(getattr(holder,'owner',None) for holder in (background,getattr(self,'pending',None)) if holder is not None)
            result=[];seen=set()
            for owner in owners:
                value=getattr(owner,'state',None)
                if value is not None and id(value) not in seen:result.append(value);seen.add(id(value))
            return result or None
        def make():
            self.namespace=LifecycleNamespaceBill(background.root,background.lock,mutex_layout=2,expanded=expanded)
            self.addCleanup(self.namespace.close)
            self.bank=LifecycleSourceRaw4(background.root/'lifecycle-background-raw.json',background.chat.run,
                background.chat.binding,background.lock,background.lock.assert_held,self.namespace,
                self.context.now,pending_read_version=1,capacity_batches=True)
            self.addCleanup(self.bank.close_host)
            return PicoLifecycleBackground(background.root/'lifecycle-background-owner.json',background.chat.run,
                background.chat.binding,background.lock,background.status,background.os_input,background.runtime,
                monotonic=self.context.now,sleep=background.sleep,raw_layout=self.bank,quiet_period=self.BACKGROUND_QUIET_PERIOD,
                **({} if self.BACKGROUND_STATE_LAYOUT is None else dict(state_layout=self.BACKGROUND_STATE_LAYOUT)))
        background.make=make;background.initialize_from_chat(self.chat);self.addCleanup(background.doCleanups)
        background.owner.prepare(background.chat);background.owner.run_owned()
        self.pending=LifecyclePendingTests();self.pending.initialize_from_background(background);self.addCleanup(self.pending.doCleanups)
        self.owner=self.pending.owner
        self.assertIs(type(self.owner),PicoLifecyclePending);self.assertEqual(3,self.owner.version)
        self.assertEqual(self.context.process_identity,self.owner.binding['processIdentity'])
        self.assertEqual(self.context.pid,self.owner.pid);self.assertIs(self.owner.originals,self.bank)
        self.assertTrue(self.owner.world.source._field_bindings)
        self.assertEqual([],self.pending.pending_sdk.calls)

    def latest_wire(self):
        archive=self.bank.archive;read=archive.state['reads']-1
        record=archive.pages[read//32]['receipts'][read%32]
        reference=dict(audioRawRangeVersion=1,scopeSha256=archive.scope_sha,read=read,sha256=record['sha256'])
        with self.owner.lock.held():wire=archive.literal(reference)
        return wire,record

    def test_diagnostic_actual_first_two_final_quiet_samples_keep_original_clocks_and_profile_storage(self):
        import json
        import tempfile
        import time
        from contextlib import ExitStack
        from pathlib import Path
        from adapters.pico4.lifecycle_family_gate import LifecycleFamilyGate4
        from adapters.pico4.lifecycle_write_gate import LifecycleWriteGate
        measured={};stopped=[]
        def wrapper(label,original):
            def call(*args,**kwargs):
                started=time.perf_counter()
                try:return original(*args,**kwargs)
                finally:
                    row=measured.setdefault(label,[0,0.]);row[0]+=1;row[1]+=time.perf_counter()-started
            return call
        save=PicoLifecycleBackground.save
        def stop(owner,state):
            result=save(owner,state)
            if state['phase']=='release-issued' and len(state['finalQuiet'])==2:
                stopped.append(True);raise OSError('Intentional diagnostic end after two genuine final-quiet originals')
            return result
        try:
            with ExitStack() as patches:
                for cls,name in ((LifecycleNamespaceBill,'__call__'),(LifecycleSourceRaw4,'_verify'),
                        (LifecycleFamilyGate4,'save'),(LifecycleWriteGate,'before_state'),(LifecycleWriteGate,'after')):
                    patches.enter_context(patch.object(cls,name,wrapper(cls.__name__+'.'+name,getattr(cls,name))))
                patches.enter_context(patch.object(PicoLifecycleBackground,'save',stop))
                with self.assertRaises(NativeUIError):self.fixture()
            self.assertTrue(stopped,'Diagnostic must reach its actual observed stop, not accept an earlier failure')
        finally:
            owner=getattr(getattr(self,'background',None),'owner',None)
            report=dict(measured=measured,diagnosticOnly=True,actualStopReached=bool(stopped))
            if owner is not None:
                report.update(phase=owner.state['phase'],quietHosts=[row['hostMonotonic'] for row in owner.state['quiet']],
                    finalQuietHosts=[row['hostMonotonic'] for row in owner.state['finalQuiet']],
                    rawReads=self.bank.archive.state['reads'],rawBill=self.bank.archive.bill(),namespaceMaximum=self.namespace.maximum)
            (Path(tempfile.gettempdir())/'pending3-actual-storage-profile.json').write_text(json.dumps(report,indent=2)+'\n')

    def test_diagnostic_original_failure_before_sanitizers_is_retained_without_any_scope_retry(self):
        import json
        import tempfile
        import traceback
        from contextlib import ExitStack
        from pathlib import Path
        from adapters.pico4.lifecycle_family_gate import LifecycleFamilyGate4
        from adapters.pico4.lifecycle_capacity_pass import LifecycleCapacityPass
        errors=[]
        def wrap(label,original):
            def call(*args,**kwargs):
                try:return original(*args,**kwargs)
                except BaseException:
                    if not errors:errors.append(dict(method=label,traceback=traceback.format_exc()))
                    raise
            return call
        try:
            with ExitStack() as patches:
                for cls,name in ((PicoLifecycleBackground,'fresh'),(PicoLifecycleBackground,'validate'),
                        (PicoLifecycleBackground,'capture'),(PicoLifecycleBackground,'bound'),
                        (LifecycleCapacityPass,'current'),(LifecycleFamilyGate4,'save'),(LifecycleNamespaceBill,'__call__')):
                    patches.enter_context(patch.object(cls,name,wrap(cls.__name__+'.'+name,getattr(cls,name))))
                self.fixture();self.owner.prepare()
        finally:
            report=dict(diagnosticOnly=True,errors=errors)
            if hasattr(self,'bank'):
                report.update(bankFailed=self.bank.failed,passFailed=self.bank._capacity_pass.failed,
                    passReuses=self.bank._capacity_pass.reuses,passFullAudits=self.bank._capacity_pass.full_audits)
            (Path(tempfile.gettempdir())/'pending3-original-failure.json').write_text(json.dumps(report,indent=2)+'\n')

    def test_real_owner_prepared_state_body_manifest_original_bank_and_fresh_after_actual_outer_exit(self):
        self.fixture();self.owner.prepare()
        self.assertEqual('prepared',self.owner.state['phase']);self.assertEqual(3,self.owner.disk['lifecyclePendingOwnerVersion'])
        self.assertNotIn('originalStamp',self.owner.disk);self.assertIs(self.bank,self.background.owner.originals)
        self.assertFalse(self.owner.store.path.with_name('lifecycle-pending-originals.json').exists())
        self.assertIs(self.bank.return_slot,self.owner.return_pins)
        self.assertEqual('pending',self.owner.return_pins.role);self.owner.return_pins.verify_data()
        self.assertEqual(1,len(self.pending.pending_sdk.calls));self.assertEqual(1,len(self.pending.pending_writes))
        wire,record=self.latest_wire();self.assertEqual('pending-wire',record['role'])
        self.assertEqual(self.owner.pending.last_raw,body_original(wire,self.pending.pending_wire.last,
            record=record,scope_sha=self.bank.archive.scope_sha,run=self.owner.run))
        self.assertTrue(any('lifecyclePendingBodyVersion' in ref for ref in self.owner.disk['originalChunks']))
        with self.owner.lock.held():
            self.owner.close_return_pins();self.assertIsNone(self.bank.return_slot)
            encoded=unpack(self.owner.disk['payload']);self.assertEqual([self.owner.state],self.bank.decode(encoded,role='pending'))
            self.bank.seal()
        history=LifecycleSourceRawHistory4.open_profile(self.bank.path,self.owner.run,self.owner.binding,
            self.owner.disk['originalChunks'],role='pending')
        self.addCleanup(history.close)
        self.assertEqual([self.owner.state],history.decode(encoded));self.assertFalse(history.report()['ownerCASAcknowledgementKnown'])
        self.assertEqual(1,len(self.pending.pending_sdk.calls))

    def test_real_family_failure_after_actual_sdk_response_keeps_wire_refuses_current_body_and_every_next_sdk(self):
        self.fixture();self.owner.prepare();transport=self.pending.pending_wire;sdk=self.pending.pending_sdk
        gate=self.owner.storage_gate;confirmed=self.bank.view('pending').confirmed;seen=[]
        with self.owner.lock.held():self.owner.close_return_pins()
        def after():
            try:
                with patch.object(self.namespace,'begin_write',side_effect=OSError('Original declared family admission failure')):
                    gate.save(deepcopy(self.owner.state))
            except OSError as error:seen.append(str(error))
        sdk.after=after;before=len(sdk.calls)
        with self.owner.lock.held(),self.assertRaises(NativeUIError):self.owner.pending.read(self.owner.run)
        self.assertEqual(1,len(seen));self.assertEqual(before+1,len(sdk.calls));self.assertIsNone(transport.last)
        self.assertIs(confirmed,self.bank.view('pending').confirmed);self.assertIsNotNone(gate.held[0].value)
        wire,record=self.latest_wire();self.assertEqual('bytes',record['kind']);self.assertEqual('pending-wire',record['role'])
        self.assertIn(b'pendingCommitOwnerVersion',wire);self.assertEqual(record['bytes'],len(wire))
        with self.owner.lock.held():self.assertIsNotNone(self.namespace.family_root_spec())
        with self.owner.lock.held(),self.assertRaises(NativeUIError):self.owner.pending.read(self.owner.run)
        self.assertEqual(before+1,len(sdk.calls));self.assertIsNone(transport.last)

    def test_codec_failure_after_real_original_file_open_is_strongly_held_charged_and_never_reconstructed(self):
        self.fixture()
        from adapters.loaded_chunk_codec import OriginalChunkCodec
        from adapters.pico4.lifecycle_family_gate import CODEC_RESERVE
        original=OriginalChunkCodec._file;opened=[]
        def failed(codec,row):
            original(codec,row);opened.append((codec,row[1]));raise OSError('Original codec failed after real original OFD open')
        with patch.object(OriginalChunkCodec,'_file',failed),self.assertRaises(NativeUIError):
            self.owner.prepare()
        self.assertEqual(1,len(opened));gate=self.bank.family_attempt[0];codec,descriptor=opened[0]
        self.assertIs(gate.codec,codec);gc.collect();self.assertIs(self.bank.family_attempt[0].codec,codec)
        self.assertGreaterEqual(self.bank.family_attempt_bytes(),CODEC_RESERVE)
        self.assertIs(self.bank.family_value[0],self.owner);self.assertEqual('prepared',self.bank.family_value[1]['phase'])
        self.assertTrue(self.bank.failed);calls=len(self.pending.pending_sdk.calls)
        with patch.object(OriginalChunkCodec,'__init__',side_effect=AssertionError('No second codec constructor')):
            with self.assertRaises(NativeUIError):self.owner.prepare()
        self.assertEqual(calls,len(self.pending.pending_sdk.calls));self.assertFalse(self.bank.close_host())
        descriptor.require(descriptor.fd)

    def test_codec_admission_refuses_before_constructor_and_keeps_actual_acquired_prepared_state(self):
        self.fixture();save=self.bank.save_pending
        def exhausted(writer,value):
            with patch.object(self.bank,'other_bill',return_value=dict(parts=0,storedBytes=0,decodedBytes=16*1024*1024,files=0)):
                return save(writer,value)
        with patch.object(self.bank,'save_pending',side_effect=exhausted):
            with patch('adapters.loaded_chunk_codec.OriginalChunkCodec.__init__',side_effect=AssertionError('No codec/OFD before capacity')):
                with self.assertRaises(NativeUIError):self.owner.prepare()
        self.assertIsNone(self.bank.family_attempt);self.assertIsNotNone(self.bank.family_value)
        self.assertIs(self.bank.family_value[0],self.owner);self.assertEqual('prepared',self.bank.family_value[1]['phase'])
        self.assertEqual(1,len(self.pending.pending_sdk.calls));self.assertTrue(self.bank.failed)


class LifecyclePending3Background5Tests(LifecyclePending3FamilyTests):
    """Same actual born-host flow, explicit Background5 selected before I/O."""
    BACKGROUND_STATE_LAYOUT=5
