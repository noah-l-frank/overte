"""Actual cold Pico UI/factory/SDK hooks; Native/Qt/backend remain models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import shlex
import subprocess
import time
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4.assets_transport import HEADER,FOOTER
from adapters.pico4.assets_wire_owner import AssetsChildUiRaw,UNRESOLVED_UI
from adapters.pico4.navigation import NativeNavigationIO
from adapters.script_journey.history import canonical
import self_tests.test_pico_assets_prefix3_factory as fixtures
from self_tests.test_pico_assets_wire_owner import stamp


class AssetsChildUiRawTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.AssetsPrefix3FactoryTests(methodName='runTest');self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.model=self.fixture.fresh_model();self.parent=self.model.owner
        self.fault=None;self.injected=[];self.decoder_entries=[]
        self.actual_sdk=self.model.binary_sdk
        current=patch('adb_transport.subprocess.run',side_effect=self.sdk)
        current.start();self.addCleanup(current.stop)

    def sdk(self,args,**options):
        result=self.actual_sdk(args,**options);p=self.parent
        cold=(p.child_ui is not None and p.child is None) or (p.upload_ui is not None and p.upload_owner is None)
        parsed=shlex.split(args[4]);name=parsed[-1].rsplit('/',1)[-1]
        if not cold or name!='navigation-ui-observation.json' or self.injected:return result
        if self.fault not in ('malformed-json','invalid-utf8','partial-timeout','foreign-bridge','oversized-ui'):return result
        self.injected.append(True);nonce=parsed[10]
        if self.fault=='partial-timeout':
            raise subprocess.TimeoutExpired(args,1.5,output=b'actual partial cold UI wire\xff')
        if self.fault=='malformed-json':raw=b'{actual malformed UI original'
        elif self.fault=='invalid-utf8':raw=b'\xff actual UI bytes before UTF8'
        elif self.fault=='oversized-ui':raw=b' '*(65536+1)
        else:
            body=self.model.snapshot();body['bridgeId']='01234567-89ab-4cde-8f01-23456789abcd';raw=canonical(body)
        original=self.model.sdk_original;original.write_bytes(raw);description=stamp(original).encode()
        output=HEADER+nonce.encode()+b'\n'+description+b'\n'+raw+FOOTER+nonce.encode()+b'\n'+description+b'\n'
        return subprocess.CompletedProcess(result.args,result.returncode,stdout=output,stderr=result.stderr)

    def parent_open(self):
        m,p=self.model,self.parent;m.activate('baseline');self.assertFalse(p.observe()['open'])
        self.assertTrue(p.act(m.activate('open'))['openDelivered'])
        self.assertEqual(3,len(m.inputs))

    def picker(self):
        return self.parent.act(self.model.activate('upload-picker-open',{'resource':'gltf-bundle/main.gltf'}))

    def no_more_sdk(self):
        before=len(self.model.sdk_calls)
        with self.assertRaises(NativeUIError):self.parent.observe()
        self.assertEqual(before,len(self.model.sdk_calls))

    def test_default_runtime_passes_exact_original_args_without_hook_keyword(self):
        from adapters.pico4 import normal_scripts
        runtime=normal_scripts.runtime
        with patch.object(normal_scripts,'runtime',wraps=runtime) as called:
            ui,_observe,binding=self.model.adapter._script_runtime(self.model.native.target)
        self.assertEqual({},called.call_args.kwargs)
        self.assertEqual(self.parent.binding,binding);self.assertIsNotNone(ui)

    def test_before_native_callback_failure_performs_zero_actual_ui_reads(self):
        def unavailable(_native):raise NativeUIError('Declared missing cold UI prerequisite')
        with patch.object(NativeNavigationIO,'_read',side_effect=AssertionError('No getter after callback refusal')) as getter:
            with self.assertRaises(NativeUIError):
                self.model.adapter._script_runtime(self.model.native.target,before_native=unavailable)
        getter.assert_not_called();self.assertFalse(self.model.inputs)

    def originals(self):
        p=self.parent
        return [(index,row) for index,row in enumerate(p.disk['rawReads']) if row.get('childSource') in ('ui-observation','ui-status')]

    def test_actual_cold_factory_capture_controls_and_ack_use_same_raw_family(self):
        self.parent_open();self.assertTrue(self.picker()['pickerObserved'])
        p=self.parent;owner=p.child_ui;self.assertIs(type(owner),AssetsChildUiRaw)
        self.assertIs(owner.child,p.child);self.assertGreaterEqual(len(owner.slots),3)
        rows=self.originals();self.assertTrue(rows)
        roles={row['childSource'] for index,row in rows};self.assertEqual({'ui-observation','ui-status'},roles)
        with p.lock.held():
            receipts=p.raw_archive.audio.pages
            commands=[record['command'] for page in receipts.values() for record in page['receipts'] if record is not None
                and record['command'].get('assetsChildUiQueryVersion')==1]
            self.assertEqual(len(rows),len(commands))
            for command in commands:
                self.assertEqual(p.state['steps'][1]['ticket'],command['ownerOpenTicket'])
                self.assertEqual(p.state['steps'][1]['ticket'],command['ticket'])
                self.assertIs(type(command['startedHostMonotonic']),float)
                self.assertIs(type(command['startedEpochMs']),int)
            for index,row in rows:self.assertIs(type(json.loads(p.literal(index))),dict)
            self.assertIsNone(p.disk['pendingChildSource']);self.assertIsNone(owner.query)
            self.assertLessEqual(p.bill()['frames'],512);self.assertLessEqual(p.bill()['decodedBytes'],16*1024*1024)
        self.assertEqual(3+p.child.state()['inputCount'],len(self.model.inputs))

    def test_cold_malformed_ui_json_is_durable_before_original_decoder(self):
        self.parent_open();self.fault='malformed-json'
        with self.assertRaises(NativeUIError):self.picker()
        self.assertTrue(self.injected);rows=self.originals();self.assertEqual(1,len(rows))
        with self.parent.lock.held():self.assertEqual(b'{actual malformed UI original',self.parent.literal(rows[0][0]))
        self.assertIsNone(self.parent.child);self.assertTrue(self.parent.child_ui.failed)
        self.assertEqual(3,len(self.model.inputs));self.no_more_sdk()

    def test_cold_invalid_utf8_ui_is_durable_before_any_json_or_binding(self):
        self.parent_open();self.fault='invalid-utf8'
        with self.assertRaises(NativeUIError):self.picker()
        self.assertTrue(self.injected);rows=self.originals();self.assertEqual(1,len(rows))
        with self.parent.lock.held():self.assertEqual(b'\xff actual UI bytes before UTF8',self.parent.literal(rows[0][0]))
        self.assertIsNone(self.parent.child);self.assertEqual(3,len(self.model.inputs));self.no_more_sdk()

    def test_cold_oversized_ui_retains_bytes_before_unchanged_semantic_limit(self):
        self.parent_open();self.fault='oversized-ui'
        with self.assertRaises(NativeUIError):self.picker()
        self.assertTrue(self.injected);rows=self.originals();self.assertEqual(1,len(rows))
        with self.parent.lock.held():self.assertEqual(b' '*(65536+1),self.parent.literal(rows[0][0]))
        self.assertIsNone(self.parent.child);self.assertEqual(3,len(self.model.inputs));self.no_more_sdk()

    def test_cold_foreign_target_refuses_before_actual_native_ui_getter(self):
        self.parent_open();original=AssetsChildUiRaw.bind_native;seen=[]
        def foreign(owner,io):
            before=len(self.model.sdk_calls);io.target='foreign-declared-model-target'
            try:return original(owner,io)
            finally:seen.append((before,len(self.model.sdk_calls)))
        with patch.object(AssetsChildUiRaw,'bind_native',foreign),patch.object(NativeNavigationIO,'_read') as getter:
            with self.assertRaises(NativeUIError):self.picker()
        self.assertTrue(seen);self.assertTrue(all(a==b for a,b in seen));getter.assert_not_called()
        self.assertEqual(3,len(self.model.inputs));self.assertIsNone(self.parent.child);self.no_more_sdk()

    def test_cold_foreign_actual_runtime_binding_refuses_without_first_ui_read(self):
        self.parent_open();original=AssetsChildUiRaw.bind_native;seen=[]
        def foreign(owner,io):
            before=len(self.model.sdk_calls);io.identity='124:314159'
            try:return original(owner,io)
            finally:seen.append((before,len(self.model.sdk_calls)))
        with patch.object(AssetsChildUiRaw,'bind_native',foreign),patch.object(NativeNavigationIO,'_read') as getter:
            with self.assertRaises(NativeUIError):self.picker()
        self.assertTrue(seen);self.assertTrue(all(a==b for a,b in seen));getter.assert_not_called()
        self.assertEqual(3,len(self.model.inputs));self.assertIsNone(self.parent.child);self.no_more_sdk()

    def test_actual_partial_timeout_cold_ui_retains_every_acquired_byte(self):
        self.parent_open();self.fault='partial-timeout'
        with self.assertRaises(NativeUIError):self.picker()
        self.assertTrue(self.injected);rows=self.originals();self.assertEqual(1,len(rows))
        with self.parent.lock.held():self.assertEqual(b'actual partial cold UI wire\xff',self.parent.literal(rows[0][0]))
        self.assertTrue(self.parent.wire.transport.failed);self.no_more_sdk()

    def test_same_pid_foreign_bridge_refused_before_child_or_ordinary_input(self):
        self.parent_open();self.fault='foreign-bridge'
        with self.assertRaises(NativeUIError):self.picker()
        self.assertTrue(self.injected);rows=self.originals();self.assertEqual(1,len(rows))
        with self.parent.lock.held():
            self.assertEqual('01234567-89ab-4cde-8f01-23456789abcd',json.loads(self.parent.literal(rows[0][0]))['bridgeId'])
        self.assertEqual(3,len(self.model.inputs));self.assertIsNone(self.parent.child);self.no_more_sdk()

    def test_actual_cold_raw_receipt_cas_lost_keeps_query_and_original_bytes(self):
        self.parent_open();p=self.parent;write=p.store.write;lost=[]
        def failed(value,previous):
            new=value.get('rawReads',[])
            actual=write(value,previous)
            if not lost and new and new[-1].get('childSource')=='ui-observation':
                lost.append(True);raise OSError('Actual cold UI receipt CAS succeeded; response lost')
            return actual
        with patch.object(p.store,'write',side_effect=failed),self.assertRaises(NativeUIError):self.picker()
        self.assertTrue(lost);self.assertIsNotNone(p.child_ui.query)
        self.assertIsNotNone(p.raw_archive.unconfirmed);self.assertIs(type(p.raw_archive.unconfirmed),bytes)
        self.assertEqual('sealed',p.raw_archive.active['state'])
        self.assertIn(p.child_ui,UNRESOLVED_UI);self.no_more_sdk()

    def test_slow_cold_capacity_with_frozen_native_clock_refuses_before_ui_getter(self):
        self.parent_open();p=self.parent;m=self.model;reserve=p.raw_archive.reserve;delayed=[]
        frozen=m.epoch();m.epoch=lambda:frozen;before=len(m.sdk_calls)
        def slow(role,*args,**options):
            result=reserve(role,*args,**options)
            if role=='child-ui-observation' and not delayed:
                delayed.append(True);time.sleep(1.51)
            return result
        with patch.object(p.raw_archive,'reserve',side_effect=slow),self.assertRaises(NativeUIError):self.picker()
        self.assertTrue(delayed);self.assertEqual(before,len(m.sdk_calls))
        self.assertTrue(p.raw_archive.audio.state['pending']);self.assertIsNotNone(p.child_ui.query)
        self.assertIsNone(p.child);self.no_more_sdk()

    def test_clock_reentry_refuses_before_getter_and_does_not_clear_outer_owner(self):
        self.parent_open();p=self.parent;clock=p.clock_ms;observed=[]
        before=len(self.model.sdk_calls)
        def reenter():
            owner=p.child_ui
            if owner is not None and owner.slots and owner.read_active and not observed:
                observed.append(True);io=owner.slots[0][0]
                with self.assertRaises(NativeUIError):io.read()
                self.assertTrue(owner.read_active);self.assertIs(owner.read_io,io)
                self.assertEqual(before,len(self.model.sdk_calls))
            return clock()
        with patch.object(p,'clock_ms',side_effect=reenter),self.assertRaises(NativeUIError):self.picker()
        self.assertTrue(observed);self.assertEqual(before,len(self.model.sdk_calls))
        self.assertTrue(p.child_ui.failed);self.assertFalse(p.child_ui.read_active)
        self.no_more_sdk()


if __name__=='__main__':unittest.main()
