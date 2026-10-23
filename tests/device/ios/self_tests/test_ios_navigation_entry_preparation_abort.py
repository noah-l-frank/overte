"""Actual interrupted ordinary initial input and unchanged originals to OS end.

Qt/native/GPU/OS producers are explicit models. Production ordinary recipes,
actual PNG files, per-input journals, real SDK HTTP and typed end readers run.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import unpack,pack
from ios.adapters import appium_adapter as backend
from ios.adapters.navigation_partial_preparation_abort import owner
from ios.adapters.navigation_failed_preparation_cleanup import verify
from ios.adapters.navigation_session_cleanup import retire_existing
from ios.self_tests.navigation_end_fixture import EndBoundary
from ios.self_tests import test_ios_navigation_whole_feature as fixtures
from ios import navigation_observer as worker


class NavigationEntryPreparationAbortTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.NavigationWholeFeatureTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.h=self.fixture.h;self.whole=self.fixture.whole;self.flow=self.h.flow

    def interrupt(self,stage):
        b=self.h.flow_fixture.b;call=b.call;lost=[]
        def actual(method,path,body=None):
            before=len(b.inputs);result=call(method,path,body)
            if method=='POST' and path.endswith('/click') and len(b.inputs)>before and not lost:
                if stage=='first' or b.inputs[-1]=='PhoneAddressGoButton':
                    lost.append(b.inputs[-1]);raise OSError('Actual ordinary input return lost')
            return result
        with patch.object(b,'call',side_effect=actual),self.assertRaises((OSError,NativeUIError)):self.whole.prepare()
        self.assertEqual(1,len(lost))
        with self.flow.held():self.flow.load()
        self.assertEqual('preparing',self.flow.state['phase']);self.assertEqual('pending',self.flow.state['entry'])
        return lost

    def finish(self,*,unknown_stop=False):
        f=self.flow;call=dict(contractVersion=16,runId=f.run)
        with f.held():bridge=EndBoundary(self,connected=dict(flow=f,world=self.h),preparing=True)
        files={path:(path.stat().st_ino,path.read_bytes()) for path in f.root.rglob('*') if path.is_file()}
        inputs=deepcopy(self.h.flow_fixture.b.inputs);commands=deepcopy(self.h.gpu.commands)
        actor=self.fixture.actor();requests=[]
        if unknown_stop:
            bridge.stop_lost=True
            with self.assertRaises((OSError,RuntimeError,ValueError)):self.whole.cleanup(call)
            self.assertEqual(1,bridge.stops)
            with patch.object(f.runtime,'_sources',side_effect=AssertionError('Abort worker queried live source')):
                self.assertIsNone(worker.step(actor,dict(target=f.selector)))
            with self.assertRaises(NativeUIError):self.whole.prepare()
            bridge.stop_lost=False
        self.assertEqual({'performed':True},self.whole.cleanup(call))
        with f.held():
            actual=owner(f);result=actual.result();self.assertEqual(3,result['iosNavigationPreparationAbortResultVersion'])
            self.assertEqual('failed',result['status']);self.assertTrue(verify(self.whole,call,{'performed':True}))
        self.assertEqual(1,bridge.stops);self.assertEqual(1,sum(method=='DELETE' for method,_ in bridge.requests))
        mutable={bridge.sdk.path,bridge.installed.store.path}
        for path,original in files.items():
            if path not in mutable:self.assertEqual(original,(path.stat().st_ino,path.read_bytes()))
        self.assertEqual(inputs,self.h.flow_fixture.b.inputs);self.assertEqual(commands,self.h.gpu.commands)
        requests=deepcopy(bridge.requests)
        completed={path:(path.stat().st_ino,path.read_bytes()) for path in f.root.rglob('*') if path.is_file()}
        def forbidden(*_args,**_kwargs):self.fail('Historical failed entry attempted transport')
        with patch.object(f.runtime,'_sources',side_effect=forbidden),patch.object(f.client,'request',side_effect=forbidden),patch.object(backend.WebDriver,'call',side_effect=forbidden):
            self.assertTrue(verify(self.whole,call,{'performed':True}))
            self.assertEqual({'performed':True},self.whole.cleanup(call))
            self.assertEqual({'cleaned':True},retire_existing(f.runtime,f.selector,None))
            self.assertEqual(2,worker.step(actor,dict(target=f.selector)))
        self.assertEqual(requests,bridge.requests)
        self.assertEqual(completed,{path:(path.stat().st_ino,path.read_bytes()) for path in f.root.rglob('*') if path.is_file()})

    def test_lost_initial_go_return_keeps_unknown_input_original_and_ends_without_any_replay(self):
        self.assertEqual(['PhoneAddressGoButton'],self.interrupt('go'));self.finish()

    def test_lost_first_hud_return_keeps_retained_editor_ownership_until_os_end(self):
        self.interrupt('first');self.finish()

    def test_unknown_process_stop_blocks_worker_acquisition_and_preparation_then_resolves_once(self):
        self.interrupt('go');self.finish(unknown_stop=True)

    def test_active_whole_or_new_ordinary_action_cannot_borrow_initial_entry_abort(self):
        self.interrupt('go');f=self.flow
        with f.held():
            bridge=EndBoundary(self,connected=dict(flow=f,world=self.h),preparing=True)
            store=PrivateFeatureState(f.store.path.with_name('ios-navigation-surface-actions.json'));store.write(dict(uncertain=True),None)
            with self.assertRaises(NativeUIError):owner(f)
            self.assertEqual(0,bridge.stops);self.assertEqual(dict(uncertain=True),store.read())

    def test_active_whole_with_completed_initial_input_cannot_borrow_preparation_failure(self):
        self.whole.prepare();f=self.flow
        with f.held():
            bridge=EndBoundary(self,connected=dict(flow=f,world=self.h),preparing=True)
            with self.assertRaises(NativeUIError):owner(f)
            self.assertEqual(0,bridge.stops);self.assertIsNotNone(bridge.sdk.read())

    def test_foreign_normal_component_cannot_borrow_the_actual_unknown_go_intent(self):
        self.interrupt('go');f=self.flow
        with f.held():
            bridge=EndBoundary(self,connected=dict(flow=f,world=self.h),preparing=True)
            store=PrivateFeatureState(f.store.path.with_name('ios-navigation-address-'+f.state['binding']['processIdentity']+'-inputs.json'))
            original=store.read();changed=deepcopy(original);state=unpack(changed['payload'])[0]
            state['rows'][0]['component']['iosNormalNavigation']['context']['processId']=99
            changed['payload']=pack([state]);store.write(changed,original)
            with self.assertRaises(NativeUIError):owner(f)
            self.assertEqual(0,bridge.stops);self.assertEqual(changed,store.read())


if __name__=='__main__':unittest.main()
