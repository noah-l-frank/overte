"""Actual owned PC originals and admitted Pico exports; media is a model."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import uuid
from adapters.normal_ui import NativeUIError
from adapters.pico4.audio_common_files import PicoAudioCommonFiles1
from self_tests.test_pico_audio_bundle_acquisition import AudioBundleAcquisitionTests


class FileTests(unittest.TestCase):
    def setUp(self):
        self.fixture=AudioBundleAcquisitionTests();self.addCleanup(self.fixture.doCleanups);self.fixture.setUp()
        self.f=self.fixture.fixture;self.actor=self.f.actor
        self.files=PicoAudioCommonFiles1(self.actor);self.addCleanup(self.files.close_host)
        self.ticket=uuid.uuid4().hex
        self.actor.arm(self.ticket,3.25);self.actor.wait_saved(self.ticket)
        self.peer=self.actor.peer();self.packet,self.raw=self.peer.original(self.f.f.run,self.ticket)

    def test_original_peer_wav_roundtrip_keeps_source_and_complete_file_stamp(self):
        value=self.files.write(self.ticket,'peer',self.ticket,self.raw,self.packet)
        self.assertEqual(2,value['audioFileVersion']);self.assertEqual(self.raw,self.files.read(value['name']))
        self.assertEqual(self.packet,value['provenance']);self.assertEqual(8,len(value['file']['signature']))
        row=self.files.saved(self.ticket,'peer');self.assertEqual(value['file']['signature'],row['physical'])
        self.assertEqual(value,self.files.value(row));self.assertEqual([],self.actor.raws.state['pending'])
        self.assertEqual(value,self.files.write(self.ticket,'peer',self.ticket,self.raw,self.packet))

    def test_equal_bytes_foreign_inode_is_not_adopted(self):
        value=self.files.write(self.ticket,'peer',self.ticket,self.raw,self.packet)
        path=self.files.root/value['name'];other=path.with_name(path.name+'.replacement');other.write_bytes(self.raw);other.chmod(0o600);other.replace(path)
        with self.assertRaises(NativeUIError):self.files.read(value['name'])
        self.assertTrue(self.files.failed);self.assertIsNotNone(self.files.failure)

    def test_foreign_capture_provenance_cannot_create_an_export(self):
        packet=deepcopy(self.packet);packet['captureId']='f'*32
        with self.assertRaises(NativeUIError):self.files.write(self.ticket,'peer',self.ticket,self.raw,packet)
        self.assertEqual([],self.files.state['files'])
        self.assertFalse(any(self.files.root.glob('audio-*.wav')))

    def test_full_original_bank_refuses_before_file_creation(self):
        with (self.f.f.path/'owned-capacity.bin').open('wb') as stream:stream.truncate(16*1024*1024)
        with patch.object(self.files.files,'write',side_effect=AssertionError('No file IO')) as write:
            with self.assertRaises(NativeUIError):self.files.write(self.ticket,'peer',self.ticket,self.raw,self.packet)
            write.assert_not_called()
        self.assertEqual([],self.files.state['files'])

    def test_retire_preserves_exact_wave_and_idempotent_absence_in_original_bank(self):
        value=self.files.write(self.ticket,'peer',self.ticket,self.raw,self.packet)
        retired=self.files.retire(value['name']);self.assertEqual('retired',retired['phase'])
        self.assertFalse((self.files.root/value['name']).exists())
        row=self.files.saved(self.ticket,'peer')
        self.assertEqual(self.raw,b''.join(self.actor.raws.literal(ref) for ref in row['retirement']['rawReferences']))
        before=self.actor.raws.state['reads'];self.assertEqual(retired,self.files.retire(value['name']))
        self.assertEqual(before,self.actor.raws.state['reads'])
        with self.assertRaises(NativeUIError):self.files.read(value['name'])

    def test_retire_full_bank_keeps_original_named_export(self):
        value=self.files.write(self.ticket,'peer',self.ticket,self.raw,self.packet)
        with (self.f.f.path/'owned-capacity.bin').open('wb') as stream:stream.truncate(16*1024*1024)
        with self.assertRaises(NativeUIError):self.files.retire(value['name'])
        self.assertEqual(self.raw,(self.files.root/value['name']).read_bytes())
        self.assertEqual('saved',self.files.saved(self.ticket,'peer')['record']['phase'])
        self.assertTrue(self.files.failed)

    def test_retire_wrong_original_inode_preserves_foreign_file(self):
        value=self.files.write(self.ticket,'peer',self.ticket,self.raw,self.packet)
        path=self.files.root/value['name'];other=path.with_name(path.name+'.replacement')
        other.write_bytes(self.raw);other.chmod(0o600);other.replace(path)
        before=self.actor.raws.state['reads']
        with self.assertRaises(NativeUIError):self.files.retire(value['name'])
        self.assertEqual(before,self.actor.raws.state['reads']);self.assertEqual(self.raw,path.read_bytes())

    def test_recreated_export_cannot_borrow_original_retirement(self):
        value=self.files.write(self.ticket,'peer',self.ticket,self.raw,self.packet)
        self.files.retire(value['name']);path=self.files.root/value['name'];path.write_bytes(self.raw);path.chmod(0o600)
        before=self.actor.raws.state['reads']
        with self.assertRaises(NativeUIError):self.files.retire(value['name'])
        self.assertEqual(before,self.actor.raws.state['reads']);self.assertEqual(self.raw,path.read_bytes())


if __name__=='__main__':unittest.main()
