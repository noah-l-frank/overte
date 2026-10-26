"""Actual Chat token/HTTP codecs; explicit settings-page/Qt models only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid
from adapters.normal_ui import NativeUIError
from adapters.token_chat_ui import TokenChatUI,same_reference,snapshot
from self_tests.test_token_chat_ui import Widgets,RUN
from ios.adapters.normal_input import observation
from ios.self_tests.test_ios_chat_controls import IOSChatControlsTests


class SettingsWidgets(Widgets):
    def capture(self):
        value=super().capture();value['chatControlsVersion']=2
        if self.panel:
            def row(identifier):
                return dict(id=identifier,token=uuid.uuid5(uuid.NAMESPACE_URL,identifier+str(self.page_life)+self.channel).hex,
                    enabled=True,focused=False,inputReady=True)
            value['controls'].append(row('chat.settings'))
            if self.channel=='settings':
                value['controls']=[row for row in value['controls'] if row['id'] not in ('chat.input','chat.send')]
                value['controls'].append(row('chat.erase'))
        for row in value['controls']:row['token']=str(uuid.UUID(row['token']))
        return value
    def input(self,identifier,action,reference,value=None):
        if identifier not in ('chat.settings','chat.erase'):return super().input(identifier,action,reference,value)
        if self.before:self.before()
        same_reference(reference,self.capture(),identifier);self.calls.append((identifier,action,value))
        if self.ignore:return
        self.sequence+=1
        if self.ignore_effect:return
        if identifier=='chat.settings':self.channel='settings'
        else:self.local=[];self.domain=[]
        if self.lose_ack:raise NativeUIError('Declared lost ordinary Erase/settings input return')


class ChatSettingsControlTests(unittest.TestCase):
    def setUp(self):
        self.model=SettingsWidgets();self.intents=[]
        self.ui=TokenChatUI(self.model,self.intents.append,RUN,monotonic=lambda:self.model.clock,sleep=self.model.sleep)
        self.ui.open()
    def test_normal_settings_and_erase_use_consumed_inputs_without_a_storage_verdict(self):
        self.model.local=['reply-'+RUN];self.model.domain=['hidden-'+RUN]
        self.ui.settings();self.assertEqual('settings',self.model.channel);self.ui.erase_history()
        self.assertEqual([],self.model.local);self.assertEqual([],self.model.domain)
        self.assertEqual(['chat.entry','chat.settings','chat.erase'],[row[0] for row in self.model.calls])
        self.assertEqual(3,len(self.intents));self.assertNotIn('restored',str(self.intents))
    def test_literal_one_cannot_admit_extended_controls_or_request_erase(self):
        value=self.ui.capture();value['chatControlsVersion']=1
        with self.assertRaises(NativeUIError):snapshot(value)
        original=self.model.capture
        self.model.capture=lambda:dict(original(),chatControlsVersion=1,controls=[row for row in original()['controls'] if row['id']!='chat.settings'])
        calls=deepcopy(self.model.calls)
        with self.assertRaises(NativeUIError):self.ui.settings()
        self.assertEqual(calls,self.model.calls)
    def test_ignored_settings_or_erase_effect_remains_unavailable(self):
        self.model.ignore_effect=True
        with self.assertRaises(NativeUIError):self.ui.settings()
        self.assertEqual('local',self.model.channel)
        self.model.ignore_effect=False;self.ui.settings();self.model.local=['reply-'+RUN];self.model.ignore_effect=True
        with self.assertRaises(NativeUIError):self.ui.erase_history()
        self.assertEqual(['reply-'+RUN],self.model.local)
    def test_uncertain_erase_returns_once_and_does_not_retry_inside_the_recipe(self):
        self.ui.settings();self.model.local=['reply-'+RUN];self.model.lose_ack=True
        with self.assertRaises(NativeUIError):self.ui.erase_history()
        self.assertEqual(1,sum(row[0]=='chat.erase' for row in self.model.calls));self.assertEqual([],self.model.local)
    def test_version_or_page_change_cannot_retarget_an_original_erase_reference(self):
        self.ui.settings();reference=self.ui.capture();self.model.channel='local'
        with self.assertRaises(NativeUIError):same_reference(reference,self.ui.capture(),'chat.erase')
        self.model.channel='settings';changed=deepcopy(reference);changed['chatControlsVersion']=1
        with self.assertRaises(NativeUIError):same_reference(changed,self.ui.capture(),'chat.erase')
        old=deepcopy(reference);old['controls']=[row for row in old['controls'] if row['id'] not in ('chat.settings','chat.erase')]
        current=deepcopy(old);old['chatControlsVersion']=1
        with self.assertRaises(NativeUIError):same_reference(old,current,'chat.local')


class IOSChatSettingsTransportTests(unittest.TestCase):
    def setUp(self):
        self.f=IOSChatControlsTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        model=self.f.widget=SettingsWidgets();model.panel=True;model.pid=42;model.instance=self.f.native.instance
        model.generation='22222222-2222-4222-8222-222222222222';self.f.marker=2
        capture=model.capture
        def original():
            value=capture()
            for row in value['controls']:
                if row['id'].startswith('tablet.'):row.pop('inputReady',None)
            return value
        model.capture=original
    def test_actual_normal_native_transport_admits_settings_and_erase_as_single_pointer_inputs(self):
        f=self.f;f.widget.local=['reply-'+RUN];f.flow.settings();f.flow.erase_history()
        self.assertEqual([],f.widget.local);self.assertEqual(['chat.settings','chat.erase'],[row[0] for row in f.widget.calls])
        edits=[command['input'] for command in f.native.commands if command.get('operation')=='edit']
        self.assertEqual(['activate','activate'],[row['operation'] for row in edits]);self.assertEqual([1,2],[row['sequence'] for row in edits])
    def test_literal_one_native_envelope_cannot_smuggle_a_settings_control(self):
        original=self.f.observed();original['chatControlsVersion']=1
        with self.assertRaises(NativeUIError):observation(original,42,self.f.native.epoch())
        self.assertEqual([],self.f.widget.calls)


if __name__=='__main__':unittest.main()
