"""Real private input replays; synthetic native authority, no device result."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_original_clone as original_probe
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_script_history import pack
from overte_phone_script_lock import PhoneScriptSourceLock
from overte_phone_snapshots_evidence import SnapshotsOriginals
from overte_phone_snapshots_feature import PhoneSnapshotsFeature

RUN,BINDING=original_probe.RUN,original_probe.BINDING


class SnapshotInputReplayGuardTests(unittest.TestCase):
    @contextmanager
    def fixture(self):
        # Reuse the existing private-original filesystem fixture. This tests
        # storage authority only; the records deliberately contain no effects.
        original=original_probe.SnapshotOriginalCloneTests('runTest');original.setUp()
        try:
            f=object.__new__(PhoneSnapshotsFeature)
            control=SimpleNamespace(allowed=True,callback=None,calls=[])
            f.root=original.root;f.run=RUN;f.role='primary'
            f.binding=deepcopy(BINDING);f.fixture_url='https://fixture.invalid/snapshots'
            f.config=dict(controlledHostFixture=True)
            f.adapter=SimpleNamespace(_existing_input_scope=dict(controlledHostSession=True))
            f._system_scope=None;f._scope_ready=True;f.monotonic=time.monotonic
            f.lock=PhoneScriptSourceLock(f.root/'phone-script-source.lock')
            f.store=PrivateFeatureState(f.root/'phone-snapshots-feature.json')
            f.state=dict(inputs=[],inputSequence=0,current=None,nested=dict(original=[1,2]))
            header=dict(snapshotsFeatureVersion=1,runId=f.run,fixtureUrl=f.fixture_url,
                binding=deepcopy(f.binding),configuration=deepcopy(f.config),payload=pack([f.state]))
            f.store.write(header,None);f.previous=deepcopy(header)
            def native():
                control.calls.append(True)
                if control.callback is not None:control.callback()
                need(control.allowed);return True
            f.guard=native
            owner=SnapshotsOriginals(f.root,f.binding,f.run,'primary',f.bound,lambda *_:True,kind='snapshots-input')
            frames=[dict(controlledInput=index,nested=dict(original=[index])) for index in range(1,4)]
            references=[];values=[]
            with f.lock.held():
                for index,frame in enumerate(frames,1):
                    value=owner.write(index,frame);values.append(owner.expand(value))
                    references=owner.append(references,value)
                f.state.update(inputs=references,inputSequence=len(frames))
                header=dict(header,payload=pack([f.state]));f.store.write(header,f.previous);f.previous=deepcopy(header)
            control.calls.clear()
            yield SimpleNamespace(feature=f,control=control,owner=owner,frames=frames,
                paths=[owner.path(value) for value in values])
        finally:self.assertTrue(original.doCleanups(),'Owned input fixture cleanup failed')

    @staticmethod
    def replace(path):
        replacement=path.with_name(path.name+'.controlled-replacement')
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600)
        os.replace(replacement,path)

    def test_every_call_reopens_actual_bodies_and_returns_fresh_graphs(self):
        with self.fixture() as fixture:
            f=fixture.feature;opened=[];real_open=os.open;read=SnapshotsOriginals.read;reads=[]
            def actual_open(path,flags,*args,**kwargs):
                descriptor=real_open(path,flags,*args,**kwargs)
                if Path(path) in fixture.paths:
                    info=os.fstat(descriptor);opened.append((Path(path),info.st_dev,info.st_ino))
                return descriptor
            def actual_read(owner,value):
                result=read(owner,value);reads.append(value['index']);return result
            # Unsaved in-progress RAM is legitimate; it must be pinned as-is,
            # rather than replaced by or compared with the durable payload.
            f.state['current']=dict(controlledUncommitted=[1])
            with f.lock.held(),patch.object(os,'open',actual_open),patch.object(SnapshotsOriginals,'read',actual_read):
                first=f.input_originals();first[0]['nested']['original'].append('caller-only')
                second=f.input_originals()
            self.assertEqual(fixture.frames,second)
            self.assertEqual([1,2,3,1,2,3],reads)
            self.assertEqual(fixture.paths*2,[row[0] for row in opened])
            self.assertTrue(all((path.stat().st_dev,path.stat().st_ino)==(device,inode) for path,device,inode in opened))
            self.assertEqual(dict(controlledUncommitted=[1]),f.state['current'])

    def test_mid_replay_owner_replacement_and_old_file_loss_are_rejected(self):
        for mutation in ('foreign-owner','same-owner-inode','missing-input','replaced-input'):
            with self.subTest(mutation=mutation),self.fixture() as fixture:
                f=fixture.feature;read=SnapshotsOriginals.read;changed=[]
                original_inode=f.store.path.stat().st_ino
                def actual_read(owner,value):
                    result=read(owner,value)
                    if not changed:
                        changed.append(True)
                        if mutation=='foreign-owner':f.store.write(dict(f.previous,runId='f'*32),f.previous)
                        elif mutation=='same-owner-inode':f.store.write(deepcopy(f.previous),f.previous)
                        elif mutation=='missing-input':fixture.paths[-1].unlink()
                        else:self.replace(fixture.paths[-1])
                    return result
                with self.assertRaises((NativeUIError,FileNotFoundError)),f.lock.held(),patch.object(SnapshotsOriginals,'read',actual_read):
                    f.input_originals()
                self.assertEqual([True],changed)
                if mutation=='same-owner-inode':
                    self.assertEqual(f.previous,f.store.read())
                    self.assertNotEqual(original_inode,f.store.path.stat().st_ino)

    def test_final_native_callback_cannot_change_files_ram_or_reuse_failed_authority(self):
        for mutation in ('missing-input','replaced-input','input-references','ram-graph'):
            with self.subTest(mutation=mutation),self.fixture() as fixture:
                f=fixture.feature;restore=SnapshotsOriginals.restore;replayed=[];changed=[]
                def actual_restore(owner,*args,**kwargs):
                    result=restore(owner,*args,**kwargs);replayed.append(True);return result
                def late():
                    if not replayed or changed:return
                    changed.append(True)
                    if mutation=='missing-input':fixture.paths[0].unlink()
                    elif mutation=='replaced-input':self.replace(fixture.paths[0])
                    elif mutation=='input-references':f.state['inputs'][0]['count']-=1
                    else:f.state['nested']['original'].append('foreign')
                fixture.control.callback=late
                with self.assertRaises((NativeUIError,FileNotFoundError)),f.lock.held(),patch.object(SnapshotsOriginals,'restore',actual_restore):
                    f.input_originals()
                self.assertEqual([True],replayed);self.assertEqual([True],changed)
        with self.fixture() as fixture:
            f=fixture.feature;restore=SnapshotsOriginals.restore;replayed=[]
            def actual_restore(owner,*args,**kwargs):
                result=restore(owner,*args,**kwargs);replayed.append(True);return result
            fixture.control.callback=lambda:setattr(fixture.control,'allowed',False) if replayed else None
            with self.assertRaises(NativeUIError),f.lock.held(),patch.object(SnapshotsOriginals,'restore',actual_restore):
                f.input_originals()
            self.assertEqual([True],replayed)
            fixture.control.callback=None
            with self.assertRaises(NativeUIError),f.lock.held():f.input_originals()
            fixture.control.allowed=True;read=SnapshotsOriginals.read;reads=[]
            def actual_read(owner,value):
                result=read(owner,value);reads.append(value['index']);return result
            with f.lock.held(),patch.object(SnapshotsOriginals,'read',actual_read):
                self.assertEqual(fixture.frames,f.input_originals())
            self.assertEqual([1,2,3],reads)


if __name__=='__main__':unittest.main()
