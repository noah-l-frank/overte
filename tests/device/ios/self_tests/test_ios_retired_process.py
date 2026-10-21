"""Separate controller/Node-host clocks and canonical stopped-process scope."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from ios.adapters.installed_code import SDK
from ios.adapters.retired_process import IOSRetiredProcess,absent,validate
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.self_tests import test_ios_script_runtime as runtime_fixture

BUNDLE='org.example.overte'
SOURCE=dict(processSourceVersion=1,source='dvt-bundle-pid-xcuitest-state',instance='d'*32,
            available=True,cleanupPending=False,sdk=dict(SDK))


class Boundary:
    def __init__(self):
        self.clock=10.;self.sequence=100;self.pid=42;self.queries=[];self.mutate=None;self.delay=0;self.good=True
        self.states=[1,1];self.pids=[0,0];self.running=[False,False]
        self.anchor=dict(sequence=1,pid=42,appStates=[4,4],bundlePids=[42,42],
            clockBefore=dict(epochMs=self.node_epoch()-5000,monotonicMs=1000),
            clockAfter=dict(epochMs=self.node_epoch()-4990,monotonicMs=1010))
    def epoch(self):return 1700000000000+round(self.clock*1000)
    def node_epoch(self):return self.epoch()+86400000
    def send(self,query):
        self.queries.append(deepcopy(query));self.sequence+=1;before=dict(epochMs=self.node_epoch(),monotonicMs=5000+self.clock*1000)
        self.clock+=.01
        value=dict(iosRetiredProcessVersion=1,commandId=query['commandId'],instance=SOURCE['instance'],sequence=self.sequence,
            source='dvt-owned-pid-and-bundle-state',clockDomain='appium-node-host',clockBefore=before,
            clockAfter=dict(epochMs=self.node_epoch(),monotonicMs=5000+self.clock*1000),anchor=deepcopy(self.anchor),
            appStates=deepcopy(self.states),bundlePids=deepcopy(self.pids),pidChecks=[dict(pid=self.pid,running=v) for v in self.running])
        if self.mutate:self.mutate(value)
        self.clock+=self.delay;self.original=deepcopy(value);return value
    def reader(self):
        return IOSRetiredProcess(self.send,lambda:self.good,BUNDLE,self.pid,SOURCE,
                                 epoch_ms=self.epoch,monotonic=lambda:self.clock)


class RetiredProcessTests(unittest.TestCase):
    def test_original_node_clocks_remain_a_day_apart_from_controller_acquisition(self):
        boundary=Boundary();reader=boundary.reader();first=reader.read();acquisition=deepcopy(reader.acquisition)
        self.assertTrue(absent(first));self.assertEqual(boundary.original,first)
        self.assertGreater(first['clockBefore']['epochMs']-acquisition['hostAfterEpochMs'],86399000)
        self.assertEqual(digest(first),acquisition['originalSha256'])
        boundary.clock+=3.1;second=reader.read();self.assertGreater(second['sequence'],first['sequence'])
        self.assertEqual(first['anchor'],second['anchor']);self.assertEqual(acquisition['originalSha256'],digest(first))
        self.assertTrue(all(set(q)=={'bundleId','commandId'} for q in boundary.queries))

    def test_actual_numeric_presence_and_os_foreground_each_prevent_absence(self):
        for states,pids,running in (([0,0],[0,0],[True,True]),([4,4],[42,42],[True,True]),
                                    ([1,1],[0,0],[True,False]),([3,1],[42,0],[True,False])):
            with self.subTest(states=states,running=running):
                b=Boundary();b.states,b.pids,b.running=states,pids,running
                self.assertFalse(absent(b.reader().read()))

    def test_foreign_source_pid_missing_api_fields_boolean_versions_and_pid_echoes_fail(self):
        faults=[lambda v:v.update(instance='e'*32),lambda v:v['pidChecks'][0].update(pid=43),
                lambda v:v['anchor'].update(pid=43),lambda v:v.pop('pidChecks'),
                lambda v:v.update(iosRetiredProcessVersion=True),lambda v:v.update(bundlePids=[False,False]),
                lambda v:v['pidChecks'][0].update(running=0),lambda v:v.update(expectedAbsent=True)]
        for fault in faults:
            with self.subTest(fault=fault):
                b=Boundary();b.mutate=fault;reader=b.reader()
                with self.assertRaises(NativeUIError):reader.read()
                self.assertIsNone(reader.last);self.assertIsNone(reader.acquisition)

    def test_replayed_nonce_sequence_and_changed_anchor_cannot_advance_the_source_floor(self):
        for field in ('commandId','sequence','anchor'):
            with self.subTest(field=field):
                b=Boundary();reader=b.reader();first=reader.read();saved=deepcopy(reader.acquisition)
                if field=='anchor':b.mutate=lambda v:v['anchor']['clockBefore'].update(epochMs=v['anchor']['clockBefore']['epochMs']-1)
                else:b.mutate=lambda v:v.update({field:first[field]})
                with self.assertRaises(NativeUIError):reader.read()
                self.assertEqual(first,reader.last);self.assertEqual(saved,reader.acquisition)

    def test_late_controller_transfer_does_not_retime_original_node_capture_or_advance_cursor(self):
        b=Boundary();reader=b.reader();first=reader.read();b.delay=1.6
        with self.assertRaises(NativeUIError):reader.read()
        self.assertEqual(first,reader.last);self.assertLess(b.original['clockAfter']['epochMs'],b.node_epoch())

    def test_regressing_and_slow_original_node_clocks_are_rejected_independently(self):
        faults=[lambda v:v['clockAfter'].update(monotonicMs=v['clockBefore']['monotonicMs']-1),
                lambda v:v['clockAfter'].update(epochMs=v['clockBefore']['epochMs']+1600),
                lambda v:v['clockAfter'].update(monotonicMs=v['clockBefore']['monotonicMs']+500)]
        for fault in faults:
            b=Boundary();b.mutate=fault
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.reader().read()

    def test_lost_scope_and_malformed_dispatch_ack_cannot_produce_empty_absence(self):
        b=Boundary();b.good=False
        with self.assertRaises(NativeUIError):b.reader().read()
        self.assertEqual([],b.queries)
        reader=IOSRetiredProcess(lambda query:dict(query),lambda:True,BUNDLE,42,SOURCE,epoch_ms=b.epoch,monotonic=lambda:b.clock)
        with self.assertRaises(NativeUIError):reader.read()
        self.assertIsNone(reader.last)

    def test_pure_original_validation_does_not_create_a_new_host_acquisition(self):
        b=Boundary();reader=b.reader();packet=reader.read();original=deepcopy(packet);b.clock+=100
        validate(packet,b.queries[-1],42,SOURCE)
        self.assertEqual(original,packet);self.assertEqual(1,len(b.queries))
        self.assertLess(reader.acquisition['hostAfterEpochMs'],b.epoch())


class RetiredRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=runtime_fixture.IOSScriptRuntimeTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.f=self.fixture.f;self.runtime=IOSGraphicsRuntime(self.f.adapter)
        self.binding=dict(self.f.adapter._binding_store('test-only').read()['scope'],processIdentity='42')
        self.source=deepcopy(self.f.source);self.boundary=Boundary();self.calls=[]
        original=self.fixture.client.execute
        def execute(session,operation,values):
            self.calls.append(operation)
            if operation=='mobile: overteRetiredProcessInfo':return self.boundary.send(values)
            return original(session,operation,values)
        self.fixture.client.execute=execute

    def test_stopped_scope_uses_original_existing_sdk_without_foreground_native_or_bundle_reads(self):
        self.f.adapter.invoke('test-only','app.stop',{});before=len(self.f.native.commands);sessions=self.f.sessions
        reader=self.runtime._retired_process_observer('test-only',self.binding,self.source)
        # The real runtime defaults to real controller time; use the synthetic
        # boundary clock without changing the original Node-host packet.
        reader.epoch_ms=self.boundary.epoch;reader.monotonic=lambda:self.boundary.clock
        self.assertTrue(absent(reader.read()));self.assertEqual(before,len(self.f.native.commands))
        self.assertEqual(sessions,self.f.sessions);self.assertEqual(1,self.f.launches)
        self.assertIn('mobile: overteRetiredProcessInfo',self.calls)

    def test_final_window_factory_keeps_explicit_run_role_stage_and_existing_stopped_session(self):
        from adapters.script_feature.lock import ScriptSourceLock
        self.f.adapter.invoke('test-only','app.stop',{})
        lock=ScriptSourceLock(self.runtime.state_path('test-only').with_name('script-feature-sources.lock'))
        with lock.held():
            owner=self.runtime._graphics_process_retirement('test-only',self.binding,self.source,'a'*32,'actor',0,lock)
            owner.reader.epoch_ms=self.boundary.epoch;owner.reader.monotonic=lambda:self.boundary.clock
            before=len(self.f.native.commands);self.assertFalse(owner.advance())
            self.assertEqual(before,len(self.f.native.commands));self.assertEqual('actor',owner.previous['role'])
            self.assertEqual('a'*32,owner.previous['runId']);self.assertEqual(0,owner.previous['stage'])
            self.assertTrue(absent(owner.current()['original']));self.assertEqual(1,self.f.launches)
            self.assertEqual('ios-graphics-actor-0-process-retirement.json',owner.store.path.name)

    def test_bound_foreign_pid_or_changed_source_cannot_query_a_retired_scope(self):
        with self.assertRaises((ValueError,RuntimeError)):self.runtime._retired_process_observer('test-only',self.binding,self.source)
        self.f.adapter.invoke('test-only','app.stop',{})
        for binding,source in ((dict(self.binding,processIdentity='43'),self.source),(self.binding,dict(self.source,instance='e'*32))):
            with self.subTest(binding=binding['processIdentity']),self.assertRaises((ValueError,RuntimeError)):
                self.runtime._retired_process_observer('test-only',binding,source)
        self.assertNotIn('mobile: overteRetiredProcessInfo',self.calls)

    def test_candidate_change_after_reader_construction_blocks_the_original_sdk_query(self):
        self.f.adapter.invoke('test-only','app.stop',{});reader=self.runtime._retired_process_observer('test-only',self.binding,self.source)
        self.f.artifact.write_bytes(b'Changed original candidate')
        with self.assertRaises(NativeUIError):reader.read()
        self.assertNotIn('mobile: overteRetiredProcessInfo',self.calls)


if __name__=='__main__':unittest.main()
