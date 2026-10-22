"""Original retained address root and actual normal W3C Cancel; SDK modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from feature_journeys.fixtures import context
from ios.adapters.navigation_address_dismiss import NavigationAddressDismiss
from ios.self_tests import test_ios_navigation_address_inputs as address_fixture


class AddressDismissTests(unittest.TestCase):
    def setUp(self):
        self.f=address_fixture.NavigationAddressInputsTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        with self.f.held():
            self.f.goto(self.f.owner())
            url='hifi://'+context('a'*32)['hidden']
            self.f.b.mutation='goto-ignored'
            self.f.owner().goto('missing',url,self.f.b.profile,{url})
            self.f.b.mutation='';self.f.b.address_open=True

    def owner(self):
        return NavigationAddressDismiss(PrivateFeatureState(self.f.path/'ios-navigation-address-dismiss-42.json'),
            self.f.owner(),epoch_ms=self.f.b.host_epoch,monotonic=lambda:self.f.b.clock)

    def test_normal_cancel_preserves_hidden_root_and_original_journals_without_claiming_destruction(self):
        with self.f.held():
            owner=self.owner();address=deepcopy(owner.address.store.read());result=owner.close()
            self.assertEqual('retained',result['status']);self.assertFalse(result['drained'])
            self.assertFalse(self.f.b.address_open);self.assertEqual(address,owner.address.store.read())
            self.assertEqual(1,self.f.b.inputs.count('PhoneAddressCancelButton'))
            before=list(self.f.b.inputs);self.assertEqual(result,self.owner().close());self.assertEqual(before,self.f.b.inputs)

    def test_already_hidden_owned_root_requires_no_cancel_input_and_remains_retained(self):
        self.f.b.address_open=False
        with self.f.held():
            before=list(self.f.b.inputs);result=self.owner().close()
            self.assertEqual('retained',result['status']);self.assertEqual(before,self.f.b.inputs)

    def test_ignored_cancel_is_owned_and_never_repeated_after_reconstruction(self):
        call=self.f.b.call
        def ignored(method,path,body=None):
            value=call(method,path,body)
            if method=='POST' and path.endswith('/click') and 'PhoneAddressCancelButton' in self.f.b.inputs:
                self.f.b.address_open=True
            return value
        self.f.b.call=ignored
        with self.f.held():
            with self.assertRaises(NativeUIError):self.owner().close()
            before=list(self.f.b.inputs)
            with self.assertRaises(NativeUIError):self.owner().close()
            self.assertEqual(before,self.f.b.inputs);self.assertTrue(self.f.b.address_open)

    def test_lost_sdk_return_is_not_replayed_even_if_the_owned_root_is_actually_hidden(self):
        call=self.f.b.call
        def lost(method,path,body=None):
            result=call(method,path,body)
            if method=='POST' and path.endswith('/click'):raise OSError('Lost actual Cancel return')
            return result
        self.f.b.call=lost
        with self.f.held():
            with self.assertRaises(NativeUIError):self.owner().close()
            self.assertFalse(self.f.b.address_open);before=list(self.f.b.inputs)
            with self.assertRaises(NativeUIError):self.owner().close()
            self.assertEqual(before,self.f.b.inputs);self.assertFalse(self.owner().state['returned'])

    def test_fully_retained_return_recovers_without_any_fresh_sdk_read_or_new_input(self):
        with self.f.held():
            owner=self.owner();write=owner.store.write
            def lost(value,previous):
                if unpack(value['payload'])[0]['phase']=='complete':raise OSError('Lost final journal write')
                return write(value,previous)
            with patch.object(owner.store,'write',side_effect=lost),self.assertRaises(OSError):owner.close()
            before=list(self.f.b.inputs);reads=len(self.f.b.native_boundary.requests)
            restored=self.owner();result=restored.recover()
            self.assertEqual('retained',result['status']);self.assertEqual(before,self.f.b.inputs)
            self.assertEqual(reads,len(self.f.b.native_boundary.requests))

    def test_foreign_root_or_changed_owned_field_cannot_be_cancelled(self):
        for fault in ('root','text'):
            with self.subTest(fault=fault):
                self.doCleanups();self.setUp()
                if fault=='root':self.f.b.root['rootId']='00000000-0000-4000-8000-000000000099'
                else:self.f.b.field='hifi://unowned'
                with self.f.held():
                    before=list(self.f.b.inputs)
                    with self.assertRaises(NativeUIError):self.owner().close()
                    self.assertEqual(before,self.f.b.inputs);self.assertTrue(self.f.b.address_open)

    def test_slow_issuing_journal_does_not_deliver_a_late_cancel(self):
        with self.f.held():
            owner=self.owner();write=owner.store.write
            def late(value,previous):
                result=write(value,previous)
                if unpack(value['payload'])[0]['phase']=='issued':self.f.b.clock+=31
                return result
            before=list(self.f.b.inputs)
            with patch.object(owner.store,'write',side_effect=late),self.assertRaises(NativeUIError):owner.close()
            self.assertEqual(before,self.f.b.inputs)
            with self.assertRaises(NativeUIError):self.owner().close()
            self.assertEqual(before,self.f.b.inputs)

    def test_actual_error_modal_cannot_be_covered_by_cancelling_the_owned_address_root(self):
        from ios.self_tests.test_ios_navigation_dialogs import Boundary
        source=Boundary();source.create();observed=self.f.b.observed
        def modal():
            value=observed();value['controls'].extend(dict(row,frame=dict(x=10,y=20,width=250,height=50))
                for row in source.controls()['controls']);return value
        self.f.b.observed=modal
        with self.f.held():
            before=list(self.f.b.inputs)
            with self.assertRaises(NativeUIError):self.owner().close()
            self.assertEqual(before,self.f.b.inputs);self.assertTrue(self.f.b.address_open)


if __name__=='__main__':unittest.main()
