#!/usr/bin/env python3
"""Actual immutable cleanup file passes never grant current target authority."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager,ExitStack
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_quiet_role_reuse as probe
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
import overte_phone_snapshots_history_pass as history_module
from overte_phone_snapshots_history_pass import SnapshotHistoryReadPass
from overte_phone_snapshots_role import PhoneSnapshotsRole
from overte_phone_snapshots_measurements import SnapshotPending


class SnapshotHistoryReadPassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):probe.SnapshotQuietRoleReuseTests.setUpClass()
    @classmethod
    def tearDownClass(cls):probe.SnapshotQuietRoleReuseTests.tearDownClass()
    def setUp(self):
        self.fixture=probe.SnapshotQuietRoleReuseTests.fixture_type('test_original_public_baseline_before_any_input_or_capture')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.feature=None
        if self._testMethodName!='test_absent_original_created_after_pass_is_red':
            self.feature=probe.prepared_role(self.fixture)['feature']

    @contextmanager
    def history_pass(self):
        f=self.feature;token=None
        with ExitStack() as session:
            with f.lock.held():
                session.enter_context(f.adapter.existing_input_session(f.selector))
                f.load();role=PhoneSnapshotsRole(f,'primary');prepared=f.cleanup_observe_pin(role)
                token=SnapshotHistoryReadPass(role,prepared)
            try:yield f,role,token
            finally:
                with f.lock.held():
                    token.close();session.close()

    def test_full_actual_files_read_unlocked_without_any_current_authority_then_single_use(self):
        with self.history_pass() as (f,role,token):
            fail=AssertionError('Host history attempted current target authority')
            with patch.object(f,'bound',side_effect=fail),patch.object(role,'bound',side_effect=fail),patch.object(f.phase,'status',side_effect=fail):
                self.assertEqual(token.prepared['framesSha256'],token.read())
            self.assertTrue(any(p.name.startswith('emote-frame-') for p in token.files))
            self.assertTrue(any(p.name.startswith('emote-index-') for p in token.files))
            self.assertTrue(any(p.suffix=='.png' for p in token.files))
            self.assertTrue(any(p.suffix=='.bin' for p in token.files))
            with self.assertRaises(NativeUIError):role.history_authority()
            with f.lock.held():self.assertTrue(token.finish())
            with self.assertRaises(NativeUIError):token.guard()
            with self.assertRaises(NativeUIError):token.read()

    def test_actual_old_original_mutations_after_full_read_are_red_at_reacquisition(self):
        # Each counter starts a NEW pass over the same genuinely owned files.
        # Restoring our fixture after rejection supplies no authority to the
        # rejected pass; it is already closed.
        for suffix,mutation in (('.json','bytes'),('.png','mode'),('.bin','link'),('.json','replacement'),('manifest','bytes')):
            with self.subTest(suffix=suffix,mutation=mutation),self.history_pass() as (f,role,token):
                token.read();path=next(p for p in token.files if (p.name.startswith('emote-index-') if suffix=='manifest' else p.suffix==suffix))
                raw=path.read_bytes();mode=path.stat().st_mode&0o777;other=path.with_name(path.name+'.controlled')
                try:
                    if mutation=='bytes':path.write_bytes(raw+b' ')
                    elif mutation=='mode':path.chmod(0o640)
                    elif mutation=='link':os.link(path,other)
                    else:path.rename(other);path.write_bytes(raw);path.chmod(mode)
                    with self.assertRaises(NativeUIError),f.lock.held():token.finish()
                    self.assertTrue(token.closed)
                finally:
                    if mutation=='bytes':path.write_bytes(raw)
                    elif mutation=='mode':path.chmod(mode)
                    elif mutation=='link':other.unlink()
                    else:path.unlink();other.rename(path)

    def test_same_valid_owner_header_replacement_is_red_even_with_equal_payload(self):
        for owner in ('feature','role'):
            with self.subTest(owner=owner),self.history_pass() as (f,role,token):
                token.read();store=f.store if owner=='feature' else role.store
                original=deepcopy(store.read());store.write(original,original)
                self.assertEqual(original,store.read())
                with self.assertRaises(NativeUIError),f.lock.held():token.finish()
                self.assertEqual(original,store.read())

    def test_absent_original_created_after_pass_is_red(self):
        fixture=self.fixture;h=probe.harness
        fixture.client.activate('c'*32)
        fixture.invoke('feature.snapshots.observe',dict(contractVersion=h.VERSION,runId=h.RUN,afterSequence=0))
        fixture.act('open',{})
        fixture.invoke('feature.snapshots.observe',dict(contractVersion=h.VERSION,runId=h.RUN,afterSequence=0))
        fixture.act('capture',dict(mode='still',format='png'))
        f=fixture.adapter._snapshots_feature('test-only-appium',h.RUN)
        with f.lock.held(),f.adapter.existing_input_session(f.selector):
            f.load();role=PhoneSnapshotsRole(f,'primary');owned=[]
            capture=f.adapter._world_render_capture;intent=role.image_intent
            def actual_capture(*args,**kwargs):
                value=capture(*args,**kwargs);owned.append(value);return value
            def actual_plan_then_pending(value):
                result=intent(value)
                if value['phase']=='planned':
                    role.release_capture(owned[-1])
                    raise SnapshotPending('Controlled loss after actual durable image plan')
                return result
            role.image_intent=actual_plan_then_pending
            with patch.object(f.adapter,'_world_render_capture',side_effect=actual_capture),self.assertRaises(SnapshotPending):
                role.read(role.state['sequence'])
            image=deepcopy(role.frames[-1]['image'])
            self.assertTrue(role.frames[-1]['diagnostic']);self.assertEqual('planned',image['phase'])
            self.assertEqual('ready',role.state['phase']);self.assertIsNone(role.state['pending'])
        fixture.client.activate('f'*32,'cleanup')
        fixture.invoke('feature.snapshots.cleanup',dict(contractVersion=h.VERSION,runId=h.RUN))
        self.feature=fixture.adapter._snapshots_feature('test-only-appium',h.RUN)
        with self.history_pass() as (f,role,token):
            token.read();path=f.root/image['name'];self.assertIn(path,token.files);self.assertIsNone(token.files[path])
            try:
                path.write_bytes(b'late actual original');path.chmod(0o600)
                with self.assertRaises(NativeUIError),f.lock.held():token.finish()
            finally:path.unlink()

    def test_actual_missing_original_after_pass_is_red(self):
        with self.history_pass() as (f,role,token):
            token.read();path=next(p for p in token.files if p.suffix=='.json');other=path.with_name(path.name+'.controlled')
            path.rename(other)
            try:
                with self.assertRaises(NativeUIError),f.lock.held():token.finish()
            finally:other.rename(path)

    def test_changed_current_native_pid_is_red_after_successful_host_pass(self):
        with self.history_pass() as (f,role,token):
            token.read();original=self.fixture.setup.f.native.identity
            try:
                self.fixture.setup.f.native.identity='32:foreign-start'
                with self.assertRaises(NativeUIError),f.lock.held():token.finish()
            finally:self.fixture.setup.f.native.identity=original

    def test_mutated_scope_and_reader_memory_cannot_supply_pass_authority(self):
        for mutation in ('scope','memory','receipt-set','joint-seal','prepared'):
            with self.subTest(mutation=mutation),self.history_pass() as (f,role,token):
                token.read();scope=deepcopy(token.scope);state=deepcopy(role.state);frames=role.frames
                try:
                    if mutation=='scope':token.scope['generation']+=1
                    elif mutation=='memory':role.state.update(sequence=0,manifests=[]);role.frames=[]
                    elif mutation=='receipt-set':token.files.clear()
                    elif mutation=='joint-seal':token.files.clear();token.file_seal=()
                    else:token.prepared['state'].update(sequence=0,manifests=[])
                    with self.assertRaises(NativeUIError),f.lock.held():token.finish()
                finally:
                    token.scope.clear();token.scope.update(scope);role.state=state;role.frames=frames

    def test_another_actual_thread_cannot_use_the_live_pass(self):
        with self.history_pass() as (f,role,token):
            token.read();errors=[]
            def foreign():
                try:token.guard()
                except NativeUIError:errors.append(True)
            thread=threading.Thread(target=foreign);thread.start();thread.join(timeout=2)
            self.assertFalse(thread.is_alive());self.assertEqual([True],errors)
            with f.lock.held():self.assertTrue(token.finish())


class SnapshotHistoryRootBoundaryTests(unittest.TestCase):
    """Actual private metadata scans; no target, timing or journey fixture."""
    @contextmanager
    def private_files(self):
        with tempfile.TemporaryDirectory(prefix='snapshot-history-root-') as temporary:
            root=Path(temporary);root.chmod(0o700);files={}
            for index in range(3):
                path=root/('original-'+str(index));path.write_bytes(bytes([index])*17);path.chmod(0o600)
                files[path]=history_module.signature(path)
            files[root/'planned-absent']=None
            token=object.__new__(SnapshotHistoryReadPass);token.root=root;token.files=files
            self.seal(token)
            yield root,token

    def seal(self,token):
        token.file_seal=tuple(token.files.items())
        token.file_seal_sha256=token._files_digest(token.file_seal)

    def test_actual_root_checks_bracket_every_individual_file_signature(self):
        with self.private_files() as (root,token):
            actual=history_module.signature;parent=PrivateFeatureState._parent;seen=[];parents=[]
            def measured(path):seen.append(path);return actual(path)
            def checked(store):parents.append(store.path.parent);return parent(store)
            with patch.object(history_module,'signature',measured),patch.object(PrivateFeatureState,'_parent',checked):
                token._verify_files()
            self.assertEqual([root,root],parents)
            self.assertEqual([root,*token.files,root],seen)

    def test_actual_root_permission_aba_during_scan_is_rejected(self):
        with self.private_files() as (root,token):
            actual=history_module.signature;before=actual(root);changed=[]
            def measured(path):
                result=actual(path)
                if path!=root and not changed:
                    root.chmod(0o750);time.sleep(.002);root.chmod(0o700)
                    changed.append(actual(root))
                return result
            with patch.object(history_module,'signature',measured),self.assertRaises(NativeUIError):
                token._verify_files()
            self.assertEqual(1,len(changed));self.assertEqual(before[:-1],changed[0][:-1])
            self.assertNotEqual(before[-1],changed[0][-1])

    def test_actual_missing_replaced_created_and_foreign_parent_files_still_reject(self):
        for kind in ('missing','same-byte-replacement','planned-created','foreign-parent'):
            with self.subTest(kind=kind),self.private_files() as (root,token),\
                    tempfile.TemporaryDirectory(prefix='snapshot-foreign-root-') as foreign:
                path=next(iter(token.files))
                if kind=='missing':path.unlink()
                elif kind=='same-byte-replacement':
                    other=root/'replacement';other.write_bytes(path.read_bytes());other.chmod(0o600)
                    os.replace(other,path)
                    self.assertNotEqual(token.files[path][:2],history_module.signature(path)[:2])
                elif kind=='planned-created':
                    path=root/'planned-absent';path.write_bytes(b'late body');path.chmod(0o600)
                else:
                    other=Path(foreign);other.chmod(0o700);path=other/'original'
                    path.write_bytes(b'foreign body');path.chmod(0o600)
                    token.files[path]=history_module.signature(path);self.seal(token)
                with self.assertRaises(NativeUIError):token._verify_files()


if __name__=='__main__':unittest.main()
