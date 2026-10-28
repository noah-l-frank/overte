"""Original actual host-file adoption and fencing; no SDK/device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile,unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import lifecycle_session_owners
from ios.adapters.touch_lease import TouchLeasePending
from ios.self_tests.lifecycle_touch_resources_fixture import Fixture


def files(root):
    return {p.name:(p.stat().st_dev,p.stat().st_ino,p.stat().st_mode,p.stat().st_size,p.stat().st_mtime_ns,p.stat().st_ctime_ns,p.read_bytes())
        for p in root.iterdir() if p.is_file()}


class LifecycleTouchResourceWALTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='lifecycle-touch-resource-wal-'));self.root.chmod(0o700)
        print('retained resource WAL root',self.root,flush=True);self.f=Fixture(self.root);await self.f.begin()
    async def asyncTearDown(self):await self.f.close()
    async def test_readonly_history_rereads_exact_original_without_acquiring_or_releasing_worker(self):
        f=self.f;value=f.owner.capture();before=files(self.root);reports=deepcopy(f.hid.reports);starts=deepcopy(f.display.starts)
        restored=f.restore();actual=restored.files.read(restored.files.expand(restored.state['frames'][-1]))
        self.assertEqual(value,actual);self.assertEqual(before,files(self.root));self.assertEqual(reports,f.hid.reports);self.assertEqual(starts,f.display.starts)
    async def test_saved_original_lost_parent_append_recovers_exact_bytes_without_capture_query_or_input(self):
        f=self.f;intent=f.owner.files.intent
        def lost(kind,ref):
            result=intent(kind,ref)
            if ref['phase']=='saved':raise RuntimeError('Declared saved append lost')
            return result
        f.owner.files.intent=lost
        with self.assertRaises(RuntimeError):f.owner.capture()
        before=files(self.root);reports=deepcopy(f.hid.reports);restored=f.restore()
        with patch.object(restored,'make_lease',side_effect=AssertionError('no factory replay')):
            value=restored.recover_capture()
        self.assertEqual(1,value['iosLifecycleTouchResourceCaptureVersion']);self.assertIsNone(restored.state['pending'])
        for name,entry in before.items():
            if '-frame-' in name:self.assertEqual(entry,files(self.root)[name])
        self.assertEqual(reports,f.hid.reports);self.assertEqual(1,len(f.display.starts))
    async def test_opened_original_remains_owned_and_cannot_be_recovered_as_saved_or_recaptured(self):
        f=self.f;intent=f.owner.files.intent
        def lost(kind,ref):
            result=intent(kind,ref)
            if ref['phase']=='opened':raise RuntimeError('Declared opened prefix')
            return result
        f.owner.files.intent=lost
        with self.assertRaises(RuntimeError):f.owner.capture()
        before=files(self.root);restored=f.restore()
        with self.assertRaises(NativeUIError):restored.recover_capture()
        with self.assertRaises(NativeUIError):restored.capture()
        self.assertEqual(before,files(self.root));self.assertEqual([0xC2],f.hid.reports)
    async def test_same_bytes_on_replaced_inode_or_missing_actual_frame_cannot_restore_valid_history(self):
        f=self.f;f.owner.capture();ref=f.owner.files.expand(f.owner.state['frames'][-1]);path=f.owner.files.path(ref);raw=path.read_bytes()
        path.rename(self.root/'retained-original-frame');path.write_bytes(raw);path.chmod(0o600)
        with self.assertRaises(NativeUIError):f.restore()
        self.assertEqual([0xC2],f.hid.reports)
    async def test_foreground_loss_blocks_new_capture_but_cannot_prevent_once_only_original_up_cleanup(self):
        f=self.f;f.owner.capture();f.current=False
        with self.assertRaises(NativeUIError):f.owner.capture()
        await f.owner.release_worker();self.assertEqual([0xC2,0x02],f.hid.reports)
        f.current=True;last=f.owner.capture();self.assertTrue(last['worker']['contextExitReturned'])
        self.assertFalse(last['source']['wholeLifecycleRetirementAvailable'])
    async def test_owner_and_orphan_resource_original_names_fence_ordinary_session_without_sdk_calls(self):
        adapter=SimpleNamespace(state_path=lambda _:self.root/'installed-session.json')
        with self.assertRaises(NativeUIError):lifecycle_session_owners.ensure_released(adapter,'private')
        # A separate private root containing only a lookalike resource frame
        # also fences ordinary SDK entry; missing owner metadata cannot erase it.
        orphan=Path(tempfile.mkdtemp(prefix='lifecycle-touch-resource-orphan-'));orphan.chmod(0o700)
        (orphan/'lifecycle-touch-resource-frame-unowned.json').write_text('{}')
        adapter=SimpleNamespace(state_path=lambda _:orphan/'installed-session.json')
        with self.assertRaises(NativeUIError):lifecycle_session_owners.ensure_released(adapter,'private')
        self.assertEqual([0xC2],self.f.hid.reports);self.assertEqual(1,len(self.f.display.starts))

    async def cleanup_after_lost_resource_CAS(self,point):
        f=self.f;write=f.owner.store.write;committed=[];original_worker=f.lease.worker
        def lost(value,previous):
            answer=write(value,previous);state=value['state'];pending=state['pending']
            match=(pending is not None and pending['phase']=='planned') if point=='planned' else bool(state['frames']) and pending is None
            if match and not committed:
                committed.append(deepcopy(value));raise OSError('Actual successful resource-owner CAS return lost')
            return answer
        with patch.object(f.owner.store,'write',side_effect=lost),self.assertRaises(OSError):f.owner.capture()
        self.assertEqual(1,len(committed));self.assertEqual(committed[0],f.owner.store.read())
        self.assertNotEqual(f.owner.previous,f.owner.store.read());self.assertEqual([0xC2],f.hid.reports)
        before=files(self.root);resource_name=f.owner.store.path.name
        # The unrelated resource WAL stays unknown and untouched. Original
        # TouchLease still verifies its own worker, intent and input journal.
        with patch.object(f.owner.store,'write',side_effect=AssertionError('Cleanup acknowledged or repaired resource WAL')):
            result=await f.owner.release_worker()
        after=files(self.root);self.assertEqual(before[resource_name],after[resource_name])
        for name,entry in before.items():
            if '-frame-' in name:self.assertEqual(entry,after[name])
        self.assertTrue(result['contextExitReturned']);self.assertIs(original_worker,f.lease.worker)
        self.assertTrue(original_worker.done());self.assertEqual([0xC2,0x02],f.hid.reports)
        self.assertEqual(1,len(f.display.starts));self.assertEqual(f.display.starts,f.display.stops)
        self.assertTrue(all(fd.fileno()==-1 for fd in f.receiver.sockets))
        with self.assertRaises(NativeUIError):f.owner.capture()
        restored=f.restore()
        with self.assertRaises(TouchLeasePending):await restored.release_worker()
        with self.assertRaises(NativeUIError):restored.make_lease(f.lease_store,f.rsd,'fd00::1',check=lambda:True)
        self.assertEqual(before[resource_name],files(self.root)[resource_name])
        self.assertEqual([0xC2,0x02],f.hid.reports);self.assertEqual(1,len(f.display.stops))

    async def test_successful_planned_capture_CAS_lost_return_cannot_block_original_up(self):
        await self.cleanup_after_lost_resource_CAS('planned')

    async def test_successful_final_append_CAS_lost_return_cannot_block_original_up(self):
        await self.cleanup_after_lost_resource_CAS('append')
