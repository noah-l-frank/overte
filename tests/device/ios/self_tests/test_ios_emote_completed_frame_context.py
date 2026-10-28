"""Shared Context host-source proof; no native GPU, compiler or device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame,absent
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.self_tests.emote_completed_frame_context_fixture import FrameCallbackContext
from self_tests.test_completed_frame_lease import BINDING,RUN
from self_tests.test_native_vulkan_world_frame import request


def query(operation,request_id,nonce):return dict(request(operation,nonce),requestId=request_id)
def owner(context,root,request_id):
    slot=context.world(request_id)
    def factory(intent,received):
        return NativeVulkanWorldFrame(slot.send,slot.original,slot.epoch,lambda:True,42,intent,receipt=received,
            monotonic=lambda:context.time,sleep=context.advance)
    return VulkanWorldFrameOwner(PrivateFeatureState(root/(request_id+'.json')),root,BINDING,RUN,'primary',0,
        request_id,factory,lambda:True,monotonic=lambda:context.time,sleep=context.advance)


class CompletedFrameContextTests(unittest.TestCase):
    def test_actual_callback_return_precedes_release_without_release_timer_or_wait(self):
        context=FrameCallbackContext();request_id='ios-'+'1'*32
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);current=owner(context,root,request_id)
            frame,raw=current.capture('2'*32);slot=context.world(request_id)
            self.assertIsNone(slot.callback());self.assertIsNone(slot.copy);self.assertFalse(slot.gpu_pending)
            start=context.time;proof=current.release()
            self.assertTrue(absent(proof));self.assertEqual(start,context.time)
            self.assertEqual(raw,current.archive());self.assertEqual(frame['source']['image']['bytes'],len(raw))
            self.assertEqual(1,sum(row['operation']=='release' for row in slot.commands))
            self.assertTrue(context.all_drained());self.assertIsNone(context.active)

    def test_retained_actual_trace_prevents_next_context_slot_until_its_reference_ends(self):
        context=FrameCallbackContext(retain_trace=True);first=context.world('ios-'+'1'*32)
        reader=first.reader();reader.perform(query('read',first.request_id,'2'))
        self.assertIsNotNone(first.callback());self.assertIsNone(first.copy);self.assertFalse(first.gpu_pending)
        released=reader.perform(query('release',first.request_id,'3'));saved=first.original()
        self.assertFalse(absent(released));self.assertEqual(1,released['source']['callbacks'])
        second=context.world('ios-'+'4'*32)
        with self.assertRaises(NativeUIError):second.reader().perform(query('read',second.request_id,'5'))
        self.assertIsNone(second.copy);self.assertIsNone(second.callback());self.assertIsNone(context.active)
        first.drop_retained_trace();self.assertIsNone(first.callback())
        self.assertEqual(saved,first.original())  # Original receipt is not rewritten.
        actual=reader.perform(query('inspect',first.request_id,'6'));self.assertTrue(absent(actual))
        third=context.world('ios-'+'7'*32)
        frame=third.reader().perform(query('read',third.request_id,'8'))
        self.assertEqual(context.instance,frame['instance']);self.assertEqual(third.request_id,context.active)

    def test_callback_death_without_fence_keeps_copy_and_global_context_closed(self):
        context=FrameCallbackContext();slot=context.world('ios-'+'1'*32);slot.no_fence=True
        with self.assertRaises(NativeUIError):slot.reader().perform(query('read',slot.request_id,'2'))
        slot.discard_callback_without_fence();self.assertIsNone(slot.callback());self.assertIsNotNone(slot.copy)
        reader=slot.reader();proof=reader.perform(query('release',slot.request_id,'3'));saved=slot.original()
        self.assertEqual(0,proof['source']['callbacks']);self.assertTrue(proof['source']['gpuPending'])
        self.assertGreater(proof['source']['gpuBufferBytes'],0);self.assertFalse(absent(proof))
        context.advance(5);self.assertEqual(saved,slot.original());self.assertFalse(context.all_drained())
        other=context.world('ios-'+'4'*32)
        with self.assertRaises(NativeUIError):other.reader().perform(query('read',other.request_id,'5'))
        self.assertIsNone(other.copy);self.assertIsNone(other.callback())

    def test_completed_original_and_active_slot_remain_until_actual_release(self):
        context=FrameCallbackContext();slot=context.world('ios-'+'1'*32)
        slot.send(query('read',slot.request_id,'2'));context.advance(.1)
        self.assertIsNone(slot.callback());self.assertTrue(context.all_drained())
        original=slot.original();context.advance(.2);self.assertEqual(original,slot.original())
        other=context.world('ios-'+'3'*32)
        with self.assertRaises(NativeUIError):other.reader().perform(query('read',other.request_id,'4'))
        self.assertEqual(slot.request_id,context.active)
        proof=slot.reader().perform(query('release',slot.request_id,'5'));self.assertTrue(absent(proof))

    def test_same_arm_keeps_original_frame_and_foreign_nonce_cannot_rearm_retired_generation(self):
        context=FrameCallbackContext();slot=context.world('ios-'+'1'*32);arm=query('read',slot.request_id,'2')
        slot.send(arm);context.advance(.1);frame=slot.original();sequence=context.sequence
        slot.send(arm);self.assertEqual(frame,slot.original());self.assertEqual(sequence,context.sequence)
        slot.send(query('read',slot.request_id,'3'));self.assertFalse(__import__('json').loads(slot.original())['available'])
        self.assertIsNone(slot.callback());self.assertIsNone(slot.copy)
        slot.reader().perform(query('release',slot.request_id,'4'))
        slot.send(arm);self.assertFalse(__import__('json').loads(slot.original())['available'])
        self.assertIsNone(context.active);self.assertIsNone(slot.callback());self.assertIsNone(slot.copy)

    def test_late_fence_callback_completion_is_not_an_original_png_or_fresh_frame(self):
        context=FrameCallbackContext();slot=context.world('ios-'+'1'*32);arm=query('read',slot.request_id,'2')
        slot.send(arm);context.advance(1.6)
        self.assertIsNone(slot.completed_original);self.assertIsNone(slot.callback());self.assertIsNone(slot.copy)
        slot.send(arm);self.assertFalse(__import__('json').loads(slot.original())['available'])
        self.assertIsNone(slot.completed_original)
        proof=slot.reader().perform(query('release',slot.request_id,'3'));self.assertTrue(absent(proof))

    def test_invalid_or_foreign_command_never_bears_a_callback_or_copy_generation(self):
        context=FrameCallbackContext();slot=context.world('ios-'+'1'*32)
        for bad in (dict(query('read',slot.request_id,'2'),schemaVersion=True),query('read','ios-'+'3'*32,'4')):
            with self.assertRaises(NativeUIError):slot.send(bad)
            self.assertIsNone(slot.callback());self.assertIsNone(slot.copy);self.assertIsNone(context.active)
        self.assertEqual([],slot.commands)

    def test_contexts_have_distinct_births_and_do_not_borrow_other_context_drain(self):
        first=FrameCallbackContext(retain_trace=True);second=FrameCallbackContext()
        a=first.world('ios-'+'1'*32);b=second.world('ios-'+'2'*32)
        fa=a.reader().perform(query('read',a.request_id,'3'));fb=b.reader().perform(query('read',b.request_id,'4'))
        self.assertNotEqual(fa['instance'],fb['instance']);self.assertIsNotNone(a.callback());self.assertIsNone(b.callback())
        self.assertFalse(first.all_drained());self.assertTrue(second.all_drained())
        b.reader().perform(query('release',b.request_id,'5'))
        self.assertIsNotNone(a.callback());self.assertEqual(a.request_id,first.active)

    def test_lost_original_return_keeps_once_only_host_owner_until_real_source_release(self):
        context=FrameCallbackContext();request_id='ios-'+'1'*32
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);current=owner(context,root,request_id);slot=context.world(request_id)
            actual_original=slot.original
            def lost_read_only():
                if slot.commands and slot.commands[-1]['operation']=='read':raise OSError('Declared lost read carrier return')
                return actual_original()
            with patch.object(slot,'original',side_effect=lost_read_only),self.assertRaises(NativeUIError):current.capture('2'*32)
            self.assertEqual(1,sum(row['operation']=='read' for row in slot.commands))
            context.advance(.1)
            proof=current.release();self.assertTrue(absent(proof));self.assertTrue(current.verify_owned_artifact())
            self.assertEqual(1,sum(row['operation']=='read' for row in slot.commands))
            self.assertEqual(1,sum(row['operation']=='release' for row in slot.commands))
            self.assertEqual(0,(root/current.name).stat().st_size)  # Ownership only; no PNG fact.


if __name__=='__main__':unittest.main()
