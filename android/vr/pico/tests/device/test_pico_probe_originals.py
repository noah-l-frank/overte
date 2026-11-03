"""Actual SDK/framed host-file reads; Android run-as remains a transport seam.

The exact fixed read script executes against owned temporary files through a
declared exec-out facade. No ADB server, device, compiler or laboratory runs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from adapters.android.adapter import AndroidAdapter,ANDROID_DEBUG_PROBE
from adapters.normal_ui import NativeUIError
from adapters.pico4.audio_raw_archive import AudioRawArchive
from adapters.pico4 import probe_originals as subject
from adapters.script_journey.lock import ScriptSourceLock


class Clock:
    def __init__(self):self.value=0.
    def now(self):return self.value


class HostProbeFile:
    def __init__(self,directory):
        self.root=directory;self.calls=0;self.old_calls=0;self.last_wire=None
        self.post=None;self.timeout=False;self.missing_footer=False
    def read_debug_app_file(self,target,package,path,**options):
        self.old_calls+=1
        return (self.root/path).read_text()
    def execute_bytes(self,arguments,*,target,timeout):
        assert arguments[0]=='exec-out' and target=='declared-pico' and 0<timeout<=5
        argv=shlex.split(arguments[1])
        assert argv[:4]==['run-as','org.overte.pico','sh','-c'] and argv[4]==subject.SCRIPT
        assert argv[5]=='overte-pico-probe' and argv[7]==str(subject.LIMIT+1)
        assert len(argv)==8
        self.calls+=1
        completed=subprocess.run(['sh','-c',argv[4],*argv[5:]],cwd=self.root,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=False)
        wire=completed.stdout
        if self.missing_footer:wire=wire.split(subject.FOOTER)[0]
        self.last_wire=wire
        if self.post:self.post()
        if self.timeout:
            error=subprocess.TimeoutExpired(['declared-exec-out'],timeout,output=wire[:len(wire)//2])
            raise RuntimeError('Declared partial transport timeout') from error
        return wire


class SDK:
    read_probe_snapshot=AndroidAdapter.read_probe_snapshot
    def __init__(self,adb):self.kind='pico';self.profile={'package':'org.overte.pico'};self.adb=adb
    def probe_retry_policy(self):return 2,.001
    def probe_maximum_age_seconds(self):return 5


class PicoProbeOriginalTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700)
        self.app=self.root/'app';self.app.mkdir(mode=0o700)
        (self.app/'files').mkdir(mode=0o700);(self.app/'files/overte-e2e').mkdir(mode=0o700)
        self.path=self.app/ANDROID_DEBUG_PROBE
        self.snapshot=dict(schemaVersion=1,sampleEpochMs=int(time.time()*1000),sampleSequence=1,
            actualModelValue='ä Ω 東京')
        self.write(json.dumps(self.snapshot,ensure_ascii=False).encode())
        self.storage=self.root/'originals';self.storage.mkdir(mode=0o700)
        self.clock=Clock();self.lock=ScriptSourceLock(self.storage/'script-sources.lock');self.delay=0;self.full=False
        def bill():
            self.clock.value+=self.delay
            return dict(parts=512 if self.full else 0,storedBytes=0,decodedBytes=0,files=0)
        self.archive=AudioRawArchive(self.storage/'probe-raw.json',dict(testOnlyProbeArchiveVersion=1),
            self.lock,self.lock.assert_held,bill,self.clock.now)
        self.addCleanup(lambda archive=self.archive:self.assertTrue(archive.close_host()))
        self.transport=HostProbeFile(self.app);self.sdk=SDK(self.transport)
        self.guard=lambda:True
        self.reader=subject.PicoProbeOriginals(self.sdk,'declared-pico',self.archive,
            lambda:self.guard(),role='primary',monotonic=self.clock.now)
    def write(self,raw):
        with self.path.open('wb') as output:output.write(raw)
        self.path.chmod(0o600)
    def wire(self):
        with self.lock.held():return self.archive.literal(json.loads(self.reader.receipts[-1]))

    def test_actual_sdk_and_fixed_host_script_retain_wire_before_sdk_json(self):
        loads=json.loads;parsed=[];literal=self.path.read_text()
        def observed(raw,*args,**options):
            if type(raw) is str and raw==literal:
                self.assertTrue(self.reader.receipts);self.assertEqual(self.transport.last_wire,self.wire());parsed.append(True)
            return loads(raw,*args,**options)
        with patch('json.loads',observed):value=self.reader.read(0)
        self.assertEqual(self.snapshot,value);self.assertEqual([True],parsed)
        self.assertEqual(1,self.transport.calls);self.assertEqual(0,self.transport.old_calls)
        self.assertEqual(self.transport.last_wire,self.wire())

    def test_unchanged_default_sdk_getter_and_phone_callback_boundary(self):
        self.assertEqual(self.snapshot,self.sdk.read_probe_snapshot('declared-pico','org.overte.pico',None))
        self.assertEqual(1,self.transport.old_calls);self.assertEqual(0,self.transport.calls)
        self.sdk.kind='phone'
        self.assertEqual(self.snapshot,self.sdk.read_probe_snapshot('declared-pico','org.overte.pico',None))
        before=self.transport.old_calls
        with self.assertRaises(RuntimeError):
            self.sdk.read_probe_snapshot('declared-pico','org.overte.pico',None,raw_reader=lambda *_a,**_k:'{}')
        self.assertEqual(before,self.transport.old_calls)

    def test_invalid_utf8_return_is_durable_before_decoder_refusal_and_no_new_query(self):
        self.write(b'\xff\x00actual original')
        with self.assertRaises(NativeUIError):self.reader.read()
        self.assertIn(b'\xff\x00actual original',self.wire());self.assertEqual(1,self.transport.calls)
        with self.assertRaises(NativeUIError):self.reader.read()
        self.assertEqual(1,self.transport.calls)

    def test_oversized_real_file_keeps_only_exact_bounded_prefix_and_refuses_json(self):
        self.write(b'x'*(subject.LIMIT+4096))
        with self.assertRaises(NativeUIError):self.reader.read()
        wire=self.wire();self.assertEqual(self.transport.last_wire,wire)
        self.assertEqual(subject.LIMIT+1,wire.count(b'x'));self.assertLessEqual(len(wire),subject.WIRE_LIMIT)
        self.assertEqual(1,self.transport.calls)

    def test_late_acquired_wire_is_archived_before_original_read_clock_refuses(self):
        self.transport.post=lambda:setattr(self.clock,'value',5.05)
        with self.assertRaises(NativeUIError):self.reader.read()
        self.assertEqual(self.transport.last_wire,self.wire());self.assertEqual(1,self.transport.calls)

    def test_slow_real_reservation_blocks_before_exec_out_under_frozen_product_clock(self):
        self.delay=5.05
        with self.assertRaises(NativeUIError):self.reader.read()
        self.assertEqual(0,self.transport.calls);self.assertEqual((),self.reader.receipts)
        self.assertEqual(1,len(self.archive.state['pending']))

    def test_original_namespace_capacity_refuses_before_native_read(self):
        self.full=True
        with self.assertRaises(NativeUIError):self.reader.read()
        self.assertEqual(0,self.transport.calls);self.assertEqual([],self.archive.state['pending'])

    def test_missing_remote_success_frame_retains_exact_wire_without_a_snapshot(self):
        self.transport.missing_footer=True
        with self.assertRaises(NativeUIError):self.reader.read()
        self.assertEqual(self.transport.last_wire,self.wire());self.assertEqual(1,self.transport.calls)

    def test_partial_timeout_output_is_retained_without_success_or_later_queries(self):
        self.transport.timeout=True
        with self.assertRaises(NativeUIError):self.reader.read()
        self.assertEqual(self.transport.last_wire[:len(self.transport.last_wire)//2],self.wire())
        with self.assertRaises(NativeUIError):self.reader.read()
        self.assertEqual(1,self.transport.calls)

    def test_changed_candidate_after_read_cannot_prevent_raw_retention_or_return_facts(self):
        self.transport.post=lambda:setattr(self,'guard',lambda:False)
        with self.assertRaises(NativeUIError):self.reader.read()
        self.assertEqual(self.transport.last_wire,self.wire());self.assertEqual(1,self.transport.calls)

    def test_callback_cannot_extend_original_five_second_anchor(self):
        self.transport.post=lambda:setattr(self.reader,'started',4.)
        with self.assertRaises(NativeUIError):self.reader.read()
        self.assertEqual(self.transport.last_wire,self.wire())

    def test_duplicate_json_and_nonfinite_source_fields_cannot_be_accepted_by_sdk(self):
        for index,tail in enumerate((b',"value":1,"value":2}',b',"value":NaN}')):
            if index:self.setUp()
            raw=json.dumps(self.snapshot).encode()[:-1]+tail;self.write(raw)
            with self.assertRaises(NativeUIError):self.reader.read()
            self.assertIn(raw,self.wire());self.assertEqual(1,self.transport.calls)

    def test_nested_read_is_sticky_before_second_transport_and_keeps_outer_return(self):
        def nested():
            with self.assertRaises(NativeUIError):self.reader.read()
        self.transport.post=nested
        with self.assertRaises(NativeUIError):self.reader.read()
        self.assertEqual(self.transport.last_wire,self.wire());self.assertEqual(1,self.transport.calls)

    def test_foreign_binary_getter_is_refused_before_any_transport(self):
        original=self.sdk.adb.execute_bytes
        self.sdk.adb.execute_bytes=lambda *_a,**_k:original(['wrong'])
        with self.assertRaises(NativeUIError):self.reader.read()
        self.assertEqual(0,self.transport.calls)

    def test_existing_sdk_retry_uses_two_distinct_literal_reads_and_original_cursor(self):
        second=dict(self.snapshot,sampleSequence=2)
        def publish_next():
            self.transport.post=None
            self.write(json.dumps(second,ensure_ascii=False).encode())
        self.transport.post=publish_next
        self.assertEqual(second,self.reader.read(1))
        self.assertEqual(2,self.transport.calls);self.assertEqual(2,len(self.reader.receipts))
        with self.lock.held():
            originals=[self.archive.literal(json.loads(reference)) for reference in self.reader.receipts]
        self.assertIn(b'"sampleSequence": 1',originals[0])
        self.assertIn(b'"sampleSequence": 2',originals[1])
        self.assertEqual(0,self.transport.old_calls)

    def test_unavailable_source_candidate_blocks_before_reservation_or_transport(self):
        self.guard=lambda:False
        with self.assertRaises(NativeUIError):self.reader.read()
        self.assertEqual(0,self.transport.calls);self.assertEqual((),self.reader.receipts)
        self.assertEqual([],self.archive.state['pending'])

    def test_actual_file_symlink_refuses_without_reading_target(self):
        actual=self.path.with_name('actual-private.json');self.path.rename(actual);self.path.symlink_to(actual.name)
        with self.assertRaises(NativeUIError):self.reader.read()
        self.assertEqual(b'',self.wire());self.assertEqual(1,self.transport.calls)

    def test_actual_file_hardlink_refuses_without_returning_probe_contents(self):
        os.link(self.path,self.path.with_name('second-private.json'))
        with self.assertRaises(NativeUIError):self.reader.read()
        self.assertEqual(b'',self.wire());self.assertEqual(1,self.transport.calls)

    def test_actual_public_file_mode_keeps_wire_but_refuses_snapshot(self):
        self.path.chmod(0o644)
        with self.assertRaises(NativeUIError):self.reader.read()
        self.assertEqual(self.transport.last_wire,self.wire());self.assertEqual(1,self.transport.calls)

    def test_sdk_reader_substitution_is_refused_before_any_transport(self):
        self.sdk.read_probe_snapshot=lambda *_a,**_k:self.snapshot
        with self.assertRaises(NativeUIError):self.reader.read()
        self.assertEqual(0,self.transport.calls);self.assertEqual((),self.reader.receipts)


if __name__=='__main__':unittest.main()
