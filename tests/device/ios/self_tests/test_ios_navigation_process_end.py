"""Lifecycle mechanics over real HTTP/files; live source seal/OS are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack
from ios.adapters.navigation_process_end import NavigationProcessEnd
from ios.adapters.navigation_session_end import NavigationSessionEnd
from ios.adapters import appium_adapter as backend
from ios.self_tests.navigation_end_fixture import EndBoundary


class NavigationProcessEndTests(unittest.TestCase):
    def setUp(self):self.h=EndBoundary(self)
    def owner(self):return NavigationProcessEnd(self.h.terminal)
    def quiet(self,owner):
        self.assertFalse(owner.advance());self.h.flow.sleep(1.6)
        self.assertFalse(owner.advance());self.h.flow.sleep(1.6);self.assertTrue(owner.advance())

    def test_once_stop_and_separate_original_os_windows_precede_actual_sdk_delete_and_replay(self):
        h=self.h
        with h.flow.held():
            owner=self.owner();owner.prepare();owner.stop();native=list(h.installed.native.commands);self.quiet(owner)
            a,b=owner.role_os('primary'),owner.role_os('actor')
            self.assertNotEqual(a['originalSha256'],b['originalSha256']);self.assertGreaterEqual(a['samples'],3)
            sdk=NavigationSessionEnd(owner);sdk.finish();original=deepcopy(sdk.previous)
            self.assertEqual(original,NavigationSessionEnd(self.owner()).historical())
            self.assertIsNone(h.sdk.read());self.assertIsNone(h.installed.store.read())
            self.assertEqual(1,h.stops);self.assertEqual(1,sum(method=='DELETE' for method,_ in h.requests))
            self.assertEqual(native,h.installed.native.commands);self.assertEqual(h.payload_bytes,h.payload.read_bytes())

    def test_lost_stop_and_delete_returns_remain_owned_and_are_never_sent_again(self):
        h=self.h
        with h.flow.held():
            owner=self.owner();owner.prepare();h.stop_lost=True
            with self.assertRaises(Exception):owner.stop()
            self.assertEqual('stop-issued',self.owner().state['phase'])
            with self.assertRaises(NativeUIError):self.owner().stop()
            owner=self.owner();self.quiet(owner);sdk=NavigationSessionEnd(owner);h.delete_lost=True
            with self.assertRaises(Exception):sdk.finish()
            self.assertEqual('delete-issued',NavigationSessionEnd(owner).state['phase'])
            NavigationSessionEnd(owner).finish()
            self.assertEqual(1,h.stops);self.assertEqual(1,sum(method=='DELETE' for method,_ in h.requests))
            self.assertIsNone(h.sdk.read())

    def test_ignored_sdk_delete_ack_keeps_actual_metadata_and_cannot_resend(self):
        h=self.h
        with h.flow.held():
            owner=self.owner();owner.prepare();owner.stop();self.quiet(owner);h.delete_ignored=True
            for _ in range(2):
                with self.assertRaises(NativeUIError):NavigationSessionEnd(owner).finish()
            self.assertEqual(1,sum(method=='DELETE' for method,_ in h.requests));self.assertEqual(1,h.stops)
            self.assertIsNotNone(h.sdk.read());self.assertIsNotNone(h.installed.store.read())

    def test_changed_original_or_slow_durable_stop_intent_prevents_first_sdk_input(self):
        h=self.h
        # The parent's original input clock must reject this even without a
        # caller's fresh API deadline; source-lock ownership remains real.
        with h.flow.lock.held():
            owner=self.owner();owner.prepare();write=owner.store.write
            def slow(value,previous):write(value,previous);h.flow.sleep(31)
            with patch.object(owner.store,'write',side_effect=slow),self.assertRaises(NativeUIError):owner.stop()
            self.assertEqual(0,h.stops);self.assertEqual('stop-issued',self.owner().state['phase'])
            with self.assertRaises(NativeUIError):self.owner().stop()
            self.assertEqual(0,h.stops)

    def test_original_file_replacement_blocks_stop_without_forgetting_retained_root(self):
        h=self.h
        with h.flow.held():
            owner=self.owner();owner.prepare();h.payload.write_text('{"foreign":true}')
            with self.assertRaises(NativeUIError):owner.stop()
            self.assertEqual(0,h.stops);self.assertIsNotNone(h.sdk.read());self.assertIsNotNone(h.installed.store.read())

    def test_unknown_sdk_get_is_preserved_before_distinct_read_and_one_delete(self):
        h=self.h
        with h.flow.held():
            owner=self.owner();owner.prepare();owner.stop();self.quiet(owner);sdk=NavigationSessionEnd(owner);sdk.prepare();h.get_lost=True
            with self.assertRaises(Exception):sdk.query()
            self.assertIsNotNone(NavigationSessionEnd(owner).state['pending'])
            again=NavigationSessionEnd(owner);again.finish()
            self.assertEqual(['abandoned','present','absent'],[row['status'] for row in again.state['queries']])
            self.assertEqual(1,sum(method=='DELETE' for method,_ in h.requests))

    def test_foreign_sdk_metadata_after_delete_uncertainty_cannot_be_removed(self):
        h=self.h
        with h.flow.held():
            owner=self.owner();owner.prepare();owner.stop();self.quiet(owner);h.delete_lost=True
            with self.assertRaises(Exception):NavigationSessionEnd(owner).finish()
            original=h.sdk.read();h.sdk.write(dict(original,sessionId='foreign-session'),original);before=list(h.requests)
            with self.assertRaises(NativeUIError):NavigationSessionEnd(owner).finish()
            self.assertEqual(before,h.requests);self.assertEqual('foreign-session',h.sdk.read()['sessionId'])

    def test_modeled_live_seal_joins_actual_sdk_end_archive_and_repeats_without_transport(self):
        h=self.h;seal=h.terminal.state['seal'];result=h.terminal.finish(seal)
        before=list(h.requests)
        with patch.object(backend.WebDriver,'call',side_effect=AssertionError('Historical finish attempted transport')):
            self.assertEqual(result,h.terminal.finish(seal))
        self.assertEqual(before,h.requests);self.assertEqual(1,h.stops)
        self.assertEqual(1,sum(method=='DELETE' for method,_ in h.requests))
        self.assertEqual(result['roles']['primary']['stopOriginalSha256'],result['roles']['actor']['stopOriginalSha256'])

    def test_rehashed_role_wrapper_cannot_borrow_primary_os_originals(self):
        h=self.h
        with h.flow.held():
            owner=self.owner();owner.prepare();owner.stop();self.quiet(owner);before=list(h.requests)
            primary=owner.os_store('primary');actor=owner.os_store('actor');copied=deepcopy(primary.read());copied['role']='actor'
            state=unpack(copied['payload'])[0]
            for reference in state['records']:
                number=reference['ordinal'];old=primary.path.with_name(primary.path.stem+'-'+str(number)+'.json')
                original=PrivateFeatureState(old).read();original['role']='actor'
                destination=PrivateFeatureState(actor.path.with_name(actor.path.stem+'-'+str(number)+'.json'))
                destination.write(original,destination.read());reference['sha256']=digest(original)
            copied['payload']=pack([state]);actor.write(copied,actor.read())
            end=deepcopy(owner.previous);state=unpack(end['payload'])[0];state['os']['actor']=digest(copied);end['payload']=pack([state])
            owner.store.write(end,owner.previous)
            with self.assertRaises(NativeUIError):self.owner()
            self.assertEqual(before,h.requests)


if __name__=='__main__':unittest.main()
