"""Normal restoration on original iOS UI/AFC/native seams; SDK is synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ios.self_tests.test_ios_normal_input import Boundary as InputBoundary
from ios.self_tests.test_ios_login_controls import Native as LoginNative
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from self_tests.test_native_account_observation import account_source
from adapters.normal_ui import NativeUI,NativeUIError,W3C_ELEMENT
from adapters.normal_feature_state import context
from ios.adapters import authentication_runtime as runtime_module,normal_input
from ios.adapters.authentication_runtime import IOSAuthenticationRuntime,IOSLoginControls
from ios.adapters.account_preferences import require_owned,validate_basis

RUN='a'*32;ORIGIN='https://owned.invalid'
BINDING=dict(sourceRevision='a'*40,artifactSha256='b'*64,sessionId='owned-session',generation=1,targetFingerprint='c'*64,processIdentity='42')


class Boundary(InputBoundary):
    def __init__(self):
        super().__init__();self.login=LoginNative();self.shown=False;self.source_sequence=0
        self.remember=False;self.saved='';self.references={};self.input_log=[];self.intents=[];self.ignore_clear=False
        self.observer=NativeBoundary();self.guard_okay=True
        def native(value):
            epoch=self.epoch();value.update(processId=42,requestedEpochMs=epoch,capturedEpochMs=epoch)
            value['animationFence']['requestedEpochMs']=epoch;account_source(value)
            value['account']['observation'].update(endpointSha256=hashlib.sha256(ORIGIN.encode()).hexdigest())
        self.observer.mutate=native
        self.ui=None;self.transport=None

    def epoch(self):return 20000+round(self.clock*1000)
    def sleep(self,seconds):self.clock+=seconds;self.login.qt.clock=self.clock
    def preferences(self):
        digest=hashlib.sha256(ORIGIN.encode()).hexdigest()
        return dict(accountPreferenceVersion=2,present=True,valueType='string',valueSha256=digest,canonicalOrigin=True,
            processOverridePresent=True,processOverrideSha256=digest,processOverrideCanonical=True,
            rememberPresent=True,rememberType='bool',rememberValue=self.remember,savedUsernamePresent=True,
            savedUsernameType='string',savedUsernameSha256=hashlib.sha256(self.saved.encode()).hexdigest())

    def observed(self):
        value=super().observed();self.source_sequence+=1
        login=self.login.packet();rows=deepcopy(login['controls']) if self.shown else []
        if self.shown and self.login.qt.dialog:
            rows.append(dict(id='tablet.home',token='11111111-2222-4333-8444-555555555555',enabled=True,focused=False,
                frame=dict(x=10,y=20,width=100,height=40)))
            rows.append(dict(id='account.remember',token=str(uuid.uuid5(uuid.NAMESPACE_URL,'remember-'+str(self.remember))),
                enabled=True,focused=False,preferenceControlVersion=1,checked=self.remember,
                frame=dict(x=10,y=20,width=100,height=40)))
        value.update(sampleEpochMs=self.epoch(),elapsedMs=round(self.clock*1000),tabletShown=self.shown,
            loginControlsVersion=2,generation=self.login.generation,featureControlsVersion=1,fileControlsVersion=1,
            loginClearInputVersion=1,scriptObservationVersion=1,scriptSourceSequence=self.source_sequence,
            scriptInventory=dict(inventoryVersion=1,complete=True,managers=[],pickers=[],tabletPresent=True,tabletShown=self.shown),
            accountPreferences=self.preferences(),controls=rows)
        return value

    def post(self,request,timeout):
        import json
        payload=json.loads(request.data)
        if payload['operation']=='observe':return super().post(request,timeout)
        self.requests.append(payload);native=payload['input'];assert native['operation']=='clear-login-username'
        assert 'text' not in native
        self.sequence=native['sequence'];self.input_log.append('clear-username')
        if not self.ignore_clear:self.login.qt.fields['login.username']=''
        self.receipt=dict(schemaVersion=1,commandId=payload['commandId'],status=dict(schemaVersion=1,
            commandId=native['commandId'],instance=self.instance,sequence=self.sequence,performed=True,
            processId=42,sampleEpochMs=self.epoch()))
        self.response=json.dumps(payload).encode();return self

    def call(self,method,path,body=None):
        if path.endswith('/elements'):
            identifier=body['value'];name=identifier.removeprefix('OverteNavigation.')
            found=(identifier=='OverteTabletOpen' and not self.shown or any(row['id']==name for row in self.observed()['controls']))
            if not found:return []
            key='node-'+str(len(self.references));self.references[key]=identifier;return [{W3C_ELEMENT:key}]
        identifier=self.references[path.split('/element/')[1].split('/')[0]];name=identifier.removeprefix('OverteNavigation.')
        if path.endswith('/displayed') or path.endswith('/enabled'):return True
        if path.endswith('/attribute/value'):return next(row['token'] for row in self.observed()['controls'] if row['id']==name)
        assert path.endswith('/click');self.input_log.append(name)
        if identifier=='OverteTabletOpen':self.shown=True
        elif name=='login.entry':self.login.qt.dialog=True;self.remember=True
        elif name=='login.username':self.login.qt.focused='login.username'
        elif name=='tablet.home':self.login.qt.dialog=False;self.login.qt.focused=None
        elif name=='account.remember':
            self.remember=not self.remember
            self.saved=self.login.qt.fields.get('login.username','') if self.remember else ''
        else:raise AssertionError('unreviewed restoration input')

    def make(self):
        native=normal_input.NativeInput(self,'owned-session',self.target,self.process,native_epoch_ms=self.epoch,
            monotonic=lambda:self.clock,sleep=self.sleep)
        runtime=object.__new__(IOSAuthenticationRuntime);runtime.origin=ORIGIN;runtime.run=RUN
        runtime._private_login_input=lambda *_:None
        def sources(_selector):
            native.capture()
            return dict(native=native,native_clock=self.epoch,check=lambda:self.guard_okay,client=self,session='owned-session',
                binding=BINDING,installed={},observer=SimpleNamespace(native_observer=lambda:self.native_reader()),
                preferences=self.preferences(),preferenceReceipt=deepcopy(native.last_receipt))
        runtime._sources=sources
        return runtime

    def native_reader(self):
        reader=self.observer.reader(ios=True);reader.pid=42;return reader


class IOSAuthenticationPreferenceRestoreTests(unittest.TestCase):
    def run_restore(self,remember,*,ignore_clear=False):
        b=Boundary();b.remember=remember
        with patch.object(normal_input,'urlopen',b.post), \
             patch.object(runtime_module,'NativeUI',side_effect=lambda *a,**kw:NativeUI(*a,**kw,monotonic=lambda:b.clock,sleep=b.sleep)), \
             patch.object(runtime_module,'IOSLoginControls',side_effect=lambda *a,**kw:IOSLoginControls(*a,**kw,monotonic=lambda:b.clock,sleep=b.sleep)):
            runtime=b.make();basis=runtime._preference_basis('owned')
            b.saved='e2e-'+RUN;b.remember=True;b.login.qt.fields['login.username']='e2e-'+RUN;b.ignore_clear=ignore_clear
            def intent(stage,original,control):b.intents.append(dict(stage=stage,original=deepcopy(original),control=control))
            actual=runtime._restore_account_preferences('owned',basis,intent)
        return b,basis,actual

    def test_ordinary_clear_and_checkbox_restore_both_original_remember_values(self):
        for remember in (False,True):
            with self.subTest(remember=remember):
                b,basis,actual=self.run_restore(remember)
                self.assertEqual(basis['preferences'],actual);self.assertEqual('',b.saved)
                self.assertEqual(remember,b.remember);self.assertFalse(b.login.qt.dialog)
                self.assertIn('clear-username',b.input_log)
                self.assertTrue(any(row['stage']=='account-preference-clear-username' for row in b.intents))
                self.assertTrue(all('text' not in row.get('input',{}) for row in b.requests))

    def test_ignored_clear_ack_cannot_replace_the_original_saved_username_restoration_proof(self):
        with self.assertRaises(NativeUIError):self.run_restore(True,ignore_clear=True)

    def test_historical_basis_foreign_process_or_changed_original_preference_is_rejected(self):
        b=Boundary()
        with patch.object(normal_input,'urlopen',b.post):basis=b.make()._preference_basis('owned')
        for change in (dict(binding=BINDING|dict(processIdentity='43')),dict(preferences=basis['preferences']|dict(rememberValue=True))):
            with self.assertRaises(NativeUIError):validate_basis(basis|change,ORIGIN)


if __name__=='__main__':unittest.main()
