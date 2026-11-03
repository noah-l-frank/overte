"""Existing stage4 factory on an EXPLICIT modeled prior-prefix precondition.

The first three normal actions are NOT executed or qualified by these tests.
No upload success, file lease, request, backend blob or mapping is seeded.
Native/Qt/Android/server effects remain the existing declared fixture models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import shlex
import subprocess
import time
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4.assets_upload_owner import OwnedAssetsUpload
from adapters.pico4.assets_wire_owner import AssetsChildUiRaw,UNRESOLVED_UI
from adapters.pico4.navigation import NativeNavigationIO
from adapters.pico4.assets_transport import HEADER,FOOTER
from self_tests.test_pico_assets_wire_owner import stamp
import self_tests.test_pico_assets_child_ui_raw as fixtures


class DeclaredColdBoundary(Exception):pass


class AssetsUploadUiRawTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.AssetsChildUiRawTests(methodName='runTest');self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.model,self.parent=self.fixture.model,self.fixture.parent
        self.evidence=self.model.root/'stage4-declared-precondition.json'
        self.precondition()

    def precondition(self):
        """Test-only authored input scope, never production restore/adoption."""
        m,p=self.model,self.parent
        m.activate('baseline');self.assertFalse(p.observe()['open'])
        # Real fresh Parent/provider/file ownership is retained. Only the
        # preceding action results are declared model setup, visibly distinct
        # from requested/current product effects and normal input receipts.
        rows=[]
        for verb,inputs in (('open',{}),('upload-picker-open',{'resource':'gltf-bundle/main.gltf'}),('upload-picker-cancel',{})):
            fields=m.activate(verb,inputs)
            with p.lock.held():
                phase,before=p.phase(verb,next_step=True)
                self.assertEqual(fields['ticket'],phase['ticket'])
                result=p.archive(dict(declaredModeledPriorPrefix=True,normalActionActuallyExecuted=False))
                p.state['steps'].append(dict(ticket=fields['ticket'],before=before,status='returned',result=result));p.save()
            rows.append(dict(verb=verb,ticket=fields['ticket'],normalActionActuallyExecuted=False))
        m.page='assets';m.tab=3
        self.assertFalse(m.inputs);self.assertFalse(m.upload_calls);self.assertFalse(m.server_rows);self.assertFalse(m.server_blobs)
        self.assertIsNone(p.child);self.assertIsNone(p.upload_owner)
        self.evidence.write_text(json.dumps(dict(testPreconditionOnly=True,executedNormalPrefix=False,
            currentSourceOrCommonQualified=False,priorActions=rows,seededUploadSuccess=False,
            originalParentStartedMonotonic=p.scope['startedMonotonic'],originalParentStartedEpochMs=p.scope['startedEpochMs']),indent=2)+'\n')

    def upload_fields(self):return self.model.activate('upload',{'resource':'gltf-bundle/main.gltf'})

    def act_cold(self,*,construct_controls=False):
        seen=[]
        def stop(owner,fields):
            seen.append(owner)
            if construct_controls:owner.ui().capture()
            raise DeclaredColdBoundary('Intentional cold-UI component boundary, not an upload result')
        with patch.object(OwnedAssetsUpload,'run',stop),self.assertRaises(NativeUIError):
            self.parent.act(self.upload_fields())
        return seen

    def rows(self):return [(i,row) for i,row in enumerate(self.parent.disk['rawReads']) if 'childSource' in row]

    def no_more_source(self):self.fixture.no_more_sdk()

    def test_actual_stage2_constructor_and_later_controls_share_upload_query2(self):
        seen=self.act_cold(construct_controls=True);self.assertEqual(1,len(seen))
        owner=seen[0];p=self.parent;raw=p.upload_ui
        self.assertIs(type(raw),AssetsChildUiRaw);self.assertEqual('upload',raw.operation)
        self.assertIs(raw.child,owner);self.assertIs(owner.ui_raw,raw)
        self.assertGreaterEqual(len(raw.slots),2);self.assertIsNotNone(owner.active_ui)
        self.assertFalse(self.model.inputs);self.assertFalse(self.model.upload_calls)
        with p.lock.held():
            commands=[row['command'] for page in p.raw_archive.audio.pages.values() for row in page['receipts']
                if row is not None and row['command'].get('assetsChildUiQueryVersion')==2]
            self.assertTrue(commands);self.assertEqual(len(self.rows()),len(commands))
            for command in commands:
                self.assertEqual(p.state['steps'][3]['ticket'],command['ticket'])
                self.assertEqual(command['ticket'],command['ownerUploadTicket']);self.assertNotIn('ownerOpenTicket',command)
                self.assertIs(type(command['startedHostMonotonic']),float);self.assertIs(type(command['startedEpochMs']),int)
                reference=command['uploadActionOriginal'];self.assertEqual(1,reference['assetsUploadActionReferenceVersion'])
                action=p.original(reference['bundle'])
                self.assertEqual(owner.started,action['startedHostMonotonic']);self.assertEqual(owner.epoch,action['nativeEpochMs'])
                self.assertEqual(command['ticket'],action['ticket'])
            for i,row in self.rows():self.assertIs(type(json.loads(p.literal(i))),dict)
            self.assertLessEqual(p.bill()['frames'],512);self.assertLessEqual(p.bill()['decodedBytes'],16*1024*1024)
        self.assertEqual('issued',p.state['steps'][3]['status']);self.assertIsNone(p.state['upload'])
        self.no_more_source()

    def test_stage4_malformed_cold_bytes_are_durable_before_owner_exists(self):
        self.fixture.fault='malformed-json';seen=self.act_cold()
        self.assertFalse(seen);self.assertIsNone(self.parent.upload_owner)
        self.assertTrue(self.parent.upload_ui.failed);self.assertIn(self.parent.upload_ui,UNRESOLVED_UI)
        rows=self.rows();self.assertEqual(1,len(rows))
        with self.parent.lock.held():self.assertEqual(b'{actual malformed UI original',self.parent.literal(rows[0][0]))
        self.assertFalse(self.model.inputs);self.no_more_source()

    def test_stage4_partial_timeout_keeps_raw_before_utf8_and_any_upload_input(self):
        self.fixture.fault='partial-timeout';self.assertFalse(self.act_cold())
        rows=self.rows();self.assertEqual(1,len(rows))
        with self.parent.lock.held():self.assertEqual(b'actual partial cold UI wire\xff',self.parent.literal(rows[0][0]))
        self.assertIsNone(self.parent.upload_owner);self.assertFalse(self.model.inputs);self.no_more_source()

    def test_stage4_foreign_bridge_cannot_construct_an_upload_owner(self):
        self.fixture.fault='foreign-bridge';self.assertFalse(self.act_cold())
        rows=self.rows();self.assertEqual(1,len(rows))
        with self.parent.lock.held():
            self.assertEqual('01234567-89ab-4cde-8f01-23456789abcd',json.loads(self.parent.literal(rows[0][0]))['bridgeId'])
        self.assertIsNone(self.parent.upload_owner);self.assertFalse(self.model.inputs);self.no_more_source()

    def test_stage4_successful_raw_receipt_cas_lost_retains_actual_pending_owner(self):
        p=self.parent;write=p.store.write;lost=[]
        def unknown(value,previous):
            result=write(value,previous);rows=value.get('rawReads',[])
            if not lost and rows and rows[-1].get('childSource')=='ui-observation':
                lost.append(True);raise OSError('Actual stage4 raw receipt CAS committed; response lost')
            return result
        with patch.object(p.store,'write',side_effect=unknown):self.assertFalse(self.act_cold())
        self.assertTrue(lost);self.assertIsNotNone(p.upload_ui.query)
        self.assertIs(type(p.raw_archive.unconfirmed),bytes);self.assertEqual('sealed',p.raw_archive.active['state'])
        self.assertIn(p.upload_ui,UNRESOLVED_UI);self.assertIsNone(p.upload_owner)
        self.assertFalse(self.model.inputs);self.no_more_source()

    def test_upload_mode_substitution_refuses_before_later_control_runtime_io(self):
        observed=[]
        def changed(owner,fields):
            before=len(self.model.sdk_calls);owner.ui_raw.operation='picker-open'
            try:owner.ui()
            finally:observed.append((before,len(self.model.sdk_calls)))
        with patch.object(OwnedAssetsUpload,'run',changed),self.assertRaises(NativeUIError):self.parent.act(self.upload_fields())
        self.assertTrue(observed);self.assertTrue(all(a==b for a,b in observed))
        self.assertFalse(self.model.inputs);self.no_more_source()

    def test_changed_original_upload_clock_refuses_before_native_clock_or_input(self):
        observed=[];p=self.parent;clock=p.clock_ms
        def changed(owner,fields):
            owner.started+=1
            before=(len(self.model.sdk_calls),native_clock.call_count)
            try:owner.age()
            finally:observed.append((before,(len(self.model.sdk_calls),native_clock.call_count)))
        with patch.object(p,'clock_ms',wraps=clock) as native_clock,patch.object(OwnedAssetsUpload,'run',changed),self.assertRaises(NativeUIError):p.act(self.upload_fields())
        self.assertTrue(observed);self.assertTrue(all(a==b for a,b in observed))
        self.assertIsNone(p.state['upload']);self.assertFalse(self.model.inputs);self.no_more_source()

    def test_real_delayed_factory_is_charged_before_runtime_sdk_or_input(self):
        p=self.parent;factory=p.upload_factory;seen=[];clock=p.clock_ms
        with patch.object(p,'clock_ms',wraps=clock) as native_clock,patch.object(self.model.adapter,'_script_runtime',wraps=self.model.adapter._script_runtime) as runtime:
            def delayed(parent,**options):
                before=(len(self.model.sdk_calls),len(self.model.calls),native_clock.call_count)
                time.sleep(20.01)
                try:return factory(parent,**options)
                finally:seen.append((before,(len(self.model.sdk_calls),len(self.model.calls),native_clock.call_count)))
            p.upload_factory=delayed
            with self.assertRaises(NativeUIError):p.act(self.upload_fields())
        self.assertTrue(seen);self.assertTrue(all(a==b for a,b in seen));runtime.assert_not_called()
        self.assertFalse(self.model.inputs);self.assertIsNone(p.upload_owner);self.assertTrue(p.upload_ui.failed)
        with p.lock.held():
            action=p.original(p.upload_ui.action_original)
            self.assertEqual(p.upload_ui.action_anchor,(action['startedHostMonotonic'],action['nativeEpochMs']))
        self.no_more_source()

    def test_real_action_anchor_cas_delay_cannot_start_a_fresh_factory_budget(self):
        p=self.parent;archive=p.archive;delayed=[]
        def slow(value,**options):
            result=archive(value,**options)
            if type(value) is dict and value.get('assetsUploadActionAnchorVersion')==1:
                before=(len(self.model.sdk_calls),len(self.model.calls));time.sleep(20.01)
                delayed.append((result,before,(len(self.model.sdk_calls),len(self.model.calls))))
            return result
        with patch.object(p,'archive',side_effect=slow),patch.object(self.model.adapter,'_script_runtime',wraps=self.model.adapter._script_runtime) as runtime:
            with self.assertRaises(NativeUIError):p.act(self.upload_fields())
        self.assertTrue(delayed);self.assertTrue(all(a==b for i,a,b in delayed));runtime.assert_not_called()
        self.assertIsNone(p.upload_ui);self.assertIsNone(p.upload_owner);self.assertFalse(self.model.inputs)
        with p.lock.held():self.assertEqual(1,p.original(delayed[0][0])['assetsUploadActionAnchorVersion'])
        self.no_more_source()

    def test_acquired_cold_ui_after_original_twenty_seconds_stays_durable(self):
        p=self.parent;original=self.fixture.actual_sdk;late=[]
        def slow(args,**options):
            result=original(args,**options)
            if p.upload_ui is not None and p.upload_owner is None and not late:
                late.append(result.stdout);time.sleep(20.01)
            return result
        self.fixture.actual_sdk=slow
        self.assertFalse(self.act_cold());self.assertTrue(late)
        rows=self.rows();self.assertEqual(1,len(rows))
        # Source1.5/action20 refuse AFTER the original opaque return is durable;
        # this is not a confirmed view, decoder result or upload success.
        self.assertNotIn('wireView',rows[0][1])
        with p.lock.held():self.assertEqual(late[0],p.literal(rows[0][0]))
        self.assertIsNone(p.upload_owner);self.assertFalse(self.model.inputs);self.no_more_source()

    def test_status_capacity_is_reserved_before_the_single_actual_input_writer(self):
        p=self.parent;reserve=p.raw_archive.reserve;seen=[]
        def unavailable(role,*args,**options):
            if role=='child-ui-status':
                seen.append((len(self.model.inputs),deepcopy(p.state['pendingInput'])))
                raise NativeUIError('Declared exact ACK reservation capacity refusal')
            return reserve(role,*args,**options)
        with patch.object(p.raw_archive,'reserve',side_effect=unavailable),self.assertRaises(NativeUIError):p.act(self.upload_fields())
        self.assertTrue(seen);self.assertTrue(all(count==0 and pending['native'] is not None for count,pending in seen))
        self.assertFalse(self.model.inputs);self.assertIsNotNone(p.upload_ui.status_prepared)
        self.assertIsNone(p.disk['pendingSource']);self.no_more_source()

    def test_foreign_status_command_refuses_before_any_actual_input_or_getter(self):
        p=self.parent;original=AssetsChildUiRaw.prepare_status;seen=[]
        def foreign(owner,command,io):
            command=deepcopy(command);command['bridgeId']='01234567-89ab-4cde-8f01-23456789abcd'
            before=len(self.model.sdk_calls)
            try:return original(owner,command,io)
            finally:seen.append((before,len(self.model.sdk_calls)))
        with patch.object(AssetsChildUiRaw,'prepare_status',foreign),self.assertRaises(NativeUIError):p.act(self.upload_fields())
        self.assertTrue(seen);self.assertTrue(all(a==b for a,b in seen));self.assertFalse(self.model.inputs);self.no_more_source()

    def status_fault(self,kind):
        original=self.fixture.actual_sdk;seen=[]
        def changed(args,**options):
            result=original(args,**options);parts=shlex.split(args[4])
            if parts[-1].rsplit('/',1)[-1]!='navigation-ui-status.json' or not self.model.inputs:return result
            seen.append(True)
            if kind=='partial':raise subprocess.TimeoutExpired(args,1.5,output=b'actual partial stage4 ACK\xff')
            packet=deepcopy(self.model.native.status);packet['commandId']='01234567-89ab-4cde-8f01-23456789abcd'
            raw=json.dumps(packet,sort_keys=True,separators=(',',':')).encode();nonce=parts[10]
            self.model.sdk_original.write_bytes(raw);description=stamp(self.model.sdk_original).encode()
            return subprocess.CompletedProcess(args,0,stdout=HEADER+nonce.encode()+b'\n'+description+b'\n'+raw+FOOTER+nonce.encode()+b'\n'+description+b'\n',stderr=b'')
        self.fixture.actual_sdk=changed
        return seen

    def test_wrong_ack_keeps_one_input_and_original_one_point_five_second_anchor(self):
        p=self.parent;seen=self.status_fault('wrong')
        # The ordinary retry policy is a declared model boundary. A real
        # pause after its first wrong ACK must not renew the input deadline.
        with patch.object(self.model.adapter,'probe_retry_policy',return_value=(3,1.51)),self.assertRaises(NativeUIError):p.act(self.upload_fields())
        self.assertEqual(1,len(seen));self.assertEqual(1,len(self.model.inputs));self.assertIsNotNone(p.upload_ui.status_prepared)
        self.assertIsNotNone(p.disk['pendingInput']);self.assertIsNone(p.disk['pendingSource'])
        with p.lock.held():
            commands=[row['command'] for page in p.raw_archive.audio.pages.values() for row in page['receipts']
                if row is not None and row['command'].get('assetsChildUiQueryVersion')==2 and row['command']['kind']=='status']
            self.assertTrue(commands);self.assertEqual(1,len({(row['startedHostMonotonic'],row['startedEpochMs']) for row in commands}))
            self.assertEqual(1,len({row['inputOriginal']['bundle'] for row in commands}))
        self.no_more_source();before=len(self.model.inputs)
        with self.assertRaises(NativeUIError):p.upload_owner.run(self.upload_fields())
        self.assertEqual(before,len(self.model.inputs))

    def test_partial_ack_after_actual_input_is_opaque_and_never_replayed(self):
        p=self.parent;seen=self.status_fault('partial')
        with self.assertRaises(NativeUIError):p.act(self.upload_fields())
        self.assertTrue(seen);self.assertEqual(1,len(self.model.inputs));self.assertIsNotNone(p.upload_ui.status_prepared)
        rows=[(i,row) for i,row in self.rows() if row['childSource']=='ui-status'];self.assertEqual(1,len(rows))
        self.assertNotIn('wireView',rows[0][1])
        with p.lock.held():self.assertEqual(b'actual partial stage4 ACK\xff',p.literal(rows[0][0]))
        self.assertIsNotNone(p.disk['pendingInput']);self.assertIsNone(p.disk['pendingSource']);self.no_more_source()

    def test_actual_ack_cas_lost_after_one_input_retains_same_command_and_bytes(self):
        p=self.parent;write=p.store.write;lost=[]
        def unknown(value,previous):
            result=write(value,previous);rows=value.get('rawReads',[])
            if not lost and self.model.inputs and rows and rows[-1].get('childSource')=='ui-status':
                lost.append(True);raise OSError('Actual stage4 ACK raw CAS committed; reply lost')
            return result
        with patch.object(p.store,'write',side_effect=unknown),self.assertRaises(NativeUIError):p.act(self.upload_fields())
        self.assertTrue(lost);self.assertEqual(1,len(self.model.inputs));self.assertIsNotNone(p.upload_ui.status_prepared)
        self.assertIs(type(p.raw_archive.unconfirmed),bytes);self.assertEqual('sealed',p.raw_archive.active['state'])
        self.assertIn(p.upload_ui,UNRESOLVED_UI);self.assertIsNotNone(p.disk['pendingInput']);self.no_more_source()

    def test_acquired_ui_survives_actual_business_failure_before_raw_retention(self):
        p=self.parent;original=self.fixture.actual_sdk;received=[]
        def failed(args,**options):
            result=original(args,**options)
            if p.upload_ui is not None and p.upload_owner is None and not received:
                received.append(result.stdout);p.upload_ui.fail()
            return result
        self.fixture.actual_sdk=failed
        self.assertFalse(self.act_cold());self.assertTrue(received)
        rows=self.rows();self.assertEqual(1,len(rows));self.assertNotIn('wireView',rows[0][1])
        with p.lock.held():self.assertEqual(received[0],p.literal(rows[0][0]))
        self.assertTrue(p.upload_ui.failed);self.assertFalse(self.model.inputs);self.no_more_source()

    def test_completed_receipt_cas_delay_keeps_original_status_until_final_freshness(self):
        p=self.parent;archive=p.archive;complete=AssetsChildUiRaw.complete_status;delayed=[];completed=[]
        def slow(value,**options):
            result=archive(value,**options)
            if type(value) is dict and 'uploadReceipt' in value and not delayed:
                time.sleep(1.51);delayed.append(p.upload_ui.status_prepared)
                if p.upload_ui.status_prepared is None:
                    # Stop this genuine old-order defect before another input;
                    # its red proof must not run an unchanged whole recipe.
                    raise DeclaredColdBoundary('Original status was released before completed receipt CAS')
            return result
        def after(owner,*args):
            completed.append(dict(afterReceiptDelay=bool(delayed),pendingCleared=p.disk['pendingInput'] is None))
            return complete(owner,*args)
        with patch.object(p,'archive',side_effect=slow),patch.object(AssetsChildUiRaw,'complete_status',after),self.assertRaises(NativeUIError):
            p.act(self.upload_fields())
        self.assertTrue(delayed);self.assertIsNotNone(delayed[0]);self.assertIsNotNone(p.upload_ui.status_prepared)
        self.assertEqual([dict(afterReceiptDelay=True,pendingCleared=True)],completed)
        self.assertIn(p.upload_ui,UNRESOLVED_UI)
        self.assertEqual(1,len(self.model.inputs));self.no_more_source()

    def test_first_ack_releases_only_after_receipt_and_pending_cas(self):
        p=self.parent;complete=AssetsChildUiRaw.complete_status;completed=[]
        def stop_after_actual_completion(owner,*args):
            self.assertIsNotNone(owner.status_prepared)
            self.assertIsNone(p.disk['pendingInput'])
            result=complete(owner,*args)
            self.assertIsNone(owner.status_prepared)
            self.assertEqual(1,len(self.model.inputs))
            completed.append(result)
            raise DeclaredColdBoundary('Intentional boundary after actual first ACK finalization; no upload result')
        with patch.object(AssetsChildUiRaw,'complete_status',stop_after_actual_completion),self.assertRaises(NativeUIError):
            p.act(self.upload_fields())
        self.assertEqual(1,len(completed));self.assertEqual(1,len(self.model.inputs))
        self.assertIsNone(p.disk['pendingInput']);self.assertIsNone(p.upload_ui.status_prepared)
        self.assertIn(p.upload_ui,UNRESOLVED_UI);self.assertFalse(self.model.upload_calls)
        self.no_more_source()

    def test_next_status_index_growth_is_reserved_under_actual_parent_byte_bound(self):
        p=self.parent;prepare=AssetsChildUiRaw.prepare_status;seen=[]
        def pressure(owner,*args):
            prepare(owner,*args)
            before=len(self.model.sdk_calls);original=owner.bill(p)
            # Exact JSON memory-pressure graph only, never a backend result.
            # All real original files/OFDs and Parent billing remain active.
            row=dict(declaredCapacityStressOnly='');p.upload_owner.backend.history.append(row)
            actual=p.bill()['decodedBytes'];row['declaredCapacityStressOnly']='x'*(16*1024*1024+1-actual)
            self.assertEqual(original,owner.bill(p))
            self.assertGreaterEqual(original,4)
            with self.assertRaises(NativeUIError):p.bill()
            # Without the reserved4, this exact graph is MAX_RAW-3.
            self.assertEqual(16*1024*1024-3,actual+len(row['declaredCapacityStressOnly'])-4)
            self.assertEqual(before,len(self.model.sdk_calls));seen.append(True)
            raise DeclaredColdBoundary('Capacity-only pre-writer boundary')
        with patch.object(AssetsChildUiRaw,'prepare_status',pressure),self.assertRaises(NativeUIError):p.act(self.upload_fields())
        self.assertTrue(seen);self.assertFalse(self.model.inputs);self.assertIn(p.upload_ui,UNRESOLVED_UI)
        self.no_more_source()

    def test_128_status_indices_refuse_before_the_next_actual_getter(self):
        p=self.parent;prepare=AssetsChildUiRaw.prepare_status;seen=[]
        def exhausted(owner,*args):
            prepare(owner,*args)
            # Declared bounded-history stress graph, not128 source reads.
            owner.status_records=owner.original_status_records=(owner.last_ui_record[1],)*128
            before=len(self.model.sdk_calls)
            with self.assertRaises(NativeUIError):owner.status_prepared[0]._read('status')
            self.assertEqual(before,len(self.model.sdk_calls));seen.append(True)
            raise DeclaredColdBoundary('No129th status getter')
        with patch.object(AssetsChildUiRaw,'prepare_status',exhausted),self.assertRaises(NativeUIError):p.act(self.upload_fields())
        self.assertTrue(seen);self.assertFalse(self.model.inputs);self.assertIn(p.upload_ui,UNRESOLVED_UI)
        self.no_more_source()

    def test_postappend_actual_byte_bound_retains_raw_before_status_decoder(self):
        p=self.parent;bill=p.bill;seen=[];decoded=[]
        from adapters.pico4 import navigation
        decoder=navigation.decode
        def decode(raw,*args,**options):
            if type(raw) is str and '"commandId"' in raw and '"performed"' in raw:decoded.append(raw)
            return decoder(raw,*args,**options)
        def pressure():
            owner=p.upload_ui
            if owner is not None and len(owner.status_records)==1 and not seen:
                before=len(self.model.sdk_calls)
                row=dict(declaredCapacityStressOnly='');p.upload_owner.backend.history.append(row)
                actual=bill()['decodedBytes'];row['declaredCapacityStressOnly']='x'*(16*1024*1024+1-actual)
                seen.append((before,owner.status_records[0]))
            return bill()
        with patch.object(p,'bill',side_effect=pressure),patch.object(navigation,'decode',side_effect=decode),self.assertRaises(NativeUIError):
            p.act(self.upload_fields())
        self.assertEqual(1,len(seen));self.assertEqual(1,len(self.model.inputs));self.assertFalse(decoded)
        self.assertEqual(seen[0][0],len(self.model.sdk_calls));self.assertIn(p.upload_ui,UNRESOLVED_UI)
        self.assertIsNotNone(p.upload_ui.status_prepared)
        with p.lock.held():
            raw=p.literal(seen[0][1]);self.assertEqual(self.model.native.status['commandId'],json.loads(raw)['commandId'])
        self.no_more_source()


if __name__=='__main__':unittest.main()
