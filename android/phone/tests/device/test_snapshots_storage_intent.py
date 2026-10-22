"""Actual private Snapshot archival and loss recovery; native signals are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_role as source
from adapters.normal_ui import NativeUIError
from adapters.native_feature_observation import need
from overte_phone_script_history import unpack


class SnapshotStorageIntentTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='snapshot-storage-intent-');self.addCleanup(temporary.cleanup)
        self.b=source.SnapshotRolesBoundary(temporary.name)
        self.owned=True;self.guards=[]
        def bound():self.guards.append(self.owned);need(self.owned);return True
        self.b.feature.bound=bound
    def track(self,role):
        changes=[];writes=[];intent=role.storage_intent;write=role.store.write
        def stored(value,previous):
            writes.append(deepcopy(unpack(value['payload'])[0]));return write(value,previous)
        def changed(kind,value):
            before=len(self.guards);start=len(writes);result=intent(kind,value)
            changes.append(dict(kind=kind,phase=value['phase'],guards=len(self.guards)-before,writes=deepcopy(writes[start:])))
            return result
        role.store.write=stored;role.originals.intent=changed
        return changes
    def test_read_callbacks_keep_manifest_target_commit_and_one_atomic_saved_receipt(self):
        with self.b.role() as role:
            changes=self.track(role);observed=role.read(0)
            self.assertEqual(1,observed['sequence'])
            self.assertEqual([('original','planned',0),('original','opened',0),('original','saved',0),('manifest','planned',1),('manifest','saved',0)],
                [(row['kind'],row['phase'],row['guards'])for row in changes])
            saved=next(row for row in changes if row['kind']=='original'and row['phase']=='saved')
            self.assertEqual(1,len(saved['writes']));pending=saved['writes'][0]['pending']
            self.assertEqual('saved',pending['original']['phase']);self.assertIsNone(pending['frame']);self.assertEqual({},pending['work'])
            self.assertEqual(role.frames[-1],role.originals.read(role.originals.expand(role.originals.manifest(role.state['manifests'][-1])[-1])))
    def test_outside_guarded_read_every_callback_still_checks_current_target(self):
        with self.b.role() as role:
            role.state.update(phase='reading',pending=dict(original=None,manifest=None,image=None,binaries=[],retirement=None,frame=None,work={}))
            role.save();changes=self.track(role)
            role.finish_archive(dict(diagnostic=True,image=None,binaries=[],retirement=None))
            self.assertEqual(5,len(changes));self.assertTrue(all(row['guards']>=2 for row in changes))
            self.owned=False;header=deepcopy(role.store.read())
            with self.assertRaises(NativeUIError):role.storage_intent('manifest',dict(phase='planned'))
            self.assertEqual(header,role.store.read())
    def test_unknown_kind_repeated_or_ignored_stage_cannot_write_a_new_receipt(self):
        with self.b.role() as role:
            role.state.update(phase='reading',pending=dict(original=dict(phase='planned'),manifest=dict(phase='planned'),image=None,binaries=[],retirement=None,frame=None,work={}))
            role.save();header=deepcopy(role.store.read())
            for kind,value in [('unknown',dict(phase='planned')),('original',dict(phase='planned')),('original',dict(phase='saved')),('manifest',dict(phase='planned'))]:
                with self.subTest(kind=kind,value=value),self.assertRaises(NativeUIError):role.storage_intent(kind,value)
                self.assertEqual(header,role.store.read())
    def recovery(self,fault):
        b=self.b;triggered=[];saved_path=[]
        with b.role() as role:
            write=role.store.write
            def failing(value,previous):
                state=unpack(value['payload'])[0];pending=state['pending']
                if not triggered and pending is not None and pending['original']is not None and pending['original']['phase']=='saved':
                    triggered.append(True);saved_path.append(role.originals.path(pending['original']))
                    if fault=='after':write(value,previous)
                    if fault=='ignored':return None
                    raise NativeUIError('Explicit saved-original commit reply loss')
                return write(value,previous)
            role.store.write=failing
            with self.assertRaises(NativeUIError):role.read(0)
            self.assertTrue(triggered);self.assertFalse(role._host_publication)
            durable=unpack(role.store.read()['payload'])[0];pending=durable['pending']
            if fault=='after':
                self.assertEqual('saved',pending['original']['phase']);self.assertIsNone(pending['frame']);self.assertEqual({},pending['work'])
            else:
                self.assertEqual('opened',pending['original']['phase']);self.assertIsNotNone(pending['frame']);self.assertTrue(pending['work'])
            raw=saved_path[0].read_bytes();inode=saved_path[0].stat().st_ino;calls=len(b.vm.snapshot.calls)
        with b.role() as resumed:
            resumed.recover();self.assertEqual('ready',resumed.state['phase']);self.assertEqual(1,resumed.state['sequence'])
            self.assertEqual(calls,len(b.vm.snapshot.calls));self.assertEqual(raw,saved_path[0].read_bytes());self.assertEqual(inode,saved_path[0].stat().st_ino)
            self.assertEqual(1,resumed.frames[-1]['state']['files'])
        return saved_path[0]
    def test_fault_before_atomic_save_retains_original_work_for_exact_recovery(self):self.recovery('before')
    def test_lost_reply_after_atomic_save_recovers_from_only_actual_saved_original(self):self.recovery('after')
    def test_ignored_atomic_save_is_red_and_recovers_original_opened_receipt(self):self.recovery('ignored')
    def test_mismatched_original_inode_stays_red_during_actual_resume(self):
        b=self.b
        with b.role() as role:
            intent=role.storage_intent;hit=[]
            def failed(kind,value):
                result=intent(kind,value)
                if kind=='original'and value['phase']=='opened'and not hit:hit.append(True);raise NativeUIError('Explicit interrupted original')
                return result
            role.originals.intent=failed
            with self.assertRaises(NativeUIError):role.read(0)
            self.assertTrue(hit);role.state['pending']['original']['file']['inode']+=1;role.save();foreign=deepcopy(role.store.read());calls=len(b.vm.snapshot.calls)
        with b.role() as resumed:
            with self.assertRaises(NativeUIError):resumed.recover()
            self.assertEqual(foreign,resumed.store.read());self.assertEqual(calls,len(b.vm.snapshot.calls));self.assertEqual(0,resumed.state['sequence'])
    def test_target_change_after_actual_manifest_still_rejects_the_public_return(self):
        with self.b.role() as role:
            append=role.originals.append;changed=[]
            def late(*args,**kwargs):
                value=append(*args,**kwargs);changed.append(True);self.owned=False;return value
            role.originals.append=late
            with self.assertRaises(NativeUIError):role.read(0)
            self.assertTrue(changed);self.assertFalse(role._host_publication);self.assertFalse(self.guards[-1])
            # The immutable original and manifest existed before the target
            # changed; neither one authorizes a successful current return.
            self.assertTrue(role.state['manifests'])
            with self.assertRaises(NativeUIError):role.save()


if __name__=='__main__':unittest.main()
