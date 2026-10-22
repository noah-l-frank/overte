"""Request/callback originals are independent of requested images and delivery ACKs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.pico4 import snapshot_originals as source
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock

RUN='a'*32
BIRTH='12345678-1234-1234-1234-123456789abc'


class Boundary:
    def __init__(self):
        self.time=0.;self.epoch=20000;self.sequence=0;self.commands=[];self.value=None;self.mutate=None
        self.requests=[];self.alive=True
    def clock(self):return self.epoch+round(self.time*1000)
    def send(self,command):
        self.commands.append(deepcopy(command));self.sequence+=1
        self.value=dict(snapshotNativeCaptureVersion=1,commandId=command['commandId'],runId=command['runId'],instance=BIRTH,
            sequence=self.sequence,pid=123,capturedEpochMs=self.clock(),resources=dict(nativeReviewEnabled=True,activeRequests=0,
                taking360=False,waitingOnSnapshot=False,projectionTimerActive=False,projectionImagesBytes=0),requests=deepcopy(self.requests))
        if self.mutate:self.mutate(self.value)
    def read(self):return json.dumps(self.value)
    def sleep(self,amount):self.time+=amount
    def reader(self,lock):return source.PicoSnapshotOriginals(self.send,self.read,self.clock,lambda:self.alive,123,lock,
        monotonic=lambda:self.time,sleep=self.sleep)
    def request(self):
        return dict(birth='22345678-1234-1234-1234-123456789abc',requestId='original-request',registeredEpochMs=20000,
            alive=True,nativeState='active',events=[])


class SnapshotOriginalTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.lock=ScriptSourceLock(Path(self.directory.name)/'script-sources.lock')
    def test_original_raw_callbacks_and_weak_lifetime_are_preserved_not_requested_effects(self):
        native=Boundary();reader=native.reader(self.lock);first=reader.capture(RUN,'arm')
        self.assertEqual([],first['requests']);native.requests=[native.request()];second=reader.capture(RUN)
        native.requests[0].update(alive=False,nativeState='');native.requests[0]['events']=[dict(sequence=1,phase='complete',
            publishedEpochMs=20000,pathSha256='c'*64,basenameSha256='d'*64,error='')]
        third=reader.capture(RUN);self.assertTrue(second['requests'][0]['alive']);self.assertFalse(third['requests'][0]['alive'])
        self.assertEqual('complete',third['requests'][0]['events'][0]['phase'])
        self.assertEqual(native.read(),reader.original()['raw']);self.assertIs(reader.lock,self.lock)
        self.assertEqual({'schemaVersion','commandId','runId','action','operation'},set(native.commands[0]))
        self.assertFalse(any('expected' in key.lower() for command in native.commands for key in command))
    def test_cold_cursor_rejects_rewritten_events_replaced_birth_revived_weak_and_reused_query(self):
        faults=(lambda v:v['requests'][0].update(birth=BIRTH),lambda v:v['requests'][0].update(requestId='foreign'),
            lambda v:v['requests'][0].update(alive=True,nativeState='completed'),lambda v:v.update(sequence=1),
            lambda v:v['requests'][0]['events'][0].update(pathSha256='e'*64),lambda v:v.update(instance='32345678-1234-1234-1234-123456789abc'))
        for fault in faults:
            native=Boundary();native.requests=[native.request()];native.requests[0].update(alive=False,nativeState='')
            native.requests[0]['events']=[dict(sequence=1,phase='complete',publishedEpochMs=20000,pathSha256='c'*64,basenameSha256='d'*64,error='')]
            first=native.reader(self.lock).capture(RUN);reader=native.reader(self.lock);reader.restore(first);native.mutate=fault
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.capture(RUN)
            self.assertEqual(first,reader.previous)
    def test_unavailable_wrong_process_or_native_types_and_expected_values_fail(self):
        faults=(lambda v:v.update(available=False),lambda v:v.update(pid=True),lambda v:v.update(pid=124),
            lambda v:v.update(runId='f'*32),lambda v:v['resources'].update(activeRequests=True),
            lambda v:v['resources'].update(nativeReviewEnabled=False),lambda v:v.update(expectedPhase='complete'),
            lambda v:v.update(capturedEpochMs=19999))
        for fault in faults:
            native=Boundary();native.mutate=fault
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):native.reader(self.lock).capture(RUN)
            self.assertEqual(1,len(native.commands))
    def test_frozen_clock_late_accept_copy_guard_and_native_clock_jump_fail_before_commit(self):
        for where in ('accept','deepcopy','host-guard','native-guard'):
            native=Boundary();reader=native.reader(self.lock);reader.clock_ms=lambda:native.epoch
            if where in ('accept','deepcopy'):
                original=getattr(source,where)
                def late(*args):
                    value=original(*args);native.time+=2;return value
                with mock.patch.object(source,where,side_effect=late):
                    with self.assertRaises(NativeUIError):reader.capture(RUN)
            else:
                calls=0
                def guard():
                    nonlocal calls
                    calls+=1
                    if calls==2:
                        if where=='host-guard':native.time+=2
                        else:native.epoch+=2000
                    return True
                reader.guard=guard
                with self.assertRaises(NativeUIError):reader.capture(RUN)
            self.assertIsNone(reader.previous);self.assertIsNone(reader.last_raw)
    def test_raw_bound_before_decode_lost_query_not_resent_and_dead_process_not_sent(self):
        native=Boundary();reader=native.reader(self.lock);reader.read=lambda:' '*65537
        with mock.patch.object(source,'decode',wraps=source.decode) as decoder:
            with self.assertRaises(NativeUIError):reader.capture(RUN)
            decoder.assert_not_called()
        native=Boundary();reader=native.reader(self.lock);reader.read=lambda:None
        with self.assertRaises(NativeUIError):reader.capture(RUN)
        self.assertEqual(1,len(native.commands))
        native=Boundary();native.alive=False
        with self.assertRaises(NativeUIError):native.reader(self.lock).capture(RUN)
        self.assertEqual([],native.commands)


if __name__=='__main__':unittest.main()
