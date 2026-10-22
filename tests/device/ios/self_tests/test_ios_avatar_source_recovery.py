"""Actual abandoned private files/CAS; native sources remain controlled seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.avatar_source_recovery import IOSAvatarSourceRecovery
from ios.adapters.avatar_sources import IOSAvatarSources
from ios.self_tests.test_ios_avatar_sources import SourcesFixture
from ios.self_tests.test_ios_avatar_input_owner import BINDING


class AvatarSourceRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name);self.path.chmod(0o700);self.root=self.path/'originals';self.root.mkdir(mode=0o700)
        self.fixture=SourcesFixture();self.lock=ScriptSourceLock(self.path/'script-feature-sources.lock')
    def sources(self,*,historical=False):return IOSAvatarSources(PrivateFeatureState(self.path/'ios-avatar-primary-sources.json'),self.root,
        BINDING,self.fixture.run,'primary',self.lock,lambda:True,None if historical else self.fixture.phase,
        readers=None if historical else self.fixture.readers(),historical=historical,
        monotonic=lambda:self.fixture.clock,epoch_ms=self.fixture.host)
    def interrupt(self):
        owner=self.sources()
        def missing():raise NativeUIError('Explicit lost original widget return')
        owner.readers['ui'].capture=missing
        with self.assertRaises(NativeUIError):owner.read()
        self.assertIn('entities',owner.state['pending']['partial']);return owner

    def test_passive_recovery_retains_all_six_originals_and_no_request_is_replayed(self):
        with self.lock.held():
            owner=self.interrupt();before=deepcopy(self.fixture.sources);native_count=self.fixture.core.sequence
            recovery=IOSAvatarSourceRecovery(owner);self.assertTrue(recovery.recover())
            self.assertEqual(before,self.fixture.sources);self.assertEqual(native_count,self.fixture.core.sequence)
            self.assertEqual('ready',owner.state['phase']);self.assertIsNone(owner.state['pending'])
            record=recovery.record(recovery.state['records'][0]);self.assertIn('entities',recovery.attempt(record)['pending']['partial'])
            fresh=self.sources();frame=fresh.read();scope=IOSAvatarSourceRecovery(fresh);self.assertTrue(scope.follow(frame))
            archived=IOSAvatarSourceRecovery.archive(scope.store.read(),self.sources(historical=True))
            self.assertTrue(archived.follow(frame,historical=True))
        self.assertTrue(list(self.root.glob('avatar-source-abandoned-*.json')))

    def test_each_actual_abandoned_channel_prefix_cannot_be_replaced_by_valid_new_packet(self):
        for channel in ('state','renderers','http','people','scripts','entities'):
            if channel!='state':self.tearDown();self.setUp()
            with self.subTest(channel=channel),self.lock.held():
                owner=self.interrupt();IOSAvatarSourceRecovery(owner).recover()
                # Every packet remains individually valid. Only the retained
                # original instance association exposes this source reset.
                self.fixture.prototypes[channel]['instance']='9'*32
                fresh=self.sources();frame=fresh.read()
                with self.assertRaises(NativeUIError):IOSAvatarSourceRecovery(fresh).follow(frame)

    def test_original_opened_empty_file_is_retained_and_replacement_inode_is_refused(self):
        with self.lock.held():
            owner=self.sources();callback=owner.originals.intent
            def lost(kind,value):
                callback(kind,value)
                if kind=='original' and value['phase']=='opened':raise NativeUIError('Explicit lost opened-file return')
            owner.originals.intent=lost
            with self.assertRaises(NativeUIError):owner.read()
            original=deepcopy(owner.state['pending']['original']);path=owner.originals.path(original)
            self.assertEqual(b'',path.read_bytes());recovery=IOSAvatarSourceRecovery(owner);recovery.recover()
            attempt=recovery.record(recovery.state['records'][0]);self.assertEqual(0,attempt['partialFile']['bytes'])
            self.assertEqual(original['file'],attempt['partialFile']['file']);self.assertTrue(path.exists())
            raw=path.read_bytes();path.unlink();path.write_bytes(raw);path.chmod(0o600)
            with self.assertRaises(NativeUIError):IOSAvatarSourceRecovery(self.sources())

    def test_lost_source_CAS_return_adopts_only_its_already_committed_transition(self):
        with self.lock.held():
            owner=self.interrupt();recovery=IOSAvatarSourceRecovery(owner);write=owner.store.write
            def lost(value,previous):write(value,previous);raise NativeUIError('Explicit lost source CAS return')
            owner.store.write=lost
            with self.assertRaises(NativeUIError):recovery.recover()
            fresh=self.sources();self.assertEqual('ready',fresh.state['phase'])
            before=deepcopy(self.fixture.sources);again=IOSAvatarSourceRecovery(fresh)
            self.assertTrue(again.recover());self.assertEqual(1,len(again.state['records']))
            self.assertEqual(before,self.fixture.sources);frame=fresh.read();self.assertTrue(again.follow(frame))

    def test_partial_prefix_schema_and_acquisition_digest_are_not_silently_discarded(self):
        with self.lock.held():
            owner=self.interrupt();recovery=IOSAvatarSourceRecovery(owner);partial=owner.state['pending']['partial']
            for operation in ('unknown','missing','hash'):
                value=deepcopy(partial)
                if operation=='unknown':value['imaginedVerdict']=True
                elif operation=='missing':del value['people']
                else:value['scripts']['acquisition']['originalSha256']='0'*64
                with self.subTest(operation=operation),self.assertRaises(NativeUIError):recovery.partial(value)

    def test_worker_retired_between_two_abandoned_reads_cannot_reappear_in_a_valid_new_frame(self):
        with self.lock.held():
            first=self.interrupt();IOSAvatarSourceRecovery(first).recover()
            workers=deepcopy(self.fixture.prototypes['scripts']['source']['workers'])
            self.fixture.prototypes['scripts']['source'].update(workers=[],revision=2)
            second=self.interrupt();IOSAvatarSourceRecovery(second).recover()
            self.fixture.prototypes['scripts']['source'].update(workers=workers,revision=3)
            fresh=self.sources();frame=fresh.read()
            with self.assertRaises(NativeUIError):IOSAvatarSourceRecovery(fresh).follow(frame)

    def test_frozen_source_v1_partial_remains_original_and_new_read_adds_real_entities(self):
        with self.lock.held():
            owner=self.interrupt();state=deepcopy(owner.state);del state['pending']['partial']['entities']
            frozen=owner.envelope(state,version=1);owner.store.write(frozen,owner.previous)
            restored=self.sources();recovery=IOSAvatarSourceRecovery(restored);recovery.recover()
            record=recovery.record(recovery.state['records'][0]);self.assertEqual(frozen,record['priorOwner'])
            self.assertNotIn('entities',recovery.attempt(record)['pending']['partial'])
            current=restored.read();self.assertIn('entities',current['originals']);self.assertTrue(recovery.follow(current))


if __name__=='__main__':unittest.main()
