"""Bounded passive settings reader; native/typed bytes are explicit seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.pico4.snapshot_settings_originals import PicoSnapshotSettingsOriginals,KEYS,validate
from adapters.script_journey.lock import ScriptSourceLock


class Boundary:
    def __init__(self,root):
        self.epoch=20000;self.host=1.;self.sequence=0;self.value=None;self.guards=0;self.late=None;self.body=None
        self.lock=ScriptSourceLock(root/'script-sources.lock')
        self.reader=PicoSnapshotSettingsOriginals(self.send,lambda:self.body if self.body is not None else json.dumps(self.value),lambda:self.epoch,self.guard,123,self.lock,
            monotonic=lambda:self.host,sleep=lambda duration:None)
    def guard(self):
        self.guards+=1
        if self.guards==2 and self.late:self.late()
        return True
    def send(self,command):
        self.sequence+=1;entries={key:dict(present=False,value=None) for key in KEYS};cache=dict(initialized=False,set=False,value='',defaultValue='')
        blob=json.dumps(dict(entries=entries,formatCache=cache),sort_keys=True).encode() # typed serializer seam
        self.value=dict(snapshotSettingsOriginalsVersion=1,commandId=command['commandId'],runId=command['runId'],pid=123,sequence=self.sequence,capturedEpochMs=self.epoch,
            source=dict(snapshotInstance='d'*32,managerInstance='c'*32,entriesEpochMs=self.epoch,entries=entries,formatCache=cache,
                typedSerializedBase64=base64.b64encode(blob).decode(),typedSha256=hashlib.sha256(blob).hexdigest()))


class SnapshotSettingsReaderTests(unittest.TestCase):
    def model(self):
        temporary=tempfile.TemporaryDirectory(prefix='snapshot-settings-reader-');self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700);return Boundary(root)
    def test_passive_original_capture_and_changed_native_birth_or_typed_hash_are_not_adopted(self):
        b=self.model();value=b.reader.capture('a'*32);self.assertFalse(value['source']['formatCache']['initialized'])
        self.assertEqual(value,validate(value,'a'*32,value['commandId'],123,b.epoch));saved=b.reader.original()
        for change in (lambda row:row['source'].update(managerInstance='e'*32),lambda row:row['source'].update(typedSha256='0'*64),lambda row:row['source']['entries'].pop(KEYS[0])):
            send=b.reader.send
            def changed(command):send(command);change(b.value)
            with self.subTest(change=change),patch.object(b.reader,'send',side_effect=changed),self.assertRaises(NativeUIError):b.reader.capture('a'*32)
            self.assertEqual(saved,b.reader.original())
    def test_final_native_clock_jump_after_last_guard_rejects_a_now_old_read(self):
        b=self.model();b.late=lambda:setattr(b,'epoch',b.epoch+2000)
        with self.assertRaises(NativeUIError):b.reader.capture('a'*32)
        self.assertIsNone(b.reader.previous);self.assertIsNone(b.reader.last_raw)
    def test_frozen_native_clock_does_not_hide_two_seconds_in_last_guard(self):
        b=self.model();b.late=lambda:setattr(b,'host',b.host+2)
        with self.assertRaises(NativeUIError):b.reader.capture('a'*32)
        self.assertIsNone(b.reader.previous)
    def test_raw_byte_limit_is_checked_before_decode_and_wrong_value_type_is_rejected(self):
        b=self.model();b.body='x'*65537
        with patch('adapters.pico4.snapshot_settings_originals.decode',side_effect=AssertionError('Bound before decode')),self.assertRaises(NativeUIError):b.reader.capture('a'*32)
        b.body=None;value=b.reader.capture('a'*32);bad=deepcopy(value);bad['source']['formatCache']['initialized']=1
        with self.assertRaises(NativeUIError):validate(bad,'a'*32,bad['commandId'],123,b.epoch)


if __name__=='__main__':unittest.main()
