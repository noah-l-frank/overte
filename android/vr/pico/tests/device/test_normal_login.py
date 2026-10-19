"""Pico wrapper login control/cleanup checks at synthetic native boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid
import test_normal_scripts as sources
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.token_login_ui import TokenLoginUI
from self_tests.test_token_login_ui import Boundary,RUN,ORIGIN,CREDS


class PicoLoginTests(unittest.TestCase):
    def setUp(self):
        self.fixture=sources.PicoNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.instance=self.fixture.instance;self.native=self.fixture.native
        self.ui=Boundary(generic=True);self.native.opened=True
        self.raw_command='{}\n';self.fault='';self.marker=2
        snapshot_original=self.native.snapshot;write_original=self.native.write_debug_app_file;read_original=self.native.read_debug_app_file
        def snapshot():
            value=snapshot_original();actual=self.ui.capture();value['loginControlsVersion']=self.marker
            value['controls']=deepcopy(actual['controls'])
            if self.ui.dialog:value['controls'].append(dict(id='tablet.home',token='e'*32,enabled=True,focused=False))
            for row in value['controls']:row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,row['token']))
            return value
        def write(target,package,path,raw):
            if path!='files/overte-e2e/navigation-ui-command.json':return write_original(target,package,path,raw)
            command=json.loads(raw)
            if command=={}:
                if self.fault!='ignore-clear':self.raw_command=raw
                return
            self.raw_command=raw
            current=snapshot();row=next(r for r in current['controls'] if r['id']==command['controlId'])
            self.assertEqual(row['token'],command['controlToken']);self.assertEqual(self.native.sequence+1,command['sequence'])
            self.native.sequence+=1;safe=deepcopy(command);safe.pop('text',None);self.native.inputs.append(safe)
            if command['controlId']=='tablet.home':self.ui.close_view()
            else:
                original=next(r for r in self.ui.capture()['controls'] if r['id']==command['controlId'])
                self.ui.input(command['controlId'],command['action'],token=original['token'],text=command.get('text'))
            self.native.status=dict(schemaVersion=1,bridgeId=current['bridgeId'],commandId=command['commandId'],
                sequence=command['sequence'],performed=True,error='',processId=123,updatedEpochMs=self.native.epoch_milliseconds(target))
            if self.fault=='lost-replace' and command['action']=='replace':self.native.status['commandId']=str(uuid.uuid4())
        def read(target,package,path,**kwargs):
            if path=='files/overte-e2e/navigation-ui-command.json':return self.raw_command
            return read_original(target,package,path,**kwargs)
        for boundary in (patch.object(self.native,'snapshot',side_effect=snapshot),
                         patch.object(self.native,'write_debug_app_file',side_effect=write),
                         patch.object(self.native,'read_debug_app_file',side_effect=read),
                         patch('adapters.token_login_ui.TokenLoginUI',partial(TokenLoginUI,
                             monotonic=lambda:self.ui.clock,sleep=self.ui.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        self.flow=self.instance._login_controls(self.native.target,self.ui.intent,RUN,ORIGIN)

    def test_actual_bound_route_uses_ordinary_fields_and_submit_without_a_login_verdict(self):
        self.flow.open();self.flow.fill(CREDS);self.assertEqual('{}\n',self.raw_command);self.flow.submit()
        self.assertTrue(self.ui.pending);self.assertFalse(self.ui.token)
        self.assertEqual(CREDS['password'],self.ui.fields['login.password'])
        self.assertNotIn(CREDS['password'],repr(self.native.inputs)+repr(self.ui.intents))

    def test_pending_generic_page_closes_through_home_and_reopens_without_request_replay(self):
        self.flow.open();self.flow.fill(CREDS);self.flow.submit();self.flow.cancel();self.flow.open()
        self.assertTrue(self.ui.pending);self.assertEqual(1,sum(r['action']=='submit' for r in self.native.inputs))
        self.assertIn('tablet.home',[r['controlId'] for r in self.native.inputs])

    def test_ignored_generic_origin_edit_cannot_deliver_private_credentials(self):
        self.flow.open();self.ui.server='https://foreign.invalid';self.ui.fault='ignore-server'
        with self.assertRaises(RuntimeError):self.flow.fill(CREDS)
        self.assertEqual({},self.ui.fields);self.assertEqual('{}\n',self.raw_command)

    def test_private_command_ack_without_actual_replacement_keeps_intent_and_fails(self):
        self.flow.open();self.fault='ignore-clear'
        with self.assertRaises(RuntimeError):self.flow.fill(CREDS)
        self.assertIn('text',json.loads(self.raw_command));self.assertEqual('login-replace',self.ui.intents[-1][0])
        self.assertFalse(self.ui.token)

    def test_uncertain_secret_input_is_not_replayed_and_actual_private_command_is_cleared(self):
        self.flow.open();self.fault='lost-replace'
        with self.assertRaises(RuntimeError):self.flow.fill(CREDS)
        self.assertEqual('{}\n',self.raw_command)
        self.assertEqual(1,sum(r['action']=='replace' for r in self.native.inputs));self.assertFalse(self.ui.token)

    def test_candidate_change_refuses_before_new_private_input(self):
        self.flow.open();before=len(self.native.inputs);self.native.digest='f'*64
        with self.assertRaises((ValueError,RuntimeError)):self.flow.fill(CREDS)
        self.assertEqual(before,len(self.native.inputs));self.assertEqual({},self.ui.fields)

    def test_legacy_native_controls_cannot_receive_credentials(self):
        self.marker=1
        with self.assertRaises((ValueError,RuntimeError)):self.flow.open()
        self.assertEqual([],self.native.inputs)

    def test_wrong_native_endpoint_and_domain_are_not_copied_from_owned_inputs(self):
        self.flow.open();self.ui.endpoint='f'*64
        with self.assertRaises(RuntimeError):self.flow.fill(CREDS)
        self.assertEqual({},self.ui.fields)

    def test_ignored_home_close_keeps_pending_dialog_and_fails(self):
        self.flow.open();self.ui.fault='ignored'
        with self.assertRaises(RuntimeError):self.flow.cancel()
        self.assertTrue(self.ui.dialog)


if __name__=='__main__':unittest.main()
