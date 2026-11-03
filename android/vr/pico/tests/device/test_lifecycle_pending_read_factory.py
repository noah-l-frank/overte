"""Actual Pico factories; Native/SDK are explicitly synthetic and never run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_normal_scripts as canonical
from adapters.native_feature_observation import NativeFeatureObservation,need
from adapters.pending_commit_owner import NativePendingCommitOwner
from adapters.pico4.lifecycle_namespace_bill import LifecycleNamespaceBill
from adapters.pico4.lifecycle_pending_read import PicoLifecyclePendingRead
from adapters.pico4.lifecycle_source_raw import LifecycleSourceRaw4
from adapters.script_journey.lock import ScriptSourceLock
from self_tests.test_pico_lifecycle_source import RUN


class LifecyclePendingReadFactoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=canonical.PicoNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.adapter,self.native=self.fixture.instance,self.fixture.native
        self.native.identity='123:400';self.native.require_process_identity=lambda value:need(value==self.native.identity)
        self.binary_calls=[]
        def binary(*args,**kwargs):
            self.binary_calls.append((args,kwargs));raise AssertionError('No actual SDK read is allowed in factory admission')
        self.native.execute_bytes=binary
        installed=self.adapter._installation(self.native.target)
        self.binding=dict(sourceRevision=installed['sourceRevision'],artifactSha256=installed['artifactSha256'],
            processIdentity=self.native.identity,sessionId=self.native.bridge_id,generation=0,
            targetFingerprint=hashlib.sha256((self.native.target+'\0'+str(self.adapter.pico_configuration)).encode()).hexdigest())
        root=self.adapter._lifecycle_world_store(self.native.target).path.parent
        self.lock=ScriptSourceLock(root/'script-sources.lock')
        self.namespace=LifecycleNamespaceBill(root,self.lock,mutex_layout=2);self.addCleanup(self.namespace.close)
        self.bank=LifecycleSourceRaw4(root/'lifecycle-background-raw.json',RUN,self.binding,self.lock,
            self.lock.assert_held,self.namespace,time.monotonic,pending_read_version=1);self.addCleanup(self.bank.close_host)
        self.reader=PicoLifecyclePendingRead(self.adapter,self.native.target,self.binding,self.bank.archive,bank=self.bank)

    def zero_native(self,call):
        with ExitStack() as stack:
            spies=[]
            for name in dir(self.native):
                if name!='execute_bytes' and not name.startswith('_') and callable(getattr(self.native,name)):
                    spies.append(stack.enter_context(patch.object(self.native,name,side_effect=AssertionError('Foreign factory must not touch SDK'))))
            with self.assertRaises(ValueError):call()
            self.assertTrue(all(spy.call_count==0 for spy in spies))
        self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)
        self.assertEqual([],self.binary_calls);self.assertEqual(0,self.bank.archive.state['reads'])

    def test_actual_optin_factory_pins_same_native_owner_write_closure_and_original_bank_without_input(self):
        with self.lock.held():
            owner=self.adapter._pending_owner(self.native.target,binding=self.binding,pending_read=self.reader)
        self.assertIs(type(owner),NativePendingCommitOwner)
        self.assertIs(type(self.reader.native_binding[0]),NativeFeatureObservation)
        self.assertIs(self.reader.owner_binding[0],owner)
        self.assertIs(owner.send,self.reader.native_binding[1]);self.assertIs(owner.guard,self.reader.native_binding[2])
        self.assertEqual(owner.original,self.reader.get_original);self.assertEqual(owner.before_io,self.reader.before_io)
        self.assertEqual(self.binding,self.bank.archive.scope['binding']);self.assertIs(self.reader.bank,self.bank)
        self.assertEqual([],self.binary_calls);self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)
        self.assertEqual(0,self.bank.archive.state['reads'])

    def test_actual_default_factory_preserves_unwrapped_getter_and_before_io_none(self):
        owner=self.adapter._pending_owner(self.native.target,binding=self.binding)
        self.assertIs(type(owner),NativePendingCommitOwner);self.assertIsNone(owner.before_io)
        self.assertIsNone(self.reader.native_binding);self.assertIsNone(self.reader.owner_binding)
        self.assertEqual([],self.binary_calls);self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)

    def test_wrong_target_missing_or_foreign_binding_refuse_before_any_cold_script_or_sdk_helper(self):
        wrong=deepcopy(self.binding);wrong['generation']+=1
        for target,binding in ((self.native.target+'-foreign',self.binding),(self.native.target,None),(self.native.target,wrong)):
            with self.subTest(target=target,binding=binding),self.lock.held():
                self.zero_native(lambda:self.adapter._pending_owner(target,binding=binding,pending_read=self.reader))

    def test_foreign_adapter_or_unheld_original_lock_refuse_before_any_sdk(self):
        with self.lock.held():
            original=self.reader.adapter;self.reader.adapter=SimpleNamespace()
            try:self.zero_native(lambda:self.adapter._pending_owner(self.native.target,binding=self.binding,pending_read=self.reader))
            finally:self.reader.adapter=original
        self.zero_native(lambda:self.adapter._pending_owner(self.native.target,binding=self.binding,pending_read=self.reader))


if __name__=='__main__':unittest.main()
