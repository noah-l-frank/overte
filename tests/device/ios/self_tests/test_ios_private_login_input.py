"""Original iOS factories/private transport at synthetic native/Qt/AFC seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from functools import partial
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch
import uuid
import test_ios_normal_scripts as sources
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from adapters.private_login_input import PrivateLoginInput as Owner,FILE
from self_tests.test_private_login_input import Boundary as FileBoundary
from self_tests.test_token_login_ui import Boundary as LoginBoundary,RUN,ORIGIN,CREDS
from adapters.token_login_ui import TokenLoginUI
from adapters.normal_ui import NativeUIError
from ios.adapters import adapter as component
from ios.adapters.feature_observation import FeatureObservation
from adapters.ios import binding as canonical


class IOSPrivateInputTests(unittest.TestCase):
    def setUp(self):
        self.fixture=sources.IOSNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.adapter=self.fixture.adapter;self.native=self.fixture.native
        self.login=LoginBoundary(generic=True);self.native.qt.opened=True
        root=self.fixture.path.parent/'private-native-input';root.mkdir(mode=0o700)
        self.core=FileBoundary(root,self.adapter.private_login_input_store('owned'));self.addCleanup(self.core.close)
        self.native_generation=str(uuid.uuid4());self.private_calls=[]
        controls_original=self.native.controls;observed_original=self.native.observed
        post_original=self.native.post;execute_original=self.native.execute;call_original=self.native.call
        def controls():
            rows=deepcopy(self.login.capture()['controls'])
            if self.login.dialog:rows.append(dict(id='tablet.home',token='e'*32,enabled=True,focused=False))
            for row in rows:
                row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,row['token']));row['frame']=dict(x=10,y=20,width=200,height=48)
            return rows
        def observed():
            value=observed_original();value.update(loginControlsVersion=2,generation=self.native_generation,controls=controls())
            return value
        def post(request,timeout):
            value=json.loads(request.data)
            if value['action']!='feature-private-login-input':return post_original(request,timeout)
            self.native.fixture.set_client_command(value);self.native.commands.append(deepcopy(value))
            self.native.echo=json.dumps(value).encode()
            payload=None
            if value['operation']=='deliver' and self.core.path(value).exists():
                try:payload=json.loads(self.core.path(value).read_bytes())['input']
                except (ValueError,KeyError):pass
            self.core.send(value)
            state=self.core.value['source']
            if value['operation']=='deliver' and self.core.value['available'] and payload is not None and 'inputStatus' in state:
                rows=[r for r in controls() if r['token']==payload['fieldToken'] and r['id'] in ('login.username','login.password')]
                valid=(len(rows)==1 and rows[0]['focused'] and rows[0]['inputReady'] and payload['instance']==self.native.instance
                    and payload['sequence']==self.native.sequence+1)
                if valid:
                    self.native.sequence+=1;row=next(r for r in self.login.capture()['controls'] if r['id']==rows[0]['id'])
                    old_fault=self.login.fault
                    if self.core.fault=='ignored-ui':self.login.fault='ignored'
                    self.login.input(rows[0]['id'],'replace',token=row['token'],text=payload['text'])
                    self.login.fault=old_fault
                status=self.core.rows[value['inputId']]['inputStatus']
                status['performed']=valid and self.login.fields.get(rows[0]['id'])==payload['text']
                state['inputStatus']=deepcopy(status)
            return self.native
        def execute(session,operation,values):
            if operation=='mobile: pushFile':
                name=values['remotePath'].rsplit('/',1)[1];self.private_calls.append((operation,name))
                self.core.write(name,base64.b64decode(values['payload'],validate=True));return None
            if operation=='mobile: pullFile':
                name=values['remotePath'].rsplit('/',1)[1]
                if name==FILE:return base64.b64encode(self.core.read().encode()).decode()
                if name.startswith('feature-login-input-'):
                    self.private_calls.append((operation,name))
                    raw=self.core.drain(name) if getattr(self.core,'deferred',None) is not None else self.core.original(name)
                    return base64.b64encode(raw).decode()
            return execute_original(session,operation,values)
        def call(method,path,body=None):
            if path.endswith('/click'):
                reference=path.split('/element/')[1].split('/')[0];name,token=self.native.elements[reference]
                if name.startswith('login.') or name=='tablet.home':
                    current=next(r for r in controls() if r['id']==name)
                    if current['token']!=token:raise NativeUIError('Retired synthetic native control')
                    if name=='tablet.home':self.login.close_view()
                    elif name=='login.submit':
                        original=next(r for r in self.login.capture()['controls'] if r['id']=='login.password')
                        self.login.input('login.password','submit',token=original['token'])
                    else:
                        original=next(r for r in self.login.capture()['controls'] if r['id']==name)
                        self.login.input(name,'activate',token=original['token'])
                    return None
            return call_original(method,path,body)
        for boundary in (patch.object(self.native,'controls',side_effect=controls),patch.object(self.native,'observed',side_effect=observed),
            patch.object(self.native,'post',side_effect=post),patch('ios.adapters.feature_observation.post_request',side_effect=post),
            patch.object(self.native,'execute',side_effect=execute),
            patch.object(self.native,'call',side_effect=call),
            patch.object(component,'FeatureObservation',partial(FeatureObservation,monotonic=lambda:self.login.clock,sleep=self.login.sleep)),
            patch('adapters.private_login_input.PrivateLoginInput',partial(Owner,monotonic=lambda:self.login.clock,sleep=self.login.sleep)),
            patch('adapters.token_login_ui.TokenLoginUI',partial(TokenLoginUI,monotonic=lambda:self.login.clock,sleep=self.login.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        self.flow=self.adapter._login_controls('owned',self.login.intent,RUN,ORIGIN)

    def test_private_original_bytes_fill_native_fields_and_submit_without_public_credential_payload(self):
        self.flow.open();self.flow.fill(CREDS);self.flow.submit()
        self.assertEqual(CREDS['password'],self.login.fields['login.password']);self.assertTrue(self.login.pending)
        self.assertIsNone(self.adapter.private_login_input_store('owned').read())
        self.assertEqual(2,sum(op=='mobile: pushFile' for op,_ in self.private_calls))
        self.assertNotIn(CREDS['password'],repr(self.native.commands)+repr(self.core.value)+repr(self.login.intents))
        self.assertTrue(all(r['fd'] is None for r in self.core.rows.values()))

    def test_private_push_ack_without_real_app_file_never_delivers_a_credential(self):
        self.flow.open();self.core.fault='push-ack'
        with self.assertRaises(NativeUIError):self.flow.fill(CREDS)
        self.assertEqual({},self.login.fields);self.assertIsNone(self.adapter.private_login_input_store('owned').read())

    def test_acknowledged_but_ignored_actual_field_input_is_not_promoted_to_success(self):
        self.flow.open();self.core.fault='ignored-ui'
        with self.assertRaises(NativeUIError):self.flow.fill(CREDS)
        self.assertEqual({},self.login.fields);self.assertIsNone(self.adapter.private_login_input_store('owned').read())
        self.assertFalse(self.login.pending)

    def test_foreign_copied_private_file_is_not_adopted_or_deleted(self):
        self.flow.open();self.core.fault='foreign-inode'
        with self.assertRaises(NativeUIError):self.flow.fill(CREDS)
        owned=self.adapter.private_login_input_store('owned').read();self.assertIsNotNone(owned)
        self.assertEqual({},self.login.fields);self.assertTrue(list(self.core.root.glob('feature-login-input-*')))

    def test_false_native_cleanup_ack_retains_journal_even_after_a_real_field_edit(self):
        self.flow.open();self.core.fault='cleanup-ack'
        with self.assertRaises(NativeUIError):self.flow.fill(CREDS)
        self.assertIsNotNone(self.adapter.private_login_input_store('owned').read());self.assertIn('login.username',self.login.fields)
        self.core.fault='';self.adapter._private_login_input('owned',RUN).retire()
        self.assertIsNone(self.adapter.private_login_input_store('owned').read())

    def test_missing_original_native_result_refuses_to_promote_an_input_ack(self):
        self.flow.open();self.core.fault='missing-result'
        with self.assertRaises(NativeUIError):self.flow.fill(CREDS)
        self.assertIsNone(self.adapter.private_login_input_store('owned').read())

    def test_private_transfer_cleanup_is_reached_before_original_session_teardown(self):
        self.flow.open();self.core.fault='cleanup-ack'
        with self.assertRaises(NativeUIError):self.flow.fill(CREDS)
        self.core.fault='';self.assertEqual({'cleaned':True},self.adapter.cleanup('owned'))
        self.assertFalse(self.native.running);self.assertIsNone(self.adapter.private_login_input_store('owned').read())

    def test_incomplete_private_cleanup_still_reaches_base_teardown_and_cannot_pass(self):
        self.flow.open();self.core.fault='foreign-inode'
        with self.assertRaises(NativeUIError):self.flow.fill(CREDS)
        with self.assertRaises((ValueError,RuntimeError)):self.adapter.cleanup('owned')
        self.assertFalse(self.native.running);self.assertIsNotNone(self.adapter.private_login_input_store('owned').read())

    def test_pending_native_view_closes_and_reopens_without_replaying_private_credentials(self):
        self.flow.open();self.flow.fill(CREDS);self.flow.submit();count=len(self.private_calls)
        self.flow.cancel();self.flow.open();self.assertTrue(self.login.pending)
        self.assertEqual(count,len(self.private_calls))

    def test_lost_upload_waits_for_actual_serialized_private_completion_before_retirement(self):
        self.flow.open();self.core.fault='late-push'
        with self.assertRaises(NativeUIError):self.flow.fill(CREDS)
        self.assertEqual(1,self.core.drains);self.assertIsNone(self.core.deferred)
        self.assertEqual({},self.login.fields);self.assertIsNone(self.adapter.private_login_input_store('owned').read())

    def test_unresolved_private_completion_fence_keeps_pending_intent_and_blocks_retirement(self):
        self.flow.open();self.core.fault='drain-error'
        with self.assertRaises(NativeUIError):self.flow.fill(CREDS)
        self.assertTrue(self.adapter.private_login_input_store('owned').read()['transferPending'])
        self.assertFalse(any(c['operation']=='retire' for c in self.core.commands))
        with self.assertRaises((ValueError,RuntimeError)):self.adapter.cleanup('owned')
        self.assertFalse(self.native.running);self.assertTrue(self.adapter.private_login_input_store('owned').read()['transferPending'])

    def test_canonical_binding_keeps_both_new_private_factories_unavailable(self):
        with patch.object(component.AppiumAdapter,'load_targets',return_value={}):
            adapter=canonical.create_adapter(SimpleNamespace(platform='ios',action='cleanup'),component.AppiumAdapter)
        for name in ('_private_login_input','_login_controls'):
            with self.assertRaisesRegex(ValueError,'INSTALLED_CODE_BINDING_UNAVAILABLE'):getattr(adapter,name)('unread')


if __name__=='__main__':unittest.main()
