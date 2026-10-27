"""Actual Script invocation and strict factual causal source boundaries.

Native/V8/Qt queues remain explicitly modeled. This does not compile the new
native source or bind the causal source into the live parent Upload owner.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import snapshot_causal_dispatch as source
from ios.self_tests.snapshot_causal_dispatch_domain import CausalDispatchDomain


class SnapshotCausalDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # One complete independent fresh normal flow creates all facts. Each
        # decoder case below receives a copy; no original file/clock is changed.
        cls.fixture=unittest.TestCase();cls.addClassCleanup(cls.fixture.doCleanups)
        cls.domain=CausalDispatchDomain(cls.fixture);cls.domain.prepare_native()
        cls.query=dict(schemaVersion=1,action=source.ACTION,commandId='ios-'+'c'*32,runId='a'*32)
        cls.packet=cls.domain.causal_packet(cls.query)
        query=dict(cls.query,action='feature-ios-snapshot-combined-preflight-http',commandId='ios-'+'d'*32)
        cls.http=cls.domain.http.produce(query)
    def packet_copy(self):return deepcopy(self.packet)
    def later(self,value=None):
        packet=self.packet_copy() if value is None else deepcopy(value)
        packet['sequence']+=1;packet['requestId']='ios-'+'e'*32
        for key in ('clockBefore','clockAfter'):
            packet[key]['epochMs']+=10;packet[key]['monotonicMs']+=10
        return packet

    def test_actual_script_window_invocation_drives_original_callback_and_native_job_identity(self):
        d=self.domain;packet=self.packet_copy();self.assertIs(packet,source.original(packet))
        calls=source.admitted(packet,'qrc:/scripts/');self.assertEqual(1,len(calls));observed=calls[0]
        self.assertEqual(['created','sent','callback-enter','text-read','window-share','window-return','callback-leave'],[row['kind'] for row in d.http.trace_events])
        self.assertEqual(d.upload.upload['instance'],observed['upload']);self.assertFalse(observed['leaseAlive'])
        self.assertTrue(all(row['leftEpochMs'] is not None for row in observed['hops']))
        link=source.http_join(observed,self.http,'qrc:/scripts/')
        self.assertEqual(d.native_birth_preflight,[link['finished']['details']['responseId']])
        self.assertLessEqual(link['read']['clock']['epochMs'],observed['bornEpochMs'])
        self.assertEqual(1,d.upload_count)

    def test_readable_unknown_caller_facts_cannot_be_promoted_to_snapshot_admission(self):
        for field,value in (('caller',{}),):
            packet=self.packet_copy();packet['source']['calls'][0][field]=value
            source.original(packet)
            with self.assertRaises(NativeUIError):source.admitted(packet,'qrc:/scripts/')
        packet=self.packet_copy();frame=packet['source']['calls'][0]['caller']['snapshotCombinedStack']
        frame['complete']=False;frame['frames'][0]['compiled']=None;source.original(packet)
        with self.assertRaises(NativeUIError):source.admitted(packet,'qrc:/scripts/')

    def test_foreign_actual_compiled_bytes_and_wrong_independent_root_refuse_admission(self):
        packet=self.packet_copy();call=packet['source']['calls'][0];caller=call['caller']
        target=next(row for row in caller['snapshotCombinedSources']['evaluations'] if row['url'].endswith('/system/snapshot.js'))
        target['sha256']='0'*64;caller['snapshotCombinedStack']['frames'][0]['compiled']['sha256']='0'*64
        source.original(packet)
        with self.assertRaises(NativeUIError):source.admitted(packet,'qrc:/scripts/')
        with self.assertRaises(NativeUIError):source.admitted(self.packet,'qrc:/foreign/')

    def test_http_original_identity_and_actual_event_bytes_are_required(self):
        observed=deepcopy(self.packet['source']['calls'][0])
        for field in ('httpInstance','event'):
            changed=deepcopy(observed)
            if field=='httpInstance':changed['http']['httpInstance']='0'*32
            else:changed['http']['read']['clock']['epochMs']+=1
            with self.subTest(field=field),self.assertRaises(NativeUIError):source.http_join(changed,self.http,'qrc:/scripts/')

    def test_original_getter_clocks_run_process_and_strict_query_remain_bound(self):
        for mutation in (lambda value:value.update(processId=99),lambda value:value.update(runId='0'*32),
                lambda value:value['clockAfter'].update(epochMs=value['clockBefore']['epochMs']+1500),
                lambda value:value['source']['calls'][0].update(bornEpochMs=value['clockAfter']['epochMs']+1)):
            packet=self.packet_copy();mutation(packet)
            with self.subTest(mutation=mutation),self.assertRaises(NativeUIError):source.validate(packet,self.query,42)
        for field in ('caller','upload','url','manager','pid'):
            with self.subTest(field=field),self.assertRaises(NativeUIError):source.command(dict(self.query,**{field:'requested'}))

    def test_immutable_call_hop_compilation_and_job_prefix_cannot_be_rewritten(self):
        for mutation in (lambda row:row['hops'][0].update(stage='snapshot'),
                lambda row:row['file'].update(nameSha256='0'*64),lambda row:row.update(upload='0'*32),
                lambda row:row['caller'].update(sequence=row['caller']['sequence']+1)):
            packet=self.later();mutation(packet['source']['calls'][0])
            with self.subTest(mutation=mutation),self.assertRaises(NativeUIError):source.validate(packet,dict(self.query,commandId=packet['requestId']),42,previous=self.packet)

    def test_complete_false_cannot_heal_and_released_dispatch_cannot_resurrect(self):
        previous=self.packet_copy();previous['source']['complete']=False
        packet=self.later();source.original(previous)
        with self.assertRaises(NativeUIError):source.validate(packet,dict(self.query,commandId=packet['requestId']),42,previous=previous)
        packet=self.later();row=packet['source']['calls'][0];row['leaseAlive']=True;row['releasedEpochMs']=None
        with self.assertRaises(NativeUIError):source.validate(packet,dict(self.query,commandId=packet['requestId']),42,previous=self.packet)

    def test_weak_expiry_without_destructor_departure_is_only_an_original_fact(self):
        packet=self.packet_copy();packet['source']['calls'][0]['releasedEpochMs']=None
        source.original(packet)
        later=self.later(packet);later['source']['calls'][0]['releasedEpochMs']=self.packet['source']['calls'][0]['releasedEpochMs']
        source.validate(later,dict(self.query,commandId=later['requestId']),42,previous=packet)
        changed=self.later(packet);changed['source']['calls'][0]['hops'].append(dict(instance='1'*32,stage='snapshot',
            enteredEpochMs=self.packet['clockBefore']['epochMs'],leftEpochMs=self.packet['clockBefore']['epochMs']))
        with self.assertRaises(NativeUIError):source.validate(changed,dict(self.query,commandId=changed['requestId']),42,previous=packet)


class SnapshotCausalLeaseTests(unittest.TestCase):
    def test_actual_held_diagnostic_queue_lease_blocks_drain_until_original_weak_expiry(self):
        d=CausalDispatchDomain(self);d.hold_dispatch=True;d.prepare_native()
        query=dict(schemaVersion=1,action=source.ACTION,commandId='ios-'+'7'*32,runId='a'*32)
        before=d.causal_packet(query);source.admitted(before,'qrc:/scripts/');key=before['source']['calls'][0]['instance']
        self.assertTrue(d.held);self.assertFalse(source.drained(before,[key]));old=deepcopy(before)
        d.held.clear();after=d.causal_packet(dict(query,commandId='ios-'+'8'*32))
        source.validate(after,dict(query,commandId=after['requestId']),42,previous=before)
        self.assertTrue(source.drained(after,[key]));self.assertEqual(old,before)
        self.assertEqual(1,d.upload_count)


if __name__=='__main__':unittest.main()
