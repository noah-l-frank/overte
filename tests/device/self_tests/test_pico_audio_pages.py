"""Explicit page/transport boundaries; no normal input or device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.pico4 import audio_pages as pages
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock
BRIDGE='01234567-89ab-4def-8123-456789abcdef'


def row():
    return dict(id='c'*32,pageId='d'*32,contextId='e'*32,rootId='f'*32,windowId='1'*32,firstObservedEpochMs=20000,
        pageAlive=True,contextAlive=True,rootAlive=True,windowAlive=True,alive=True,attached=True,visible=True,current=True,
        originalPeakValuesEnabled=False)


class Boundary:
    def __init__(self):
        self.time=0.;self.epoch=20000;self.sequence=0;self.originals=[];self.current='';self.open=False
        self.mutate=None;self.alive=True;self.freeze=False;self.packet=None
    def clock(self):return self.epoch+round(self.time*1000)
    def read(self):
        if not self.freeze:
            self.sequence+=1
            value=dict(instance='a'*32,sequence=self.sequence,capturedEpochMs=self.clock(),componentSourceSha256='b'*64,
                current=self.current,originals=deepcopy(self.originals))
            self.packet=dict(schemaVersion=1,bridgeId=BRIDGE,generation=BRIDGE,processId=123,elapsedMs=self.sequence,
                updatedEpochMs=self.clock(),lastCommandSequence=0,open=self.open,ready=self.open,controls=[],picoAudioPageVersion=1,picoAudioPages=value)
            if self.mutate:self.mutate(self.packet)
        return json.dumps(self.packet)
    def sleep(self,amount):self.time+=amount
    def reader(self,lock):return pages.PicoAudioPages(self.read,self.clock,lambda:self.alive,123,BRIDGE,lock,
        monotonic=lambda:self.time,sleep=self.sleep)


class AudioPageTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.lock=ScriptSourceLock(Path(self.directory.name)/'sources.lock')
    def test_original_hidden_detached_and_destroyed_page_retains_separate_context(self):
        native=Boundary();reader=native.reader(self.lock);reader.capture()
        native.originals=[row()];native.current='c'*32;native.open=True
        opened=reader.capture();self.assertEqual('c'*32,opened['picoAudioPages']['current'])
        native.current='';native.originals[0].update(visible=False,current=False)
        hidden=reader.capture();self.assertTrue(hidden['picoAudioPages']['originals'][0]['pageAlive'])
        native.originals[0].update(attached=False);reader.capture()
        native.originals[0].update(pageAlive=False)
        gone=reader.capture()['picoAudioPages']['originals'][0]
        self.assertTrue(gone['alive']);self.assertTrue(gone['contextAlive']);self.assertFalse(gone['pageAlive'])
        self.assertEqual(json.loads(reader.last_raw)['picoAudioPages'],reader.previous)
    def test_inconsistent_liveness_expected_flag_duplicate_identity_and_future_clock_fail(self):
        faults=(lambda v:v['picoAudioPages']['originals'][0].update(alive=False),
            lambda v:v['picoAudioPages']['originals'][0].update(pageAlive=False),
            lambda v:v['picoAudioPages'].update(current='f'*32),lambda v:v['picoAudioPages'].update(expectedClosed=True),
            lambda v:v['picoAudioPages']['originals'][0].update(contextId='d'*32),
            lambda v:v['picoAudioPages'].update(capturedEpochMs=20300))
        for fault in faults:
            native=Boundary();native.open=True;native.originals=[row()];native.current='c'*32;native.mutate=fault
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError,RuntimeError)):native.reader(self.lock).capture()
    def test_historical_restore_rejects_replacement_revival_lost_history_and_foreign_bridge(self):
        faults=(lambda v:v.update(bridgeId='abcdef01-2345-4678-8123-456789abcdef'),lambda v:v['picoAudioPages'].update(instance='f'*32),
            lambda v:v['picoAudioPages']['originals'][0].update(pageAlive=True,alive=True),
            lambda v:v['picoAudioPages']['originals'][0].update(contextId='f'*32),lambda v:v['picoAudioPages'].update(originals=[]))
        for fault in faults:
            native=Boundary();native.originals=[row()];native.originals[0].update(pageAlive=False,attached=False,visible=False,current=False)
            first=native.reader(self.lock).capture()['picoAudioPages'];reader=native.reader(self.lock);reader.restore(first);native.mutate=fault
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError,RuntimeError)):reader.capture()
            self.assertEqual(first,reader.previous)
    def test_unchanged_original_frame_is_not_a_new_sample_and_oversize_is_bounded_before_decode(self):
        native=Boundary();reader=native.reader(self.lock);reader.capture();native.freeze=True
        with self.assertRaises(NativeUIError):reader.capture()
        native=Boundary();reader=native.reader(self.lock);reader.read=lambda:' '*65537
        with mock.patch.object(pages,'decode') as decoder:
            with self.assertRaises(NativeUIError):reader.capture()
            decoder.assert_not_called()
    def test_final_native_jump_and_slow_copy_under_frozen_native_clock_are_rejected(self):
        for mode in ('guard','copy'):
            native=Boundary();reader=native.reader(self.lock)
            if mode=='guard':
                calls=0
                def guard():
                    nonlocal calls
                    calls+=1
                    if calls==3:native.epoch+=2000
                    return True
                reader.guard=guard
                with self.assertRaises(NativeUIError):reader.capture()
            else:
                original=pages.deepcopy
                def late(*args):
                    value=original(*args);native.time+=2;return value
                with mock.patch.object(pages,'deepcopy',side_effect=late):
                    with self.assertRaises(NativeUIError):reader.capture()
            self.assertIsNone(reader.previous)


if __name__=='__main__':unittest.main()
