"""Actual SDK WAL/originals/OS stage one with explicit paired-cut models.

The pair's native seal/fence and closed SDK cut are deliberately modeled here.
This suite verifies once-only SDK dispatch and recovery, not whole Emote end.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.appium_adapter import WebDriverRequestError
from ios.adapters.emote_rooted_process_end import IOSEmoteRootedProcessEnd
from ios.adapters.emote_rooted_session_end import IOSEmoteRootedSessionEnd
from ios.adapters.installed_code import VERSION
from ios.self_tests.test_ios_bundle_observation import Boundary as BundleBoundary
from ios.self_tests import test_ios_emote_rooted_process_end as process_fixture
from ios.self_tests.test_ios_process_retirement import BINDING
from ios.self_tests.test_ios_retired_process import SOURCE,BUNDLE


class RootedSessionEndStorageTests(unittest.TestCase):
    def setUp(self):
        self.f=process_fixture.RootedProcessEndStorageTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.process=self.f.owner;self.os=self.f.os
        for _ in range(3):self.process.advance();self.os.clock+=1.6
        self.assertEqual('complete',self.process.state['phase'])
        self.base=self.process.runtime.adapter
        self.sdk=PrivateFeatureState(self.process.lock.path.with_name('session.json'))
        self.sdk.write({key:BINDING[key] for key in ('sessionId','generation','targetFingerprint')},None)
        self.installed=PrivateFeatureState(self.process.lock.path.with_name('installed-code-binding.json'))
        bundle=BundleBoundary();bundle.send(dict(schemaVersion=1,commandId='ios-'+'a'*32,action='ios-bundle-observe'))
        observation=json.loads(bundle.original())
        self.installed.write(dict(bindingVersion=VERSION,phase='retired',scope={key:value for key,value in BINDING.items() if key!='processIdentity'},
            source=deepcopy(SOURCE),process=dict(bundleId=BUNDLE,pid=42,foreground=True),observation=observation,previousInstance=None,recovery=None),None)
        self.base.read_session=lambda selector:self.sdk.read()
        self.base._binding_store=lambda selector:self.installed
        self.base.state_path=lambda selector:self.sdk.path
        self.base._candidate_guard=lambda **kwargs:None
        self.base._retired_candidate_scope=lambda selector,scope:dict(serverUrl='http://127.0.0.1:9',appId=BUNDLE)
        primary=object.__new__(IOSEmoteRootedProcessEnd);primary.role='primary';primary.peer=self.process;primary.archive=self.process.archive
        primary.completed=lambda:dict(explicitPrimaryProcessModel=True)
        self.processes=dict(actor=self.process,primary=primary)
        self.calls=[];self.deleted=False;self.fault='';case=self
        class Client:
            def call(_self,method,path):
                case.calls.append(method);case.assertEqual('/session/'+BINDING['sessionId'],path)
                if case.deleted:raise WebDriverRequestError(404,'Explicit SDK absence')
                if method=='DELETE':
                    if case.fault=='ignored':return {}
                    case.deleted=True
                    if case.fault=='lost':raise RuntimeError('Explicit lost DELETE reply')
                else:case.assertEqual('GET',method)
                return {}
        class ExplicitCutModel:
            def __init__(_self,session):pass
            def issued(_self,reads):case.assertTrue(reads)
            def guard(_self):
                if case.fault=='stale':case.os.clock+=2
                return True
        self.enterContext(patch('ios.adapters.appium_adapter.WebDriver',return_value=Client()))
        self.enterContext(patch('ios.adapters.emote_rooted_session_end.retired_process_observer',side_effect=lambda *args:self.os.reader()))
        self.enterContext(patch('ios.adapters.emote_rooted_sdk_cut.IOSEmoteRootedSDKCut',ExplicitCutModel))
    def owner(self):return IOSEmoteRootedSessionEnd(self.process,self.processes)
    def until_ready(self):
        owner=self.owner()
        self.assertFalse(owner.finish());self.os.clock+=1.6;self.assertFalse(owner.finish());self.os.clock+=1.6
        return owner
    def test_actual_stage_one_quiet_delete_and_independent_404_then_pure_completed_replay(self):
        owner=self.until_ready();self.assertTrue(owner.finish());self.assertEqual(1,self.calls.count('DELETE'))
        self.assertEqual('GET',self.calls[-1]);self.assertTrue(self.deleted)
        self.assertIsNone(self.sdk.read());self.assertIsNone(self.installed.read())
        self.assertTrue(owner.os_state()['windows'][-1]['complete'])
        queries,calls=deepcopy(self.os.queries),deepcopy(self.calls)
        self.assertTrue(self.owner().finish());self.assertEqual(queries,self.os.queries);self.assertEqual(calls,self.calls)
    def test_lost_delete_reply_reopens_original_journal_and_observes_404_without_resend(self):
        owner=self.until_ready();self.fault='lost'
        with self.assertRaises((RuntimeError,NativeUIError)):owner.finish()
        self.assertEqual('delete-issued',owner.state['phase']);self.assertTrue(self.deleted)
        self.fault='';self.assertTrue(self.owner().finish());self.assertEqual(1,self.calls.count('DELETE'))
    def test_ignored_delete_ack_retains_sdk_and_installed_ownership_and_never_resends(self):
        owner=self.until_ready();self.fault='ignored'
        with self.assertRaises(NativeUIError):owner.finish()
        for _ in range(2):
            with self.assertRaises(NativeUIError):self.owner().finish()
        self.assertEqual(1,self.calls.count('DELETE'));self.assertFalse(self.deleted)
        self.assertIsNotNone(self.sdk.read());self.assertIsNotNone(self.installed.read())
    def test_foreign_local_sdk_after_uncertainty_is_not_discarded(self):
        owner=self.until_ready();self.fault='lost'
        with self.assertRaises((RuntimeError,NativeUIError)):owner.finish()
        old=self.sdk.read();foreign=dict(old,sessionId='foreign-session');self.sdk.write(foreign,old);self.fault=''
        with self.assertRaises(NativeUIError):self.owner().finish()
        self.assertEqual(foreign,self.sdk.read());self.assertIsNotNone(self.installed.read());self.assertEqual(1,self.calls.count('DELETE'))
    def test_lost_stage_one_reply_cannot_bridge_quiet_or_dispatch_delete(self):
        owner=self.owner()
        with patch.object(self.os,'send',side_effect=OSError('Explicit lost stage-one reply')),self.assertRaises((OSError,NativeUIError)):owner.finish()
        self.os.clock+=1;owner=self.owner();self.assertFalse(owner.finish())
        self.assertEqual('preparing',owner.state['phase']);state=owner.os_state()
        self.assertEqual(1,state['windows'][-1]['start']);self.assertEqual(0,state['windows'][-1]['elapsedMs']);self.assertEqual([],self.calls)
    def test_expired_original_os_acquisition_blocks_delete_after_durable_issue(self):
        owner=self.until_ready();self.fault='stale'
        with self.assertRaises(NativeUIError):owner.finish()
        self.assertEqual('delete-issued',owner.state['phase']);self.assertEqual(0,self.calls.count('DELETE'))
        self.assertIsNotNone(self.sdk.read());self.assertIsNotNone(self.installed.read())
    def test_stage_one_cannot_start_a_different_original_os_process_anchor(self):
        self.os.anchor=deepcopy(self.os.anchor);self.os.anchor['sequence']+=1
        with self.assertRaises(NativeUIError):self.owner().finish()
        self.assertEqual([],self.calls);self.assertIsNotNone(self.sdk.read());self.assertIsNotNone(self.installed.read())
    def test_boolean_sdk_generation_cannot_equal_the_bound_integer_generation(self):
        previous=self.sdk.read();self.sdk.write(dict(previous,generation=True),previous)
        owner=self.until_ready()
        with self.assertRaises(NativeUIError):owner.finish()
        self.assertEqual([],self.calls);self.assertIsNotNone(self.sdk.read())
    def test_stage_one_reader_uses_role_host_callbacks_without_retiming_stage_zero(self):
        owner=self.owner();original=deepcopy(self.process.os_store().read());readers=[]
        def fresh_reader(*args):
            reader=self.os.reader();reader.epoch_ms=lambda:1;reader.monotonic=lambda:0;readers.append(reader);return reader
        with patch('ios.adapters.emote_rooted_session_end.retired_process_observer',side_effect=fresh_reader):
            self.assertFalse(owner.finish())
        self.assertIs(owner.flow.epoch_ms,readers[0].epoch_ms);self.assertIs(owner.monotonic,readers[0].monotonic)
        self.assertEqual(original,self.process.os_store().read());self.assertEqual([],self.calls)
        self.assertGreater(readers[0].acquisition['hostBeforeEpochMs'],1700000000000)


if __name__=='__main__':unittest.main()
