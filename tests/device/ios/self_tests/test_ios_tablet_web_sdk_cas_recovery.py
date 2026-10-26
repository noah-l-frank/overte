"""Actual SDK HTTP and local CAS recovery after an original GET/404.

The preceding complete Tablet/OS authority is the existing explicit component
fixture. No live seal, independent worker, native or full-area end is supplied
by these tests. SDK requests, metadata deletion and reconstruction are real.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.self_tests import test_ios_tablet_web_session_end as session_fixture


class TabletSDKCASRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f=session_fixture.TabletSessionEndTests();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def lose_local_discard_return(self,path):
        original=PrivateFeatureState.discard;lost=[]
        def discard(store,previous):
            result=original(store,previous)
            if store.path==path:
                lost.append(store.path);raise OSError('Actual local metadata discard returned ambiguously after unlink')
            return result
        owner=self.f.owner()
        with patch.object(PrivateFeatureState,'discard',new=discard),self.assertRaises(OSError):owner.advance()
        self.assertEqual([path],lost);self.assertEqual('sdk-absent',owner.state['phase'])
        self.assertFalse(self.f.server.present)
        self.assertEqual([('GET','/session/test-only'),('DELETE','/session/test-only'),('GET','/session/test-only')],self.f.server.calls)
        return owner

    def recover_without_any_request(self,owner):
        requests=list(self.f.server.calls);os_queries=deepcopy(self.f.os.queries)
        transcript=deepcopy({key:owner.state[key] for key in ('queries','osHistory','sdkOriginal','installedOriginal')})
        rebuilt=self.f.owner();result=rebuilt.advance();self.assertEqual('complete',rebuilt.state['phase'])
        self.assertEqual(requests,self.f.server.calls);self.assertEqual(os_queries,self.f.os.queries)
        self.assertEqual(transcript,{key:rebuilt.state[key] for key in transcript})
        self.assertIsNone(self.f.sdk_store.read());self.assertIsNone(self.f.fixture.store.read())
        self.assertEqual(result,self.f.owner().advance());self.assertEqual(requests,self.f.server.calls)
        self.assertEqual(os_queries,self.f.os.queries)

    def test_lost_local_SDK_discard_return_keeps_installed_owner_then_resumes_only_original_CAS(self):
        with self.f.lock.held():
            owner=self.lose_local_discard_return(self.f.sdk_store.path)
            self.assertIsNone(self.f.sdk_store.read());self.assertIsNotNone(self.f.fixture.store.read())
            self.recover_without_any_request(owner)

    def test_lost_installed_discard_return_adopts_actual_absence_without_HTTP_or_OS_resend(self):
        with self.f.lock.held():
            owner=self.lose_local_discard_return(self.f.fixture.store.path)
            self.assertIsNone(self.f.sdk_store.read());self.assertIsNone(self.f.fixture.store.read())
            self.recover_without_any_request(owner)

    def test_foreign_installed_replacement_after_own_SDK_CAS_stays_owned_and_cannot_report_complete(self):
        with self.f.lock.held():
            owner=self.lose_local_discard_return(self.f.sdk_store.path)
            original=self.f.fixture.store.read();foreign=deepcopy(original);foreign['scope']['generation']+=1
            self.f.fixture.store.write(foreign,original);path=self.f.fixture.store.path;raw=path.read_bytes();inode=path.stat().st_ino
            journal=owner.store.path.read_bytes();journal_inode=owner.store.path.stat().st_ino
            requests=list(self.f.server.calls);os_queries=deepcopy(self.f.os.queries)
            with self.assertRaises((ValueError,NativeUIError)):self.f.owner().advance()
            self.assertEqual(raw,path.read_bytes());self.assertEqual(inode,path.stat().st_ino)
            self.assertEqual(journal,owner.store.path.read_bytes());self.assertEqual(journal_inode,owner.store.path.stat().st_ino)
            self.assertEqual(requests,self.f.server.calls);self.assertEqual(os_queries,self.f.os.queries)
            self.assertIsNone(self.f.sdk_store.read());self.assertEqual('sdk-absent',self.f.owner().state['phase'])

    def test_actor_cannot_begin_SDK_end_or_create_a_new_session_end_journal(self):
        with self.f.lock.held():
            self.f.feature.role='actor';owner=self.f.owner();os_queries=deepcopy(self.f.os.queries)
            self.assertFalse(owner.store.path.exists())
            with self.assertRaises(NativeUIError):owner.advance()
            self.assertFalse(owner.store.path.exists());self.assertEqual([],self.f.server.calls)
            self.assertEqual(os_queries,self.f.os.queries);self.assertIsNotNone(self.f.sdk_store.read())
            self.assertIsNotNone(self.f.fixture.store.read());self.assertTrue(self.f.server.present)


if __name__=='__main__':unittest.main()
