"""Exact private Actor journal migrations never infer a Primary observation.

These are actual private-file/CAS host checks. The current binding guard is an
explicit host boundary; no native, Android or public journey result is claimed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.witness import Client
from fixture.messages_mixer import start_identity
from overte_phone_script_history import pack,unpack
from overte_phone_script_lock import PhoneScriptSourceLock
from overte_phone_snapshots_actor import PhoneSnapshotsActor,actor_fields,validate_primary_cue

BINDING=dict(sourceRevision='1'*40,artifactSha256='2'*64,processIdentity='31:123',sessionId='own-session',generation=4,targetFingerprint='3'*64)
RUN='b'*32


class SnapshotActorScheduleMigrationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.queries=[]
        def bound():self.queries.append('binding');return True
        self.f=SimpleNamespace(root=self.root,run=RUN,role='actor',binding=deepcopy(BINDING),bound=bound,
            phase=SimpleNamespace(client=Client('https://owned.invalid:443/feature-fixture/v1','a'*64)),
            store=PrivateFeatureState(self.root/'phone-snapshots-feature.json'),state=dict(hostProcess=dict(pid=1,start='foreign-host')),
            lock=PhoneScriptSourceLock(self.root/'phone-script-sources.lock'))
        self.actor=PhoneSnapshotsActor(self.f)
    def legacy(self,version):
        state=dict(process=dict(pid=os.getpid(),start=start_identity(os.getpid())),phase='watching',pending=None,last=None,
            dropped=[],quiet=None,closure=None,partialClosure=None)
        if version>=2:state['transitions']=[]
        header=dict(snapshotsActorVersion=version,runId=RUN,binding=deepcopy(BINDING),payload=pack([state]))
        self.actor.store.write(header,None);return state,header
    def test_exact_versions_one_and_two_add_no_invented_consumed_cue_and_preserve_original_until_cas(self):
        for version in (1,2):
            with self.subTest(version=version):
                if self.actor.store.read() is not None:
                    self.actor.store.discard(self.actor.store.read())
                state,header=self.legacy(version);path=self.actor.store.path;before=(path.stat().st_ino,path.read_bytes())
                flow=PhoneSnapshotsActor(self.f)
                with self.f.lock.held():
                    flow.load();self.assertEqual(dict(state,transitions=[],primaryCue=None),flow.state)
                    self.assertEqual(before,(path.stat().st_ino,path.read_bytes()))
                    flow.save()
                actual=flow.store.read();self.assertEqual(3,actual['snapshotsActorVersion'])
                self.assertEqual(dict(state,transitions=[],primaryCue=None),unpack(actual['payload'])[0])
    def test_legacy_unknown_or_v3_only_fields_are_not_silently_removed(self):
        for version in (1,2):
            for field in ('primaryCue','unowned'):
                with self.subTest(version=version,field=field):
                    if self.actor.store.read() is not None:self.actor.store.discard(self.actor.store.read())
                    state,header=self.legacy(version);state[field]=None
                    changed=dict(header,payload=pack([state]));self.actor.store.write(changed,header)
                    before=self.actor.store.path.read_bytes()
                    with self.f.lock.held(),self.assertRaises(NativeUIError):PhoneSnapshotsActor(self.f).load()
                    self.assertEqual(before,self.actor.store.path.read_bytes())
    def test_unknown_versions_or_missing_v3_cue_remain_red_without_private_writes(self):
        state,header=self.legacy(2)
        for version in (True,0,4,3):
            with self.subTest(version=version):
                old=self.actor.store.read();candidate=dict(header,snapshotsActorVersion=version)
                self.actor.store.write(candidate,old);before=self.actor.store.path.read_bytes()
                with self.f.lock.held(),self.assertRaises(NativeUIError):PhoneSnapshotsActor(self.f).load()
                self.assertEqual(before,self.actor.store.path.read_bytes())
    def test_foreign_original_process_is_not_rebound_during_legacy_migration(self):
        state,header=self.legacy(2);state['process']['start']='foreign-start'
        foreign=dict(header,payload=pack([state]));self.actor.store.write(foreign,header)
        with self.f.lock.held(),self.assertRaises(NativeUIError):self.actor.load()
        self.assertEqual(foreign,self.actor.store.read())
    def test_retained_actor_rejects_formally_valid_rollback_after_own_v3_save(self):
        _state,header=self.legacy(2)
        with self.f.lock.held():
            self.actor.load();self.actor.save();self.actor.store.write(header,self.actor.previous)
            before=self.actor.store.path.read_bytes()
            with self.assertRaises(NativeUIError):self.actor.load()
        self.assertEqual(before,self.actor.store.path.read_bytes())
    def test_empty_cue_has_no_current_or_historical_measurement_authority(self):
        def forbidden():raise AssertionError('Empty scheduling floor acquired a source')
        self.f.bound=forbidden
        validate_primary_cue(self.f,None,None,history_guard=forbidden)
        self.assertEqual(actor_fields(1)|{'transitions','primaryCue'},actor_fields(3))
        with self.assertRaises(NativeUIError):actor_fields(True)


if __name__=='__main__':unittest.main()
