"""Actual private reservation/reconstruction; product boundaries are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.tablet_web_app_owner import TabletWebAppOwner,input_scopes
from ios.self_tests.test_ios_tablet_web_sources import RUN,ROOT


class TabletAppOwnerTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');held=self.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='42',sessionId='existing-session',generation=1,targetFingerprint='c'*64)
        self.calls=[];source=SimpleNamespace(root=self.root,binding=self.binding,run=RUN,role='primary',fixture=ROOT,lock=self.lock,
            bound=lambda:True,epoch_ms=lambda:100000,monotonic=lambda:0.)
        self.runtime=SimpleNamespace(observer=SimpleNamespace(source=source),check=lambda:True,read_auxiliary=self.query)
    def query(self,kind,**kwargs):
        self.calls.append((kind,deepcopy(kwargs)))
        if kind=='widgets':return dict(observation=dict(tabletShown=False,scriptInventory=dict(inventoryVersion=2,complete=True,managers=[],pickers=[])))
        raise OSError('Modeled first actual native stage return is unavailable')
    def test_exact_reserved_input_is_owned_before_any_native_stage_and_unknown_stage_cannot_replay(self):
        owner=TabletWebAppOwner(self.runtime)
        with self.assertRaises(OSError):owner.prepare('b'*32)
        rebuilt=TabletWebAppOwner(self.runtime);generation=rebuilt.state['generations'][0]
        metadata=rebuilt.ownership(generation);self.assertEqual(metadata,generation['ownership']);self.assertTrue(generation['reserved'])
        self.assertEqual('failed',rebuilt.state['pending']['status']);self.assertEqual('stage-app-1',rebuilt.state['pending']['label'])
        self.assertEqual([metadata],input_scopes(self.root,self.binding,RUN));before=deepcopy(self.calls)
        with self.assertRaises(NativeUIError):rebuilt.prepare('b'*32)
        self.assertEqual(before,self.calls)
    def test_lost_host_owner_return_reconstructs_same_nonce_bytes_inode_without_reservation_replay(self):
        owner=TabletWebAppOwner(self.runtime);write=PrivateFeatureState.write;failed=[False]
        def lost(store,value,previous):
            result=write(store,value,previous)
            if store.path.name.startswith('tabletweb-app-files-') and not failed[0]:failed[0]=True;raise OSError('Actual private owner return lost')
            return result
        with patch.object(PrivateFeatureState,'write',lost),self.assertRaises(OSError):owner.prepare('b'*32)
        generation=owner.state['generations'][0];self.assertFalse(generation['reserved']);self.assertIsNotNone(generation['ownership'])
        path=self.root/generation['ownerFile'];original=path.read_bytes();stat=path.stat();metadata=deepcopy(generation['ownership'])
        rebuilt=TabletWebAppOwner(self.runtime)
        with self.assertRaises(OSError):rebuilt.prepare('b'*32)  # The first native stage now occurs once.
        self.assertEqual(original,path.read_bytes());self.assertEqual(stat,path.stat());self.assertEqual(metadata,rebuilt.state['generations'][0]['ownership'])
        self.assertEqual(1,len([kind for kind,_ in self.calls if kind=='files']))
    def test_a_foreign_host_owner_cannot_be_adopted_from_a_planned_filename(self):
        owner=TabletWebAppOwner(self.runtime);write=PrivateFeatureState.write
        def stop(store,value,previous):
            if store.path.name.startswith('tabletweb-app-files-'):raise OSError('Actual owner not written')
            return write(store,value,previous)
        with patch.object(PrivateFeatureState,'write',stop),self.assertRaises(OSError):owner.prepare('b'*32)
        generation=owner.state['generations'][0];changed=deepcopy(generation['ownership']);changed['ownerToken']='f'*64
        PrivateFeatureState(self.root/generation['ownerFile']).write(changed,None);before=deepcopy(self.calls)
        rebuilt=TabletWebAppOwner(self.runtime)
        with self.assertRaises(NativeUIError):rebuilt.prepare('b'*32)
        self.assertEqual(before,self.calls)


if __name__=='__main__':unittest.main()
