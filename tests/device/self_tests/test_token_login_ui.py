"""Device-free counterexamples for normal login input, not product acceptance."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.token_login_ui import TokenLoginUI
from adapters.normal_ui import NativeUIError

RUN='a'*32
ORIGIN='https://owned.invalid'
CREDS={'username':'e2e-'+RUN,'password':'private-synthetic-input'}


class Boundary:
    def __init__(self,generic=False):
        self.generic=generic;self.server=ORIGIN
        self.clock=0.;self.instance='b'*32;self.generation='c'*32;self.account='d'*32
        self.endpoint=hashlib.sha256(ORIGIN.encode()).hexdigest();self.account_generation=1
        self.dialog=False;self.waiting=False;self.pending=False;self.token=False;self.domain=False;self.closing=False
        self.error='none';self.focused=None;self.fields={};self.inputs=[];self.intents=[];self.fault=''
        self.transform=lambda v:v
        self.ui=TokenLoginUI(self,self.intent,RUN,ORIGIN,monotonic=lambda:self.clock,sleep=self.sleep)

    def sleep(self,value):self.clock+=value
    def intent(self,verb,value,identifier):
        if self.fault=='intent':raise RuntimeError('Private journal unavailable')
        self.intents.append((verb,deepcopy(value),identifier))

    def capture(self):
        def row(identifier,ready=True,**extra):
            # Actual independent boundary state determines token and metadata.
            source=repr((identifier,self.dialog,self.waiting,self.pending,self.token,self.domain,self.closing,self.endpoint,self.account_generation,self.server))
            return dict(id=identifier,token=hashlib.sha256(source.encode()).hexdigest()[:32],enabled=True,
                focused=self.focused==identifier,inputReady=ready,**extra)
        if self.dialog:
            rows=[row('login.page',False,profile='qml-login-v1' if self.generic else 'phone-login-v1',
                stage='pending' if self.waiting else 'credentials',
                submitEndpointSha256=hashlib.sha256(self.server.encode()).hexdigest() if self.generic else self.endpoint,domain=self.domain,waiting=self.waiting,closing=self.closing,
                error=self.error,accountInstance=self.account,credentialGeneration=self.account_generation,
                endpointSha256=self.endpoint,nativePending=self.pending,tokenPresent=self.token)]
            ready=not any((self.waiting,self.pending,self.token,self.domain,self.closing))
            if self.generic:rows.append(row('login.server',ready))
            ready=ready and (not self.generic or self.server==ORIGIN)
            rows += [row('login.'+v,ready) for v in ('username','password','submit')]
            if not self.generic:rows += [row('login.cancel',not self.domain and not self.closing)]
        else:rows=[row('login.entry',not self.token)]
        return self.transform(dict(loginControlsVersion=2,ready=True,instance=self.instance,generation=self.generation,controls=rows))

    def input(self,identifier,action,*,token,text=None):
        if self.fault=='late-endpoint':self.endpoint='f'*64
        original=next(row for row in self.capture()['controls'] if row['id']==identifier)
        if original['token']!=token or not original['inputReady']:raise NativeUIError('Native current control refuses old intent')
        assert len(self.intents)==len(self.inputs)+1
        self.inputs.append((identifier,action)) # Secrets intentionally absent from input history.
        if self.fault=='ignored':return
        if action=='activate':
            if identifier=='login.entry':self.dialog=True
            elif identifier=='login.cancel':self.dialog=False;self.error='none';self.fields={};self.focused=None
            elif identifier in ('login.username','login.password','login.server'):self.focused=identifier
        elif action=='replace':
            if identifier=='login.server':
                if self.fault!='ignore-server':self.server=text
            else:self.fields[identifier]=text
        elif action=='submit':
            self.waiting=True;self.pending=True
        if self.fault=='uncertain':raise NativeUIError('Delivery response lost')

    def close_view(self):
        assert self.generic and self.intents[-1][0]=='login-close'
        self.inputs.append(('tablet.home','activate'))
        if self.fault!='ignored':self.dialog=False;self.error='none';self.focused=None;self.fields={}


class LoginUITests(unittest.TestCase):
    def test_original_fields_receive_private_input_without_a_login_verdict(self):
        b=Boundary();b.ui.open();b.ui.fill(CREDS);b.ui.submit()
        self.assertEqual(CREDS['password'],b.fields['login.password']);self.assertTrue(b.pending)
        self.assertFalse(b.token);self.assertEqual('none',b.ui.capture()['controls'][0]['error'])
        self.assertNotIn(CREDS['password'],repr(b.intents)+repr(b.inputs)+repr(b.ui.capture()))

    def test_pending_view_close_and_reopen_does_not_abort_the_real_request(self):
        b=Boundary();b.ui.open();b.ui.fill(CREDS);b.ui.submit();b.ui.cancel();b.ui.open()
        page=b.ui.capture()['controls'][0]
        self.assertTrue(page['waiting']);self.assertTrue(page['nativePending'])
        self.assertEqual(1,sum(action=='submit' for _,action in b.inputs))
        with self.assertRaises(NativeUIError):b.ui.fill(CREDS)
        b.ui.cancel();count=len(b.inputs);b.ui.cancel();self.assertEqual(count,len(b.inputs))

    def test_ignored_open_focus_and_cancel_fail_from_actual_followup_observations(self):
        for stage in ('open','focus','cancel'):
            with self.subTest(stage=stage):
                b=Boundary()
                if stage!='open':b.ui.open()
                b.fault='ignored'
                with self.assertRaises(NativeUIError):
                    if stage=='open':b.ui.open()
                    elif stage=='focus':b.ui.fill(CREDS)
                    else:b.ui.cancel()
                self.assertLessEqual(b.clock,10.01)

    def test_input_intent_failure_prevents_delivery_and_uncertain_delivery_is_not_replayed(self):
        b=Boundary();b.fault='intent'
        with self.assertRaises(RuntimeError):b.ui.open()
        self.assertEqual([],b.inputs)
        b=Boundary();b.fault='uncertain'
        with self.assertRaises(NativeUIError):b.ui.open()
        self.assertEqual(1,len(b.inputs))

    def test_domain_or_foreign_origin_cannot_receive_credentials(self):
        for kind in ('domain','endpoint','token','pending','closing'):
            with self.subTest(kind=kind):
                b=Boundary();b.ui.open();b.inputs=[];b.intents=[]
                if kind=='endpoint':b.endpoint='e'*64
                elif kind=='token':b.token=True
                else:setattr(b,kind,True)
                with self.assertRaises(NativeUIError):b.ui.fill(CREDS)
                self.assertEqual([],b.inputs);self.assertEqual({},b.fields)

    def test_changed_endpoint_between_observation_and_delivery_refuses_original_token(self):
        b=Boundary();b.ui.open();b.fault='late-endpoint'
        with self.assertRaises(NativeUIError):b.ui.fill(CREDS)
        self.assertEqual({},b.fields)

    def test_foreign_and_unreviewed_text_is_rejected_without_public_secret_errors(self):
        for value in (dict(CREDS,username='other'),dict(CREDS,password='bad\ninput'),dict(CREDS,password='\ue007'),
                      dict(CREDS,password='x'*4097),dict(CREDS,password=''),dict(CREDS,expected='owned')):
            b=Boundary();b.ui.open();count=len(b.inputs)
            with self.assertRaises(NativeUIError) as error:b.ui.fill(value)
            self.assertEqual(count,len(b.inputs));self.assertNotIn(str(value),str(error.exception))

    def test_missing_and_forged_ui_facts_cannot_become_observed_error_or_readiness(self):
        mutations=(lambda v:v['controls'][0].update(error='unavailable'),
            lambda v:v['controls'][0].update(nativePending=True),
            lambda v:v['controls'][0].update(credentialGeneration=True),
            lambda v:v['controls'][0].update(password='private'),
            lambda v:v['controls'].append(deepcopy(v['controls'][1])),
            lambda v:v['controls'].pop(0),lambda v:v.update(loginControlsVersion=0))
        for mutate in mutations:
            b=Boundary();b.ui.open()
            def change(v):mutate(v);return v
            b.transform=change
            with self.assertRaises(NativeUIError):b.ui.capture()

    def test_original_account_and_ui_identity_cannot_regress_or_switch(self):
        for kind in ('account','instance','generation','account_generation'):
            b=Boundary();b.ui.open()
            if kind=='account_generation':b.account_generation=2;b.ui.capture();b.account_generation=1
            else:setattr(b,kind,'e'*32)
            with self.assertRaises(NativeUIError):b.ui.capture()

    def test_invalid_error_is_read_from_original_ui_and_no_result_is_injected(self):
        b=Boundary();b.ui.open();b.error='invalid-credentials'
        self.assertEqual('invalid-credentials',b.ui.capture()['controls'][0]['error'])
        self.assertEqual(1,len(b.inputs))

    def test_generic_server_field_is_observed_and_changed_by_normal_input_before_credentials(self):
        b=Boundary(generic=True);b.server='https://foreign.invalid';b.ui.open();b.ui.fill(CREDS)
        self.assertEqual(ORIGIN,b.server);self.assertEqual(CREDS['password'],b.fields['login.password'])
        server=next(i for i,v in enumerate(b.inputs) if v==('login.server','replace'))
        secret=next(i for i,v in enumerate(b.inputs) if v==('login.password','replace'))
        self.assertLess(server,secret);self.assertNotIn(CREDS['password'],repr(b.intents))

    def test_ignored_generic_server_input_and_forged_target_readiness_cannot_release_credentials(self):
        b=Boundary(generic=True);b.server='https://foreign.invalid';b.fault='ignore-server';b.ui.open()
        with self.assertRaises(NativeUIError):b.ui.fill(CREDS)
        self.assertEqual({},b.fields)
        b=Boundary(generic=True);b.ui.open()
        def forged(v):v['controls'][0]['submitEndpointSha256']='f'*64;return v
        b.transform=forged
        with self.assertRaises(NativeUIError):b.ui.capture()

    def test_generic_pending_view_closes_through_real_navigation_and_ignored_navigation_is_detected(self):
        b=Boundary(generic=True);b.ui.open();b.ui.fill(CREDS);b.ui.submit();b.ui.cancel()
        self.assertFalse(b.dialog);self.assertTrue(b.pending);self.assertIn(('tablet.home','activate'),b.inputs)
        b.ui.open();self.assertTrue(b.pending);b.fault='ignored'
        with self.assertRaises(NativeUIError):b.ui.cancel()
        self.assertTrue(b.dialog)

    def test_generic_profile_missing_server_source_or_legacy_version_fails_before_credentials(self):
        for fault in ('missing-server','legacy','foreign-stage'):
            b=Boundary(generic=True);b.ui.open()
            def change(v):
                if fault=='missing-server':v['controls']=[r for r in v['controls'] if r['id']!='login.server'];v['controls'][0]['submitEndpointSha256']='f'*64
                elif fault=='legacy':v['loginControlsVersion']=1
                else:v['controls'][0]['stage']='requested-success'
                return v
            b.transform=change
            with self.assertRaises(NativeUIError):b.ui.fill(CREDS)
            self.assertEqual({},b.fields)

    def test_native_account_and_server_targets_are_separate_required_measurements(self):
        b=Boundary(generic=True);b.ui.open();b.endpoint='f'*64
        with self.assertRaises(NativeUIError):b.ui.fill(CREDS)
        self.assertEqual({},b.fields)

    def test_reversed_or_stalled_clock_is_bounded(self):
        b=Boundary();b.ui.now();b.clock=-1
        with self.assertRaises(NativeUIError):b.ui.now()
        b=Boundary();b.fault='ignored';b.ui.sleep=lambda _:None
        with self.assertRaises(NativeUIError):b.ui.open()
        self.assertEqual(1,len(b.inputs))
