"""Original SDK/source lock boundaries with independent host role threads.

No Runtime/source/decoder result is patched. The modeled native producers,
Installed observation CAS, read-only peer admission and OS locks are real host
component paths. These tests do not qualify native execution or full Avatar.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import threading
import unittest
from adapters.script_feature.lock import ScriptSourceBusy,ScriptSourceLock
from ios.self_tests import test_ios_avatar_prepare_composed as preparation


class AvatarRoleSourceSerializationTests(preparation.AvatarPrepareComposedTests):
    # Only these exact new IDs are selected. Inherited tests remain separate
    # unchanged preparation prerequisites.
    def locked_peer(self,owner):
        other='actor' if owner.role=='primary' else 'primary'
        entered=threading.Event();release=threading.Event();errors=[]
        def work():
            try:
                with ScriptSourceLock(owner.locks[other].path).held():
                    entered.set()
                    if not release.wait(10):raise RuntimeError('Owned lock holder was not released')
            except BaseException as error:errors.append(error);entered.set()
        thread=threading.Thread(target=work,name='avatar-test-existing-peer-lock')
        def stop():
            release.set();thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
            if errors:raise errors[0]
        self.addCleanup(stop);thread.start();self.assertTrue(entered.wait(3))
        if errors:raise errors[0]
        return stop

    def snapshots(self,d):
        return {role:dict(bundle=deepcopy(d.installed[role].native.commands),
            native=deepcopy(n.commands),input=list(n.input_log),
            installed=deepcopy(d.installed[role].store.read())) for role,n in d.natives.items()}

    def test_prepare_with_a_busy_peer_lock_refuses_before_either_native_nonce_or_login(self):
        d=self.domain();owner=d.owners['primary'];before=self.snapshots(d)
        stop=self.locked_peer(owner)
        with self.assertRaises(ScriptSourceBusy):owner.prepare()
        self.assertEqual(before,self.snapshots(d));self.assertIsNone(owner.store.read())
        stop()

    def test_own_source_under_real_peer_lock_queries_only_its_sdk_and_preserves_peer_original(self):
        d=self.domain();owner=d.owners['primary']
        with owner.held(paired=True):owner.initialize()
        before=self.snapshots(d);stop=self.locked_peer(owner)
        with owner.held():
            owner.load();source=owner.own_source()
            self.assertEqual(owner.state['bindings']['primary'],source.binding)
        after=self.snapshots(d)
        self.assertEqual(before['actor'],after['actor'])
        self.assertGreater(len(after['primary']['bundle']),len(before['primary']['bundle']))
        self.assertEqual(before['primary']['input'],after['primary']['input'])
        self.assertEqual(before['primary']['native'],after['primary']['native'])
        stop()

    def test_own_source_refuses_changed_peer_process_source_without_any_peer_native_query(self):
        d=self.domain();owner=d.owners['primary']
        with owner.held(paired=True):owner.initialize()
        before=self.snapshots(d);d.installed['actor'].source['instance']='f'*32
        with owner.held():
            owner.load()
            with self.assertRaises((ValueError,RuntimeError)):owner.own_source()
        after=self.snapshots(d)
        self.assertEqual(before['actor'],after['actor'])
        self.assertEqual(before['primary']['input'],after['primary']['input'])
        self.assertEqual(before['primary']['native'],after['primary']['native'])


if __name__=='__main__':unittest.main()
