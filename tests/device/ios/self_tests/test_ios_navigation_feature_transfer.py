"""Connected restart and independently born current source producers.

Actual journals, normal input recipes, HTTP and file bytes; OS/native are models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.self_tests import test_ios_navigation_feature_restart as first
from ios.self_tests.navigation_feature_next_process_fixture import NextProcess


class NavigationFeatureTransferTests(unittest.TestCase):
    setUp=first.NavigationFeatureRestartTests.setUp
    action=first.NavigationFeatureRestartTests.action
    ready=first.NavigationFeatureRestartTests.ready
    restart_call=first.NavigationFeatureRestartTests.restart_call

    def install(self,*,lost_bookmark=False):
        h=self.h;self.new=None
        def owner(*args):
            if self.new is None:
                self.new=NextProcess(h)
                if lost_bookmark:self.new.books.loaded={}
            return self.new.owner(*args)
        h.runtime._navigation_process_owner=owner
        previous=h.runtime._navigation_observer
        h.runtime._navigation_observer=lambda selector,client,run,role,stage,root,lock:(
            previous(selector,client,run,role,stage,root,lock) if stage==0 else self.new.observer(role,lock=lock))

    def test_actual_new_source_group_advances_once_without_rewriting_old_admission_or_restart(self):
        self.ready();h=self.h;self.install();initial=deepcopy(h.flow_fixture.f.admission.store.read())
        call=self.restart_call();self.assertEqual({'performed':True},h.flow.act(call))
        parent=unpack(h.flow.store.read()['payload'])[0];self.assertEqual(1,parent['stage'])
        self.assertEqual('43',parent['binding']['processIdentity']);self.assertEqual('42',parent['initialBinding']['processIdentity'])
        self.assertGreater(parent['observerOffsets']['primary'],0);self.assertGreater(parent['observerOffsets']['actor'],0)
        self.assertEqual(initial,h.flow_fixture.f.admission.store.read())
        original=PrivateFeatureState(h.root/'ios-navigation-process-context.json').read();state=unpack(original['payload'])[0]
        self.assertEqual('transferred',state['phase'])
        for name,value in state['originals'].items():self.assertEqual(43,value['processId'],name)
        commands=deepcopy(h.lifecycle.calls);requests={n:deepcopy(p.requests) for n,p in self.new.producers.items()}
        self.assertEqual({'performed':True},h.flow_fixture.flow().act(call))
        self.assertEqual(commands,h.lifecycle.calls);self.assertEqual(['app.stop','app.launch'],commands)
        self.assertEqual(requests,{n:p.requests for n,p in self.new.producers.items()})
        self.assertEqual(original,PrivateFeatureState(h.root/'ios-navigation-process-context.json').read())

    def test_both_roles_capture_fresh_current_process_originals_after_actual_transfer(self):
        self.ready();h=self.h;self.install();h.flow.act(self.restart_call())
        first=deepcopy(h.flow.state['observerOffsets'])
        measured=h.flow.observe_active(first['primary'])
        self.assertEqual(first['primary']+1,measured['sequence']);self.assertEqual(1,measured['stage'])
        self.assertEqual('43',measured['binding']['processIdentity']);self.assertEqual('A',measured['state']['location'])
        self.assertEqual(43,measured['nativeAfter']['processId'])
        actor=h.flow_fixture.flow('actor');peer=actor.observe_active(first['actor'])
        self.assertEqual(first['actor']+1,peer['sequence']);self.assertEqual(1,peer['stage'])
        self.assertNotEqual(measured['requestId'],peer['requestId']);self.assertEqual(2,self.new.gpu.frames)

    def test_real_persistence_bytes_with_ignored_new_startup_load_keep_transfer_owned_and_no_restart_replay(self):
        self.ready();h=self.h;self.install(lost_bookmark=True);call=self.restart_call()
        with self.assertRaises(NativeUIError):h.flow.act(call)
        self.assertEqual(['app.stop','app.launch'],h.lifecycle.calls)
        parent=unpack(h.flow.store.read()['payload'])[0];self.assertEqual(0,parent['stage']);self.assertIsNone(parent['transferSha256'])
        store=PrivateFeatureState(h.root/'ios-navigation-process-context.json');original=deepcopy(store.read())
        self.assertIsNotNone(original)
        with self.assertRaises(NativeUIError):h.flow_fixture.flow().act(call)
        self.assertEqual(['app.stop','app.launch'],h.lifecycle.calls);self.assertEqual(original,store.read())


if __name__=='__main__':unittest.main()
