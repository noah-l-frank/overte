"""iOS login metadata/input counterexamples; no native app or device is run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import time
import unittest
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from adapters.normal_ui import NativeUI,NativeUIError,W3C_ELEMENT
from adapters.token_login_ui import TokenLoginUI
from self_tests.test_token_login_ui import Boundary,RUN,ORIGIN,CREDS
from ios.adapters.normal_login import IOSLoginIO
from ios.adapters.normal_input import observation,NativeInput


class Native:
    def __init__(self):
        self.qt=Boundary(generic=True);self.edits=[];self.calls=[];self.references={};self.process=True
        self.instance=str(uuid.uuid4());self.generation=str(uuid.uuid4());self.mutate=lambda v:v
        self.io=IOSLoginIO(self)
        self.native=self
        self.ui=NativeUI(self,'owned-session',self.guard,monotonic=lambda:self.qt.clock,sleep=self.qt.sleep)
        self.flow=TokenLoginUI(self.io,self.qt.intent,RUN,ORIGIN,monotonic=lambda:self.qt.clock,sleep=self.qt.sleep)

    def guard(self):
        if not self.process:raise NativeUIError('Synthetic source process was lost')

    def packet(self):
        value=self.qt.capture();rows=deepcopy(value['controls'])
        for row in rows:
            row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,row['token']))
            row['frame']=dict(x=10,y=20,width=100,height=48)
        return self.mutate(dict(schemaVersion=1,instance=self.instance,generation=self.generation,loginControlsVersion=2,
            frameSpace='qt-window-logical',processId=42,sampleEpochMs=int(time.time()*1000),elapsedMs=round(self.qt.clock*1000),
            lastSequence=len(self.edits),tabletShown=True,ready=True,featureControlsVersion=1,fileControlsVersion=1,controls=rows))

    def capture(self):
        self.guard();return observation(self.packet(),42)

    def edit(self,operation,text,*,field):
        self.edits.append((operation,text,field))
        row=next(r for r in self.qt.capture()['controls'] if r['id']==field)
        self.qt.input(field,operation,text=text,token=row['token'])

    def call(self,method,path,body=None):
        self.guard();self.calls.append((method,path))
        if path.endswith('/elements'):
            identifier=body['value'].removeprefix('OverteNavigation.')
            row=next((r for r in self.capture()['controls'] if r['id']==identifier),None)
            if row is None:return []
            reference='node-'+row['token'];self.references[reference]=(identifier,row['token'])
            return [{W3C_ELEMENT:reference}]
        identifier,token=self.references[path.split('/element/')[1].split('/')[0]]
        current=next(r for r in self.capture()['controls'] if r['id']==identifier)
        if path.endswith('/displayed'):return True
        if path.endswith('/enabled'):return current['enabled']
        if path.endswith('/attribute/value'):return current['token']
        assert path.endswith('/click') and method=='POST'
        if token!=current['token']:raise NativeUIError('Original element token retired')
        row=next(r for r in self.qt.capture()['controls'] if r['id']==identifier)
        self.qt.input(identifier,'activate',token=row['token'])


class IOSLoginControlsTests(unittest.TestCase):
    def test_original_login_view_source_and_current_pointer_tokens_are_observed(self):
        n=Native();n.flow.open();page=n.flow.capture()['controls'][0]
        self.assertEqual('qml-login-v1',page['profile']);self.assertEqual('none',page['error'])
        self.assertEqual([],n.edits);self.assertEqual([('login.entry','activate')],n.qt.inputs)

    def test_ignored_pointer_input_cannot_become_an_open_login_view(self):
        n=Native();n.qt.fault='ignored'
        with self.assertRaises(NativeUIError):n.flow.open()
        self.assertFalse(n.qt.dialog)

    def test_server_field_uses_only_normal_nonsecret_edit_and_ignored_change_is_detected(self):
        n=Native();n.flow.open();n.qt.server='https://foreign.invalid';n.flow.configure_origin()
        self.assertEqual([('replace',ORIGIN,'login.server')],n.edits);self.assertEqual(ORIGIN,n.qt.server)
        n=Native();n.flow.open();n.qt.server='https://foreign.invalid';n.qt.fault='ignore-server'
        with self.assertRaises(NativeUIError):n.flow.configure_origin()
        self.assertEqual({},n.qt.fields)

    def test_private_credentials_cannot_leak_into_the_existing_public_fixture_channel(self):
        n=Native();n.flow.open()
        with self.assertRaises(NativeUIError):n.flow.fill(CREDS)
        self.assertEqual([],n.edits);self.assertEqual({},n.qt.fields)
        self.assertNotIn(CREDS['password'],repr(n.calls)+repr(n.qt.intents))

    def test_public_native_input_api_rejects_credential_fields_before_any_transport(self):
        # An uninitialized real API object proves validation precedes all
        # HTTP/capture access; no fake transport can conceal a credential post.
        native=object.__new__(NativeInput)
        for field in ('login.username','login.password'):
            with self.assertRaises(NativeUIError):native.edit('replace',CREDS['password'],field=field)
        with self.assertRaises(NativeUIError):native.edit('replace','https://user:password@foreign.invalid',field='login.server')

    def test_missing_legacy_untyped_and_foreign_source_facts_are_unavailable(self):
        for fault in ('version','generation','field','extra','process'):
            n=Native();n.flow.open()
            def change(v):
                if fault=='version':v['loginControlsVersion']=1
                elif fault=='generation':v.pop('generation')
                elif fault=='field':v['controls'][0].pop('submitEndpointSha256')
                elif fault=='extra':v['controls'][0]['password']=CREDS['password']
                else:v['processId']=99
                return v
            n.mutate=change
            with self.assertRaises(NativeUIError):n.io.capture()

    def test_context_change_and_lost_process_cannot_be_repaired_by_an_input_ack(self):
        n=Native();n.flow.open();n.generation=str(uuid.uuid4())
        with self.assertRaises(NativeUIError):n.flow.capture()
        n=Native();n.flow.open();n.process=False
        with self.assertRaises(NativeUIError):n.flow.configure_origin()

    def test_source_elapsed_clock_regression_is_not_retimed(self):
        n=Native();n.qt.clock=2;n.io.capture();n.qt.clock=1
        with self.assertRaises(NativeUIError):n.io.capture()


if __name__=='__main__':unittest.main()
