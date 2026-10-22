"""Real Python recipe/HTTP/AFC/journals; actual Qt and world are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from adapters.script_feature.history import unpack
from ios.adapters import normal_input
from ios.adapters.navigation_address_inputs import NavigationAddressInputs
from ios.self_tests.test_ios_normal_navigation import IOSBoundary
from ios.self_tests.test_ios_navigation_ui import root
from self_tests.test_completed_frame_lease import BINDING as ORIGINAL_BINDING
from navigation_observation import viewpoint_urls

BINDING=ORIGINAL_BINDING|dict(sessionId='owned-session')
RUN='a'*32


class RetainedBoundary(IOSBoundary):
    def __init__(self,mutation=''):
        super().__init__(mutation);self.root=None;self.source_sequence=0
    def native_epoch(self):return 10000+round(self.clock*1000)
    def host_epoch(self):return 90000+round(self.clock*1000)
    def call(self,method,path,body=None):
        value=super().call(method,path,body)
        if self.address_open and self.root is None:self.root=root()
        return value
    def observed(self):
        value=super().observed();self.source_sequence+=1
        value.update(sampleEpochMs=self.native_epoch(),elapsedMs=round(100+self.clock*1000),
            navigationDialogControlsVersion=1,navigationDialogSourceSequence=self.source_sequence,
            navigationInventory=dict(iosNavigationUiInventoryVersion=1,complete=True,roots=[]))
        if self.root is not None:
            row=deepcopy(self.root);row.update(shown=self.address_open,visible=self.address_open)
            row['field'].update(text=self.field,visible=self.address_open,focused=self.address_open)
            value['navigationInventory']['roots']=[row]
        return value
    def post(self,request,timeout):
        response=super().post(request,timeout);receipt=self.native_boundary.receipt
        if 'status' in receipt:receipt['status']['sampleEpochMs']=self.native_epoch()
        return response
    def native(self):
        return normal_input.NativeInput(self.native_boundary,'owned-session',self.target,self.native_boundary.process,
            monotonic=lambda:self.clock,sleep=self.sleep,native_epoch_ms=self.native_epoch)


class NavigationAddressInputsTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name);self.path.chmod(0o700);self.b=RetainedBoundary()
        self.lock=ScriptSourceLock(self.path/'script-feature-sources.lock')
        self.store=PrivateFeatureState(self.path/'ios-navigation-address-42-inputs.json')
        self.native=self.b.native();self.guard=lambda:True
        self.http=patch.object(normal_input,'urlopen',self.b.post);self.http.start();self.addCleanup(self.http.stop)
    @contextmanager
    def held(self):
        caught=None
        with self.lock.held():
            try:yield
            except Exception as error:caught=error
        if caught is not None:raise caught
    def owner(self,binding=BINDING):
        return NavigationAddressInputs(self.store,binding,RUN,self.lock,self.guard,self.b.ui,self.native,
            epoch_ms=self.b.host_epoch,monotonic=lambda:self.b.clock)
    def goto(self,owner,key='enter',point='A'):
        urls=viewpoint_urls(self.b.scene);return owner.goto(key,urls[point],self.b.profile,set(urls.values()))

    def test_normal_recipe_retains_hidden_original_root_and_real_native_command_receipt_across_return(self):
        with self.held():
            owner=self.owner();value=self.goto(owner)
            self.assertEqual('retained',value['status']);self.assertFalse(value['drained'])
            lease=deepcopy(owner.state['lease']);events=owner.state['rows'][0]['intents']
            self.assertEqual(['hud.goto','address.field','replace','address.go'],[e['kind'] for e in events])
            self.assertEqual(events[2]['intent']['command']['commandId'],events[2]['receipt']['status']['commandId'])
            self.assertNotEqual(events[2]['intent']['command']['commandId'],events[2]['receipt']['commandId'])
            self.assertEqual(90000,self.b.host_epoch()-round(self.b.clock*1000))
            self.assertEqual(10000,lease['opened']['sampleEpochMs'])
            rebuilt=self.owner();again=self.goto(rebuilt,'return','B')
            self.assertEqual(lease,rebuilt.state['lease']);self.assertFalse(again['drained'])
            self.assertEqual(2,self.b.inputs.count('PhoneAddressGoButton'))
            calls=list(self.b.calls);native=list(self.b.native_boundary.requests)
            self.assertEqual(again,self.goto(self.owner(),'return','B'))
            self.assertEqual(calls,self.b.calls);self.assertEqual(native,self.b.native_boundary.requests)
            self.assertIsNotNone(self.store.read())

    def test_lost_native_or_final_result_never_repeats_any_existing_input(self):
        for fault in ('native','finish'):
            if fault!='native':self.doCleanups();self.setUp()
            with self.held():
                owner=self.owner();write=self.store.write
                def lose(value,previous):
                    row=unpack(value['payload'])[0]['rows'][-1]
                    if fault=='native' and len(row['intents'])==3 and row['intents'][2]['receipt'] is not None:raise OSError('Lost native return journal')
                    if fault=='finish' and row['phase']=='acknowledged':raise OSError('Lost completion journal')
                    return write(value,previous)
                with patch.object(self.store,'write',side_effect=lose),self.assertRaises(OSError):self.goto(owner)
                calls=list(self.b.calls);native=list(self.b.native_boundary.requests);rebuilt=self.owner()
                self.assertEqual('issued',rebuilt.state['rows'][-1]['phase'])
                with self.assertRaises(NativeUIError):self.goto(rebuilt)
                self.assertEqual(calls,self.b.calls);self.assertEqual(native,self.b.native_boundary.requests)

    def test_lost_hud_result_keeps_ordinary_opening_intent_without_inventing_root_or_replaying(self):
        with self.held():
            call=self.b.call
            def lost(method,path,body=None):
                result=call(method,path,body)
                if method=='POST' and path.endswith('/element/n0/click'):raise OSError('Lost actual HUD response')
                return result
            self.b.call=lost;owner=self.owner()
            with self.assertRaises(NativeUIError):self.goto(owner)
            rebuilt=self.owner();self.assertIsNone(rebuilt.state['lease'])
            event=rebuilt.state['rows'][0]['intents'][0];self.assertEqual('hud.goto',event['kind']);self.assertIsNone(event['receipt'])
            calls=list(self.b.calls)
            with self.assertRaises(NativeUIError):self.goto(rebuilt)
            self.assertEqual(calls,self.b.calls);self.assertTrue(self.b.address_open)
            inputs=list(self.b.inputs);current=rebuilt.observe_pending()
            self.assertEqual('visible',current['root']['status']);self.assertEqual(inputs,self.b.inputs)
            self.assertEqual('issued',self.owner().state['rows'][0]['phase'])
            self.assertIsNone(self.owner().state['rows'][0]['intents'][0]['receipt'])

    def test_preexisting_root_and_foreign_retained_text_cannot_be_taken_over(self):
        with self.held():
            self.b.root=root(shown=False,visible=False)
            with self.assertRaises(NativeUIError):self.goto(self.owner())
            self.assertEqual([],self.b.inputs)
        self.doCleanups();self.setUp()
        with self.held():
            self.goto(self.owner());self.b.field='unowned edit';before=list(self.b.inputs)
            with self.assertRaises(NativeUIError):self.goto(self.owner(),'return','B')
            self.assertEqual(before,self.b.inputs)

    def test_ignored_field_edit_is_detected_before_go_and_ignored_goto_ack_does_not_claim_arrival(self):
        self.b.mutation='text-ignored'
        with self.held():
            with self.assertRaises(NativeUIError):self.goto(self.owner())
            self.assertNotIn('PhoneAddressGoButton',self.b.inputs)
        self.doCleanups();self.setUp();self.b.mutation='goto-ignored'
        with self.held():
            before=self.b.current;result=self.goto(self.owner())
            self.assertEqual(before,self.b.current);self.assertNotIn('arrived',result);self.assertFalse(result['drained'])

    def test_mutation_is_durable_before_delivery_and_slow_journal_cannot_send_expired_input(self):
        with self.held():
            write=self.store.write
            def slow(value,previous):
                result=write(value,previous);row=unpack(value['payload'])[0]['rows'][-1]
                if row['intents'] and row['intents'][0]['receipt'] is None:self.b.clock+=2
                return result
            with patch.object(self.store,'write',side_effect=slow),self.assertRaises(NativeUIError):self.goto(self.owner())
            self.assertEqual([],self.b.inputs);self.assertIsNotNone(self.owner().state['rows'][0]['intents'][0])

    def test_changed_candidate_and_rewritten_original_root_cannot_restore_ownership(self):
        with self.held():
            self.goto(self.owner());before=list(self.b.inputs)
            with self.assertRaises(NativeUIError):self.owner(BINDING|dict(artifactSha256='0'*64))
            value=self.store.read();state=unpack(value['payload'])[0];state['lease']['rootId']=root()['rootId']
            from adapters.script_feature.history import pack
            changed=deepcopy(value);changed['payload']=pack([state]);self.store.write(changed,value)
            with self.assertRaises(NativeUIError):self.owner()
            self.assertEqual(before,self.b.inputs)


if __name__=='__main__':unittest.main()
