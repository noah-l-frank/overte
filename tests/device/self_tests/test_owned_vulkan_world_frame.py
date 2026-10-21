"""Durable original frame/file ownership and reconstructed cleanup boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from self_tests.test_native_vulkan_world_frame import World
from self_tests.test_completed_frame_lease import BINDING,RUN

REQUEST='ios-'+'7'*32
TICKET='8'*32


def owner(b,store,root,*,binding=BINDING,role='primary'):
    def factory(intent,received):
        return NativeVulkanWorldFrame(b.send,b.original,b.epoch,lambda:b.okay,42,intent,receipt=received,
                                     monotonic=lambda:b.clock,sleep=b.sleep)
    return VulkanWorldFrameOwner(store,root,binding,RUN,role,0,REQUEST,factory,lambda:b.okay,
                                 monotonic=lambda:b.clock,sleep=b.sleep)


class OwnerTests(unittest.TestCase):
    def test_abandoned_empty_artifact_can_verify_only_inode_ownership_without_native_or_png_claim(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);store=PrivateFeatureState(root/'owner.json');b=World();current=owner(b,store,root);send=b.send
            def lost(query):
                send(query)
                if query['operation']=='read':raise OSError('Synthetic lost native capture return')
            b.send=lost
            with self.assertRaises(NativeUIError):current.capture(TICKET)
            b.send=send;current.release();before=len(b.commands)
            self.assertTrue(current.verify_owned_artifact());self.assertEqual(before,len(b.commands))
            with self.assertRaises(NativeUIError):current.archive()
            (root/'foreign-link').hardlink_to(root/current.name)
            with self.assertRaises(NativeUIError):current.verify_owned_artifact()
            self.assertEqual(before,len(b.commands))

    def test_capture_retains_original_file_and_chunk_summaries_across_host_reconstruction(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);store=PrivateFeatureState(root/'owner.json');b=World();current=owner(b,store,root)
            capture,raw=current.capture(TICKET);self.assertEqual(b.png,raw);self.assertEqual(raw,(root/current.name).read_bytes())
            events=unpack(store.read()['transcript']);self.assertEqual('inspect',events[0]['command']['operation'])
            self.assertEqual(capture,store.read()['frame']);self.assertEqual('captured',store.read()['phase'])
            chunks=[row['receipt'] for row in events if row['command']['operation']=='read-bytes']
            self.assertGreater(len(chunks),1);self.assertTrue(all('data' not in row['packet']['source'] for row in chunks))
            self.assertEqual(raw,owner(b,store,root).archive());proof=owner(b,store,root).release()
            self.assertEqual(0,proof['source']['callbacks']);self.assertEqual(0,proof['source']['pngBytes'])
            self.assertEqual(raw,owner(b,store,root).archive());self.assertTrue((root/current.name).exists())
            with self.assertRaises(NativeUIError):owner(b,store,root).capture(TICKET)
            self.assertEqual(1,sum(c['operation']=='read' for c in b.commands))
            self.assertTrue(owner(b,store,root).remove_image());self.assertFalse((root/current.name).exists())
            self.assertIsNotNone(store.read());self.assertTrue(owner(b,store,root).remove_image())

    def test_lost_frame_or_chunk_cannot_be_retried_by_reconstructing_owner(self):
        for phase in ('frame','chunk'):
            with self.subTest(phase=phase),tempfile.TemporaryDirectory() as root:
                root=Path(root);store=PrivateFeatureState(root/'owner.json');b=World();original=b.send
                def lost(query):
                    original(query)
                    if query['operation']==('read' if phase=='frame' else 'read-bytes'):raise OSError('Synthetic lost source delivery')
                b.send=lost
                with self.assertRaises(NativeUIError):owner(b,store,root).capture(TICKET)
                with self.assertRaises(NativeUIError):owner(b,store,root).capture(TICKET)
                self.assertEqual(1,sum(c['operation']=='read' for c in b.commands))
                self.assertIsNone(unpack(store.read()['transcript'])[-1]['receipt'])
                b.send=original;b.sleep(.2);self.assertTrue(owner(b,store,root).remove_image())

    def test_unknown_gpu_work_or_context_replacement_cannot_release_old_ownership(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);store=PrivateFeatureState(root/'owner.json');b=World();b.no_fence=True
            with self.assertRaises(NativeUIError):owner(b,store,root).capture(TICKET)
            before=deepcopy(store.read())
            # Synthetic replacement Context has no record of the old copy. Its
            # empty counters must not satisfy the pinned old source's cleanup.
            b.no_fence=False;b.request=None;b.held=b.gpu_pending=b.metadata=False;b.sequence=0
            b.fault=lambda value:value.update(instance='e'*32)
            with self.assertRaises(NativeUIError):owner(b,store,root).release()
            self.assertNotEqual('released',store.read()['phase']);self.assertIsNone(store.read()['absence'])
            previous=unpack(before['transcript']);current=unpack(store.read()['transcript'])
            self.assertEqual(previous,current[:len(previous)])
            self.assertIsNone(unpack(store.read()['transcript'])[-1]['receipt'])

    def test_lost_release_response_is_only_inspected_and_never_resubmitted(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);store=PrivateFeatureState(root/'owner.json');b=World();owner(b,store,root).capture(TICKET)
            original=b.send
            def lost(query):
                original(query)
                if query['operation']=='release':raise OSError('Synthetic lost release receipt')
            b.send=lost
            with self.assertRaises(NativeUIError):owner(b,store,root).release()
            b.send=original;b.sleep(.2);proof=owner(b,store,root).release()
            self.assertEqual(0,proof['source']['callbacks']);self.assertEqual(1,sum(c['operation']=='release' for c in b.commands))

    def test_changed_original_chunk_header_digest_cannot_authorize_archived_pixels(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);store=PrivateFeatureState(root/'owner.json');b=World();owner(b,store,root).capture(TICKET)
            before=store.read();changed=deepcopy(before);events=unpack(changed['transcript'])
            chunk=next(row for row in events if row['command']['operation']=='read-bytes')
            chunk['receipt']['originalSha256']='0'*64;changed['transcript']=pack(events);store.write(changed,before)
            with self.assertRaises(NativeUIError):owner(b,store,root).archive()

    def test_replaced_linked_or_changed_image_cannot_be_archived_or_removed_as_owned(self):
        for fault in ('replaced','linked','bytes'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as root:
                root=Path(root);store=PrivateFeatureState(root/'owner.json');b=World();current=owner(b,store,root);current.capture(TICKET)
                path=root/current.name
                if fault=='replaced':path.rename(root/'original.png');path.write_bytes(b'foreign');path.chmod(0o600)
                elif fault=='linked':(root/'other.png').hardlink_to(path)
                else:path.write_bytes(b'changed')
                with self.assertRaises(NativeUIError):owner(b,store,root).archive()
                if fault!='bytes':
                    with self.assertRaises(NativeUIError):owner(b,store,root).remove_image()
                    self.assertTrue(path.exists())
                else:self.assertTrue(owner(b,store,root).remove_image())

    def test_foreign_candidate_role_or_owner_cas_change_is_not_adopted(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);store=PrivateFeatureState(root/'owner.json');b=World();owner(b,store,root).capture(TICKET)
            previous=deepcopy(store.read());calls=len(b.commands)
            for options in (dict(role='actor'),dict(binding=BINDING|{'artifactSha256':'f'*64}),dict(binding=BINDING|{'processIdentity':'43'})):
                with self.assertRaises(NativeUIError):owner(b,store,root,**options).release()
            self.assertEqual(previous,store.read());self.assertEqual(calls,len(b.commands))

    def test_failed_intent_or_receipt_persistence_never_returns_a_successful_image(self):
        class Failing(PrivateFeatureState):
            def __init__(self,path,at):super().__init__(path);self.at=at;self.count=0
            def write(self,*args):
                self.count+=1
                if self.count==self.at:raise OSError('Synthetic persistence failure')
                return super().write(*args)
        for at in (1,2,3,4,5,6):
            with self.subTest(at=at),tempfile.TemporaryDirectory() as root:
                root=Path(root);store=Failing(root/'owner.json',at);b=World()
                with self.assertRaises((NativeUIError,OSError)):owner(b,store,root).capture(TICKET)
                self.assertLessEqual(sum(c['operation']=='read' for c in b.commands),1)


if __name__=='__main__':unittest.main()
