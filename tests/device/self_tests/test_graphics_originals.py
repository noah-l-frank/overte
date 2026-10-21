"""Private original stereo PNG/metadata ownership, with no device or renderer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.graphics_journey.originals import GraphicsOriginals,record,transition
from adapters.normal_ui import NativeUIError
from self_tests.test_stereo_graphics_evidence import Source,encode,RUN,TICKET


class GraphicsOriginalTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup);self.root=Path(self.temporary.name)
        self.raw,self.body,self.sample=Source().acquire();self.records={};self.events=[];self.okay=True;self.clock=0.;self.fail=None
        self.writer=GraphicsOriginals(self.root,self.body['binding'],RUN,'primary',0,lambda:self.okay,self.intent,monotonic=lambda:self.clock)
    def intent(self,value):
        transition(self.records.get(value['name']),value);self.events.append(deepcopy(value))
        if self.fail==value['phase']:raise OSError('Synthetic failed durable original intent')
        self.records[value['name']]=deepcopy(value)
    def image(self):return self.writer.write(TICKET,self.body['capture'],self.raw)
    def metadata(self):return self.writer.write(TICKET,self.body['capture'],encode(self.body),kind='file')

    def test_original_pair_is_written_once_with_planned_and_opened_intent_before_any_bytes(self):
        def observed(value):
            path=self.root/value['name']
            if value['phase']=='planned':self.assertFalse(path.exists())
            if value['phase']=='opened':self.assertEqual(0,path.stat().st_size)
            self.intent(value)
        self.writer.intent=observed;image=self.image();metadata=self.metadata()
        self.assertEqual(['planned','opened','saved']*2,[value['phase'] for value in self.events])
        self.assertEqual(self.raw,self.writer.read(image));self.assertEqual(encode(self.body),self.writer.read(metadata))
        self.assertEqual(self.raw,GraphicsOriginals.archive(self.root,image));self.assertEqual(encode(self.body),GraphicsOriginals.archive(self.root,metadata))
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),image['sha256'])
        for item in (image,metadata):self.assertEqual(0o600,(self.root/item['name']).stat().st_mode&0o777)
        self.assertEqual(self.body['capture'],image['capture']);self.assertNotEqual(image['name'],metadata['name'])

    def test_original_names_and_inode_cannot_be_overwritten_replaced_or_relabelled(self):
        image=self.image();original=(self.root/image['name']).read_bytes()
        with self.assertRaises((OSError,RuntimeError)):self.image()
        self.assertEqual(original,(self.root/image['name']).read_bytes())
        for change in (dict(role='actor'),dict(stage=1),dict(name='../foreign.png'),dict(kind='file')):
            value=deepcopy(image);value.update(change)
            with self.subTest(change=change),self.assertRaises((RuntimeError,ValueError,OSError)):self.writer.read(value)
        old=self.root/'preserved.png';(self.root/image['name']).rename(old);(self.root/image['name']).write_bytes(original)
        (self.root/image['name']).chmod(0o600)
        with self.assertRaises(NativeUIError):self.writer.read(image)
        self.assertEqual(original,old.read_bytes())

    def test_wrong_metadata_owner_capture_or_closed_schema_fails_before_allocating_a_file(self):
        for key,value in (('role','actor'),('ticket','f'*32),('runId','e'*32),('stage',1),('expectedState',{})):
            body=deepcopy(self.body);body[key]=value
            with self.subTest(key=key),self.assertRaises((ValueError,RuntimeError)):
                self.writer.write(TICKET,self.body['capture'],encode(body),kind='file')
        self.assertEqual([],self.events);self.assertEqual([],list(self.root.iterdir()))

    def test_png_storage_is_historical_and_ticket_identity_remains_a_durable_and_pixel_obligation(self):
        image=self.image();changed=deepcopy(image);changed['ticket']='f'*32
        # File identity alone cannot decode the challenge from a headset image.
        # The owning immutable transition and independent stereo pixel verifier
        # provide that separate guarantee; storage does not invent it.
        self.assertEqual(self.raw,self.writer.read(changed))
        with self.assertRaises(NativeUIError):transition(image,changed)

    def test_modified_png_metadata_digest_or_truncated_original_is_not_current_storage(self):
        image=self.image();metadata=self.metadata()
        for value in (image,metadata):
            path=self.root/value['name'];original=path.read_bytes();path.write_bytes(original[:-1])
            with self.assertRaises((RuntimeError,ValueError)):self.writer.read(value)
            path.write_bytes(original)
        value=deepcopy(metadata);value['sha256']='0'*64
        with self.assertRaises(NativeUIError):self.writer.read(value)
        with self.assertRaises((RuntimeError,ValueError)):self.writer.write(TICKET,self.body['capture'],self.raw[:-1])

    def test_uncommitted_intent_prevents_allocation_and_failed_open_intent_keeps_empty_owned_file(self):
        self.fail='planned'
        with self.assertRaises(OSError):self.image()
        self.assertEqual([],list(self.root.iterdir()));self.assertEqual({},self.records)
        self.fail='opened'
        with self.assertRaises(OSError):self.image()
        self.assertEqual('planned',next(iter(self.records.values()))['phase'])
        self.assertEqual(0,next(self.root.iterdir()).stat().st_size)
        self.assertEqual('opened',self.events[-1]['phase']);self.assertIsNotNone(self.events[-1]['file'])

    def test_lost_saved_journal_write_keeps_opened_original_and_never_fabricates_a_saved_phase(self):
        self.fail='saved'
        with self.assertRaises(OSError):self.image()
        original=next(iter(self.records.values()));self.assertEqual('opened',original['phase'])
        self.assertEqual(self.raw,self.writer.read(original));self.assertFalse(self.writer.absent(original))
        with self.assertRaises((RuntimeError,OSError)):self.image()
        self.assertEqual('opened',next(iter(self.records.values()))['phase'])

    def test_hardlink_symlink_mode_and_guard_changes_preserve_foreign_bytes_and_originals(self):
        image=self.image();path=self.root/image['name'];link=self.root/'other'
        os.link(path,link)
        with self.assertRaises(NativeUIError):self.writer.read(image)
        link.unlink();path.chmod(0o644)
        with self.assertRaises(NativeUIError):self.writer.read(image)
        path.chmod(0o600);path.rename(link);path.symlink_to(link)
        with self.assertRaises((RuntimeError,OSError)):self.writer.read(image)
        self.assertEqual(self.raw,link.read_bytes());path.unlink();link.rename(path);self.okay=False
        with self.assertRaises(NativeUIError):self.writer.read(image)
        self.assertEqual(self.raw,path.read_bytes())

    def test_archive_is_historical_and_does_not_supply_a_new_source_clock_or_native_fact(self):
        image=self.image();self.clock=9000
        self.assertEqual(self.raw,GraphicsOriginals.archive(self.root,image));self.assertEqual(20000,image['capture']['capturedEpochMs'])
        before=deepcopy(image);record(image);self.assertEqual(before,image)
        with self.assertRaises(TypeError):GraphicsOriginals.archive(self.root,image,epoch=900000)

    def test_expired_final_guard_or_regressing_monotonic_clock_cannot_finish_a_file_read(self):
        image=self.image();guard=self.writer.guard
        def late():self.clock+=6;return guard()
        self.writer.guard=late
        with self.assertRaises(NativeUIError):self.writer.read(image)
        self.writer.guard=guard;self.clock=-1
        with self.assertRaises(NativeUIError):self.writer.read(image)
        self.assertEqual(self.raw,(self.root/image['name']).read_bytes())

    def test_owner_intent_transition_cannot_skip_regress_or_change_original_capture_or_file_identity(self):
        self.image();planned,opened,saved=self.events
        for old,new in ((None,opened),(planned,saved),(saved,opened),(opened,planned)):
            with self.subTest(phases=(old and old['phase'],new['phase'])),self.assertRaises(NativeUIError):transition(old,new)
        for changes in (dict(sha256='0'*64),dict(ticket='f'*32),dict(file=dict(device=0,inode=99))):
            new=deepcopy(saved);new.update(changes)
            with self.assertRaises((RuntimeError,ValueError)):transition(opened,new)
        transition(saved,deepcopy(saved))


if __name__=='__main__':unittest.main()
