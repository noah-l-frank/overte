"""Actual Source4 fixed scripts/range writer; declared native transport model.

No Qt/native publisher, compiler, device, ADB server or Domain is executed.
The app-private producer files and all raw ranges are retained originals.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import random
import shlex
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.chat_journey.archive_file import signature
from adapters.pico4.audio_raw_archive import AudioRawArchive
from adapters.pico4.emote_stream_frame import ACTION,CONTROL_LIMIT,FRAME_LIMIT
from adapters.pico4 import emote_stream_wire as source
from adapters.script_journey.lock import ScriptSourceLock

RETAINED=[]


class StreamWireTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='pico-emote-stream4-wire-'))
        print('Retained original Emote Source4 wire fixture:',self.root,flush=True)
        self.app=self.root/'app';self.app.mkdir(mode=0o700)
        (self.app/'files').mkdir(mode=0o700);(self.app/'files/overte-e2e').mkdir(mode=0o700)
        self.host=self.root/'host';self.host.mkdir(mode=0o700)
        self.now=1.;self.epoch=20000;self.okay=True;self.binary_calls=[];self.sends=[];self.post=None
        self.cost=dict(parts=0,storedBytes=0,decodedBytes=0);self.wires=[]
        self.lock=ScriptSourceLock(self.host/'script-sources.lock')
        self.raw=AudioRawArchive(self.host/'emote.child-stream-raw.json',dict(picoEmoteStreamOriginalsVersion=1,testOnly=True),
            self.lock,lambda:None,lambda:dict(self.cost),lambda:self.now)
        self.addCleanup(self.finalize)
        self.native=SimpleNamespace(send=self.send,clock_ms=lambda:self.epoch,guard=lambda:self.okay)
        self.adapter=SimpleNamespace(kind='pico',profile=dict(package='org.overte.pico'),adb=SimpleNamespace(execute_bytes=self.binary))
        self.wire=source.PicoEmoteStreamWire(self.adapter,'declared-owned-model',self.native,self.raw,
            lambda:self.okay,role='primary',monotonic=lambda:self.now)
        self.sample=self.app/'files/overte-e2e/feature-pico-remote-avatar-stream.json'
        self.control=self.app/'files/overte-e2e/feature-pico-remote-avatar-stream-control.json'
        self.write(self.sample,b'{"nativeOnlySample":1}')

    def write(self,path,raw):
        with path.open('wb') as output:output.write(raw)
        path.chmod(0o600)

    def records(self):return [row for page in self.raw.pages.values() for row in page['receipts'] if row is not None]

    def finalize(self):
        def inventory():return {str(path.relative_to(self.root)):dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            physical=signature(path.stat())) for path in self.root.rglob('*') if path.is_file()}
        before=inventory();self.assertTrue(self.raw.close_host());after=inventory();self.assertEqual(before,after)
        RETAINED.append(dict(root=str(self.root),files=after,closedOriginalDescriptors=True))

    def binary(self,arguments,*,target,timeout):
        self.assertEqual('declared-owned-model',target);self.assertEqual('exec-out',arguments[0]);self.assertTrue(0<timeout<=5)
        argv=shlex.split(arguments[1]);self.assertEqual(8,len(argv))
        self.assertEqual(['run-as','org.overte.pico','sh','-c'],argv[:4]);self.assertIn(argv[4],source.SCRIPTS.values())
        self.assertEqual('overte-pico-emote-stream',argv[5]);self.binary_calls.append(deepcopy(arguments))
        completed=subprocess.run(['sh','-c',argv[4],*argv[5:]],cwd=self.app,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,timeout=timeout,check=False)
        self.wires.append(completed.stdout)
        if self.post:self.post()
        return completed.stdout

    def send(self,request):
        # This is the existing native.send final phase-fence edge, not a fake
        # accepted native effect. Both archive reservations already exist.
        self.assertEqual(2,len(self.raw.state['pending']));self.native.phase_fence.check()
        self.sends.append(deepcopy(request));self.write(self.control,json.dumps(dict(actualCommand=request)).encode())

    def request(self):return dict(schemaVersion=1,commandId='a'*32,action=ACTION,operation='arm',runId='d'*32,
        subjectSessionId='11111111-1111-4111-8111-111111111111',ownerPolicy='{}')

    def test_fixed_actual_script_retains_wire_before_parser_and_never_sends_for_sample(self):
        parser=source.strict_json;observed=[]
        def parse(body):
            self.assertEqual(self.wires[-1],self.raw.literal(self.wire.last_reference));observed.append(body);return parser(body)
        with patch.object(source,'strict_json',side_effect=parse):value=self.wire.read()
        self.assertEqual(dict(nativeOnlySample=1),value);self.assertEqual(1,len(observed));self.assertEqual([],self.sends)
        self.assertEqual(1,len(self.records()));self.assertFalse(self.raw.state['pending'])

    def test_actual_near_cap_incompressible_nul_literal_is_retained_before_utf8_or_json(self):
        literal=random.Random(519).randbytes(FRAME_LIMIT-1)+b'\0';self.write(self.sample,literal)
        with self.assertRaises((NativeUIError,UnicodeDecodeError,ValueError)):self.wire.read()
        wire=self.raw.literal(self.wire.last_reference);self.assertEqual(self.wires[-1],wire)
        nonce=wire[len(source.HEADER):].split(b'\n',1)[0].decode();self.assertEqual(literal,source.literal(wire,nonce,FRAME_LIMIT))
        self.assertTrue(self.wire.failed);self.assertEqual(1,len(self.binary_calls))

    def test_actual_overcap_prefix_stays_original_and_incomplete_without_parser(self):
        self.write(self.sample,b'x'*(FRAME_LIMIT+10))
        with patch.object(source,'strict_json') as parser,self.assertRaises(NativeUIError):self.wire.read()
        parser.assert_not_called();wire=self.raw.literal(self.wire.last_reference)
        self.assertEqual(self.wires[-1],wire);self.assertIn(b'x'*(FRAME_LIMIT+1),wire)
        with self.assertRaises(NativeUIError):self.wire.read()
        self.assertEqual(1,len(self.binary_calls))

    def test_duplicate_json_keys_are_retained_then_refused(self):
        self.write(self.sample,b'{"native":1,"native":2}')
        with self.assertRaises(NativeUIError):self.wire.read()
        self.assertEqual(self.wires[-1],self.raw.literal(self.wire.last_reference))

    def test_capacity_refusal_emits_zero_actual_getter(self):
        self.cost['parts']=512
        with self.assertRaises(NativeUIError):self.wire.read()
        self.assertEqual([],self.binary_calls);self.assertEqual([],self.sends)

    def test_capacity_refusal_emits_zero_actual_control_send(self):
        self.cost['storedBytes']=16*1024*1024
        with self.assertRaises(NativeUIError):self.wire.control(self.request())
        self.assertEqual([],self.binary_calls);self.assertEqual([],self.sends)

    def test_control_guarantees_both_ack_and_real_send_return_before_dispatch(self):
        request=self.request();value=self.wire.control(request)
        self.assertEqual(dict(actualCommand=request),value);self.assertEqual([request],self.sends)
        rows=self.records();self.assertEqual(2,len(rows));self.assertEqual('bytes',rows[0]['kind'])
        self.assertEqual('none',rows[1]['kind']);self.assertEqual('send-return',rows[1]['command']['transport'])
        self.assertEqual(self.wires[-1],self.raw.literal(self.wire.last_reference))

    def test_last_native_callback_delay_sends_zero_with_both_issued_reservations(self):
        original=self.native.send
        def delayed(request):self.now+=1.5;return original(request)
        # Construct on the actual callback to be pinned; never hot-rebind it.
        del self.native.phase_fence;self.native.send=delayed
        self.wire=source.PicoEmoteStreamWire(self.adapter,'declared-owned-model',self.native,self.raw,
            lambda:self.okay,role='primary',monotonic=lambda:self.now)
        with self.assertRaises(NativeUIError):self.wire.control(self.request())
        self.assertEqual([],self.sends);self.assertEqual([],self.binary_calls);self.assertEqual(2,len(self.raw.state['pending']))

    def test_already_issued_wire_survives_business_guard_loss_then_zero_new_getter(self):
        self.post=lambda:setattr(self,'okay',False)
        with self.assertRaises(NativeUIError):self.wire.read()
        self.assertEqual(self.wires[-1],self.raw.literal(self.wire.last_reference))
        with self.assertRaises(NativeUIError):self.wire.read()
        self.assertEqual(1,len(self.binary_calls))

    def test_actual_partial_timeout_bytes_are_retained_before_terminal_refusal(self):
        original=self.binary
        def partial(arguments,**options):
            wire=original(arguments,**options);raise subprocess.TimeoutExpired('owned exec-out model',1,output=wire[:43])
        self.adapter.adb.execute_bytes=partial;del self.native.phase_fence
        self.wire=source.PicoEmoteStreamWire(self.adapter,'declared-owned-model',self.native,self.raw,
            lambda:self.okay,role='primary',monotonic=lambda:self.now)
        with self.assertRaises(subprocess.TimeoutExpired):self.wire.read()
        self.assertEqual(self.wires[-1][:43],self.raw.literal(self.wire.last_reference));self.assertTrue(self.wire.failed)

    def test_native_issued_write_marker_prevents_current_sample_acceptance(self):
        marker=self.sample.with_name('feature-pico-remote-avatar-stream-pending.json');self.write(marker,b'actual native pending')
        with self.assertRaises(NativeUIError):self.wire.read()
        self.assertEqual(b'',self.raw.literal(self.wire.last_reference));self.assertTrue(marker.exists())

    def test_legacy_same_arena_file_prevents_source4_acceptance(self):
        legacy=self.sample.with_name('feature-pico-remote-avatar.json');self.write(legacy,b'{"sourceVersion":3}')
        with self.assertRaises(NativeUIError):self.wire.read()
        self.assertEqual(b'',self.raw.literal(self.wire.last_reference));self.assertEqual(1,len(self.binary_calls))


if __name__=='__main__':unittest.main()
