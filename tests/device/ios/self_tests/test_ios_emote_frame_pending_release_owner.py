"""Real PNG/file/once-intent host owners; selected native context is a model."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.native_vulkan_world_frame import absent
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.self_tests.emote_completed_frame_context_fixture import FrameCallbackContext
from ios.self_tests.test_ios_emote_completed_frame_context import owner
from self_tests.test_completed_frame_lease import BINDING,RUN


class PendingReleaseOwnerTests(unittest.TestCase):
    def pending(self,root):
        context=FrameCallbackContext(retain_trace=True);request='ios-'+'1'*32;current=owner(context,root,request)
        frame,raw=current.capture('2'*32);proof=current.release_once()
        self.assertFalse(absent(proof));self.assertEqual(1,proof['source']['callbacks'])
        return context,current,frame,raw,deepcopy(current.store.read())
    def archive(self,current,value):
        return VulkanWorldFrameOwner.archive_callback_pending_original(value,current.root,BINDING,RUN,'primary',0,current.request_id,current.lock)

    def test_actual_pending_callback_keeps_original_png_without_current_absence_or_live_factory(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);context,current,frame,raw,saved=self.pending(root)
            start=context.time
            with current.lock.held(),patch.object(context.world(current.request_id),'send',side_effect=AssertionError('Historical image read queried native')):
                actual,duty=self.archive(current,saved)
                self.assertEqual(raw,actual);self.assertFalse(absent(duty));self.assertEqual(1,duty['source']['callbacks'])
                duty['source']['callbacks']=0
                self.assertEqual(1,unpack(saved['transcript'])[-1]['receipt']['source']['callbacks'])
                with self.assertRaises(NativeUIError):VulkanWorldFrameOwner.archive_original(saved,root,BINDING,RUN,'primary',0,current.request_id,current.lock)
            self.assertEqual(start,context.time);self.assertEqual('captured',current.store.read()['phase'])
            self.assertEqual(frame['source']['image']['bytes'],len(raw));self.assertFalse(context.all_drained())

    def test_reentry_only_inspects_and_actual_token_death_finalizes_existing_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);context,current,_frame,raw,_saved=self.pending(root);slot=context.world(current.request_id)
            first=current.release_once();second=current.release_once()
            self.assertEqual('inspect',first['operation']);self.assertEqual('inspect',second['operation'])
            self.assertFalse(absent(second));self.assertEqual(1,sum(c['operation']=='release' for c in slot.commands))
            slot.drop_retained_trace();proof=current.release_once();self.assertTrue(absent(proof))
            self.assertEqual('released',current.store.read()['phase']);self.assertEqual(raw,current.archive())
            self.assertEqual(1,sum(c['operation']=='read' for c in slot.commands));self.assertEqual(1,sum(c['operation']=='release' for c in slot.commands))

    def test_lost_release_carrier_retains_issued_intent_without_release_or_capture_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);context=FrameCallbackContext(retain_trace=True)
            current=owner(context,root,'ios-'+'1'*32);current.capture('2'*32);slot=context.world(current.request_id)
            with patch.object(slot,'original',side_effect=OSError('Declared lost release carrier')),self.assertRaises(NativeUIError):current.release_once()
            state=current.store.read();rows=unpack(state['transcript'])
            self.assertEqual('release',rows[-1]['command']['operation']);self.assertIsNone(rows[-1]['receipt'])
            actual=current.release_once();self.assertEqual('inspect',actual['operation']);self.assertFalse(absent(actual))
            self.assertEqual(1,sum(c['operation']=='read' for c in slot.commands));self.assertEqual(1,sum(c['operation']=='release' for c in slot.commands))

    def test_same_byte_replaced_actual_png_inode_refuses_pending_original_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);_context,current,_frame,_raw,saved=self.pending(root)
            path=root/current.name;raw=path.read_bytes();inode=path.stat().st_ino;replacement=path.with_suffix('.replacement')
            replacement.write_bytes(raw);replacement.chmod(0o600);os.replace(replacement,path)
            self.assertEqual(raw,path.read_bytes());self.assertNotEqual(inode,path.stat().st_ino)
            with current.lock.held(),self.assertRaises(NativeUIError):self.archive(current,saved)

    def test_gpu_copy_metadata_or_unretired_source_is_not_callback_only_image_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);_context,current,_frame,_raw,saved=self.pending(root)
            for field,value in (('gpuPending',True),('gpuBufferBytes',262144),('metadataBytes',1),('retired',False),('callbacks',0)):
                bad=deepcopy(saved);rows=unpack(bad['transcript']);rows[-1]['receipt']['source'][field]=value;bad['transcript']=pack(rows)
                with self.subTest(field=field),current.lock.held(),self.assertRaises(NativeUIError):self.archive(current,bad)

    def test_changed_empty_preflight_cannot_grant_the_new_release_write_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);context,current,_frame,_raw,saved=self.pending(root)
            changed=deepcopy(saved);rows=unpack(changed['transcript']);rows[0]['receipt']['source'].update(present=True,metadataBytes=1)
            changed['transcript']=pack(rows);current.store.write(changed,saved);commands=deepcopy(context.world(current.request_id).commands)
            with self.assertRaises(NativeUIError):current.release_once()
            self.assertEqual(commands,context.world(current.request_id).commands)


if __name__=='__main__':unittest.main()
