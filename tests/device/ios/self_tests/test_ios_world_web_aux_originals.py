"""Actual returned auxiliary packets remain durable before each next query."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.self_tests.world_web_sources_fixture import SDK


class WorldWebAuxOriginalTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.store=PrivateFeatureState(self.root/'ios-world-web-primary-sources.json')
        self.sdk=SDK();self.sdk.use_snapshot=True;self.sdk.use_whole_snapshot=True
    def test_each_return_is_already_durable_before_next_query_and_old_raw_swap_or_deletion_blocks_send(self):
        with self.lock.held():
            owner=self.sdk.owner(self.store,self.lock);old=owner.read_floor;seen=[]
            def reading(name,*args):
                if name=='uikit':
                    from adapters.script_feature.history import unpack
                    actual=unpack(self.store.read()['payload'])[0]['pending']['auxOriginals']
                    self.assertEqual({'widgetReceipt'},set(actual));self.assertEqual(owner.state['pending']['auxOriginals'],actual);seen.append(deepcopy(actual))
                return old(name,*args)
            owner.read_floor=reading;owner.capture('durable-return');self.assertEqual(1,len(seen))
        for fault in ('swap','delete'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);root.chmod(0o700);lock=ScriptSourceLock(root/'script-feature-sources.lock');sdk=SDK();sdk.use_snapshot=True;sdk.use_whole_snapshot=True
                with lock.held():
                    owner=sdk.owner(PrivateFeatureState(root/'ios-world-web-primary-sources.json'),lock);capture=owner.capture_widgets
                    def mutate():
                        capture();raw=owner.state['pending']['auxOriginals']
                        if fault=='swap':raw['widgetReceipt']['observation']['ready']=False
                        else:raw.clear()
                    owner.capture_widgets=mutate
                    with self.assertRaises(NativeUIError):owner.capture('forbidden-raw-change')
                    self.assertNotIn('uikit',sdk.queries)
    def test_interrupted_carrier_planned_opened_saved_reconstructs_exact_returned_raws_without_replaying_any_query(self):
        for phase in ('planned','opened','saved'):
            with self.subTest(phase=phase),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);root.chmod(0o700);lock=ScriptSourceLock(root/'script-feature-sources.lock');sdk=SDK();sdk.use_snapshot=True;sdk.use_whole_snapshot=True
                store=PrivateFeatureState(root/'ios-world-web-primary-sources.json')
                with lock.held():
                    owner=sdk.owner(store,lock);intent=owner.storage_intent
                    def interrupt(name,kind,value):
                        result=intent(name,kind,value)
                        if name=='widgets' and value['phase']==phase:raise NativeUIError('Modeled interruption after actual durable carrier phase')
                        return result
                    owner.storage_intent=interrupt
                    with self.assertRaises(NativeUIError):owner.capture('interrupted-carrier')
                    retained=deepcopy(owner.state['pending']);self.assertEqual({'widgetReceipt','uikit','browser'},set(retained['auxOriginals']))
                    commands=deepcopy(sdk.queries);posts=len(sdk.snapshot_native.commands)
                    rebuilt=sdk.owner(store,lock,historical=True)
                    self.assertEqual(retained,rebuilt.state['pending']);self.assertEqual(commands,sdk.queries);self.assertEqual(posts,len(sdk.snapshot_native.commands))
                    if phase=='saved':
                        values=[value for key,value in retained['storage'].items() if key.startswith('widgets.')]
                        self.assertEqual(1,len(values));self.assertEqual('saved',values[0]['phase'])
                        carrier=owner.parts.legacy.store('widgets').read(values[0])
                        self.assertIn('data',carrier)
    def test_dropped_third_return_or_slow_durable_raw_write_blocks_next_actual_clock_request(self):
        for fault in ('drop-browser','slow-write'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);root.chmod(0o700);lock=ScriptSourceLock(root/'script-feature-sources.lock');sdk=SDK();sdk.use_snapshot=True;sdk.use_whole_snapshot=True
                with lock.held():
                    owner=sdk.owner(PrivateFeatureState(root/'ios-world-web-primary-sources.json'),lock);remember=owner.remember_aux;sent=[]
                    native_send=owner.native.send
                    def native(query):sent.append(deepcopy(query));return native_send(query)
                    owner.native.send=native;floor=[]
                    def remember_return(name,value):
                        result=remember(name,value)
                        if name=='browser':
                            floor.append(len(sent))
                            if fault=='drop-browser':owner.state['pending']['auxOriginals'].pop('browser')
                            else:sdk.sleep(2)
                        return result
                    owner.remember_aux=remember_return
                    with self.assertRaises(NativeUIError):owner.capture('late-or-missing-actual-raw')
                    self.assertEqual(1,len(floor));self.assertEqual(floor[0],len(sent))
                    from adapters.script_feature.history import unpack
                    retained=unpack(owner.store.read()['payload'])[0]['pending']['auxOriginals']
                    self.assertEqual({'widgetReceipt','uikit','browser'},set(retained))


if __name__=='__main__':unittest.main()
