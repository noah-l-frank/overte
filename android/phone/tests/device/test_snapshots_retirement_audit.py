"""Independent journal-retirement counterprobes using actual private files.

Only the native preflight boundary is unavailable. These tests exercise partial
ownership, real provider retirement and real actor exit; they prove host recovery,
not a successful product Snapshot or a device run.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_snapshots_feature as source
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from fixture.messages_mixer import start_identity
from overte_phone_script_history import pack,unpack
from overte_phone_snapshots_retirement import PhoneSnapshotsRetirement,completed_archive,NAMES


class SnapshotsRetirementAuditTests(unittest.TestCase):
    setUp=source.SnapshotsFeatureTests.setUp
    feature=source.SnapshotsFeatureTests.feature
    failed_preflight=source.SnapshotsFeatureTests.failed_preflight
    call=source.SnapshotsFeatureTests.call

    def closed_owner(self):
        f=self.failed_preflight();self.client.activate('cleanup');f.cleanup(self.call());self.client.retire()
        child=subprocess.Popen([sys.executable,'-c','pass'])
        process=dict(pid=child.pid,start=start_identity(child.pid))
        self.assertIsNotNone(process['start']);self.assertEqual(0,child.wait(timeout=5))
        with f.lock.held():
            proof=f.partial_restored();closure=f.phase.status()
            actor=dict(process=process,phase='retired',pending=None,last=None,dropped=[],quiet=None,closure=closure,partialClosure=proof)
            header=dict(snapshotsActorVersion=1,runId=f.run,binding=f.binding,payload=pack([actor]))
            PrivateFeatureState(f.store.path.with_name('phone-snapshots-actor-lifecycle.json')).write(header,None)
        return f

    def test_interrupted_actual_child_unlink_resumes_from_original_archive(self):
        f=self.closed_owner();discard=PrivateFeatureState.discard;removed=[]
        def interrupt(store,expected):
            discard(store,expected)
            if store.path.name=='phone-snapshots-actor-lifecycle.json':
                removed.append(store.path);raise RuntimeError('Explicit interruption after actual child unlink')
        with patch.object(PrivateFeatureState,'discard',interrupt),self.assertRaises(NativeUIError):f.finalize()
        self.assertEqual(1,len(removed));self.assertFalse(removed[0].exists())
        self.assertIsNotNone(f.store.read())
        self.assertIsNotNone(PrivateFeatureState(f.store.path.with_name('phone-snapshots-retirement.json')).read())
        archive=completed_archive(f.root,f.binding,f.run,lambda:True)
        self.assertIsNotNone(archive['controls']['phone-snapshots-actor-lifecycle.json'])
        self.assertEqual({'performed':True},self.feature().finalize())
        self.assertTrue(all(PrivateFeatureState(f.store.path.with_name(name)).read() is None for name in NAMES))
        self.assertEqual(archive,completed_archive(f.root,f.binding,f.run,lambda:True))

    def test_completed_archive_cannot_hide_new_foreign_child_journal(self):
        f=self.closed_owner();f.finalize()
        store=PrivateFeatureState(f.store.path.with_name('phone-snapshots-primary-originals.json'))
        foreign=dict(runId='foreign',retired=False);store.write(foreign,None)
        with self.assertRaises(NativeUIError):self.feature().finalize()
        self.assertEqual(foreign,store.read())

    def test_actual_archive_byte_change_is_detected_on_repeated_finalization(self):
        f=self.closed_owner();f.finalize()
        paths=list(f.root.glob('emote-frame-snapshots-retirement-*.json'));self.assertEqual(1,len(paths))
        path=paths[0];original=path.read_bytes();path.chmod(0o600)
        with path.open('r+b') as stream:stream.seek(len(original)-1);stream.write(b' ')
        path.chmod(0o400)
        with self.assertRaises(NativeUIError):self.feature().finalize()
        self.assertNotEqual(original,path.read_bytes())

    def test_pending_owner_live_provider_and_active_closure_are_rejected(self):
        f=self.closed_owner()
        with f.lock.held():
            proof=f.partial_restored();closure=f.phase.status()
            archive=dict(owner=deepcopy(f.previous),controls={name:PrivateFeatureState(f.store.path.with_name(name)).read() for name in NAMES},proof=proof,closure=closure)
            self.assertIs(archive,PhoneSnapshotsRetirement(f).validate_archive(archive))
            for fault in ('current','handoff','lease','provider','closure'):
                changed=deepcopy(archive)
                if fault in ('current','handoff','lease'):
                    owner=unpack(changed['owner']['payload'])[0]
                    if fault=='lease':owner['leases']['settings']=True
                    else:owner[fault]=dict(pending=True)
                    changed['owner']['payload']=pack([owner])
                    changed['controls']['phone-snapshots-feature.json']=deepcopy(changed['owner'])
                    changed['proof']['owner']=deepcopy(changed['owner'])
                elif fault=='provider':changed['proof']['provider']['active']=True
                else:changed['closure']['active']=True
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):PhoneSnapshotsRetirement(f).validate_archive(changed)


if __name__=='__main__':unittest.main()
