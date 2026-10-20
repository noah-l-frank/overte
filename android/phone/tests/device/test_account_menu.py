"""Actual normal-menu recipe with synthetic W3C/native sources only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(ROOT/'tests/device/adapters/android-phone'))
from overte_phone_account_menu import PhoneAccountMenu
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_ui import NativeUI,W3C_ELEMENT,NativeUIError
from self_tests.test_native_feature_observation import Boundary
from self_tests.test_native_account_observation import account

RUN='a'*32
ORIGIN='https://owned.invalid'
PACKAGE='io.github.noah_be.overte.phone'


class MenuClient:
    def __init__(self):
        self.panel=None;self.logged=True;self.inputs=[];self.ignore='';self.package=PACKAGE
        self.clock=0.;self.refs={};self.duplicate=False;self.page=1;self.menu_page=1;self.after_click=None

    def rows(self):
        if self.panel is None:return [('tablet.open','')]
        common=[('nav.close','')]
        if self.panel=='home':
            return common+[('tabletPage.1',''),('tabletPage.2','')]+([('','MENU')] if self.page==self.menu_page else [])
        if self.panel=='menu':return common+[('nav.home',''),('','File')]
        if self.panel=='file':
            return common+[('nav.home',''),('','Directory Service: Logout e2e-'+RUN if self.logged else 'Directory Service: Log In / Sign Up')]
        return common+[('nav.home','')]

    def call(self,method,path,body=None):
        if path.endswith('/source'):
            root=ET.Element('hierarchy')
            for resource,label in self.rows():
                ET.SubElement(root,'node',{'package':self.package,'class':'android.widget.Button','displayed':'true',
                    'enabled':'true','resource-id':PACKAGE+':id/'+resource if resource else '',
                    'content-desc':label,'text':label})
            return ET.tostring(root,encoding='unicode')
        if path.endswith('/elements'):
            rows=[row for row in self.rows() if (PACKAGE+':id/'+row[0] if body['using']=='id' else row[1])==body['value']]
            if not rows:return []
            ref='row-'+str(len(self.refs));self.refs[ref]=rows[0]
            return [{W3C_ELEMENT:ref}]*(2 if self.duplicate else 1)
        if '/element/' in path:
            ref=path.split('/element/',1)[1].split('/')[0];row=self.refs[ref]
            if path.endswith('/displayed'):return row in self.rows()
            if path.endswith('/enabled'):return True
            if path.endswith('/click'):
                resource,label=row;self.inputs.append(row)
                stage='logout' if label.startswith('Directory Service: Logout') else label or resource
                if stage==self.ignore:return None
                if resource=='tablet.open' or resource=='nav.home':self.panel='home'
                elif resource=='nav.close':self.panel=None
                elif resource.startswith('tabletPage.'):self.page=int(resource.rsplit('.',1)[1])
                elif label=='MENU':self.panel='menu'
                elif label=='File':self.panel='file'
                elif stage=='logout':self.logged=False
                else:raise AssertionError('Unexpected synthetic normal control')
                if self.after_click:self.after_click(stage)
                return None
        raise AssertionError('Unexpected synthetic SDK request')


class AccountMenuTests(unittest.TestCase):
    def setUp(self):
        self.client=MenuClient();self.boundary=Boundary();self.intents=[];self.native_edits={}
        def mutate(packet):
            packet['processId']=31;value=account()
            value.update(loggedIn=self.client.logged,principalSha256=hashlib.sha256(('e2e-'+RUN).encode()).hexdigest())
            value['observation'].update(endpointSha256=hashlib.sha256(ORIGIN.encode()).hexdigest(),
                tokenPresent=self.client.logged,tokenValid=self.client.logged,refreshPresent=self.client.logged)
            for key,item in self.native_edits.items():
                if key in value:value[key]=item
                else:value['observation'][key]=item
            packet['account']=value
        self.boundary.mutate=mutate
        self.source=NativeFeatureObservation(self.boundary.send,self.boundary.original,lambda:20000,
            self.boundary.guard,31,monotonic=lambda:self.boundary.clock,sleep=self.boundary.sleep)
        self.ui=NativeUI(self.client,'native-session',self.boundary.guard,timeout=.6,
            monotonic=lambda:self.client.clock,sleep=self.sleep)
        self.menu=PhoneAccountMenu(self.ui,self.source,self.intent,RUN,ORIGIN)

    def sleep(self,value):self.client.clock+=value
    def intent(self,verb,original,stage):self.intents.append((verb,deepcopy(original),stage))

    def test_normal_tablet_menu_file_logout_has_original_native_barriers_and_no_service_mutation(self):
        self.assertEqual({'performed':True},self.menu.logout())
        self.assertEqual(['tablet.open','MENU','File','Directory Service: Logout e2e-'+RUN],
            [resource or label for resource,label in self.client.inputs])
        self.assertEqual(4,len(self.intents));self.assertFalse(self.client.logged)
        self.assertTrue(all(packet['action']=='feature-native-observe' for packet in self.boundary.commands))
        self.assertTrue(all(frame['account']['loggedIn'] for _,frame,_ in self.intents))
        self.assertNotIn('password',repr(self.intents));self.assertNotIn('expected',repr(self.intents))

    def test_other_owned_tablet_page_and_actual_pagination_use_normal_home_and_page_controls(self):
        self.client.panel='other';self.client.menu_page=2
        self.menu.logout()
        self.assertEqual('nav.home',self.client.inputs[0][0]);self.assertIn(('tabletPage.2',''),self.client.inputs)
        self.assertFalse(self.client.logged)

    def test_foreign_anonymous_pending_or_wrong_endpoint_cannot_receive_logout_input(self):
        for edit in (dict(principalSha256='f'*64),dict(loginPending=True),dict(refreshPending=True),
                     dict(endpointSha256='f'*64),dict(credentialActive=False)):
            self.native_edits=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):self.menu.logout()
        self.assertEqual([],self.client.inputs)
        self.native_edits={};self.client.logged=False
        with self.assertRaises(NativeUIError):self.menu.logout()
        self.assertEqual([],self.client.inputs)

    def test_ignored_menu_and_logout_are_detected_without_repeating_the_click(self):
        for ignored in ('MENU','logout'):
            with self.subTest(ignored=ignored):
                self.client.panel=None;self.client.logged=True;self.client.inputs=[];self.client.ignore=ignored
                with self.assertRaises(NativeUIError):self.menu.logout()
                self.assertEqual(1,sum((label=='MENU' if ignored=='MENU' else label.startswith('Directory Service: Logout'))
                                      for _,label in self.client.inputs))
                self.assertTrue(self.client.logged)

    def test_owner_intent_failure_stops_before_sdk_input(self):
        def fail(*_args):raise OSError('synthetic private ownership failure')
        self.menu.intent=fail
        with self.assertRaises(NativeUIError):self.menu.logout()
        self.assertEqual([],self.client.inputs)

    def test_account_replaced_during_navigation_is_rejected_before_logout(self):
        self.client.after_click=lambda stage:self.native_edits.update(principalSha256='f'*64) if stage=='File' else None
        with self.assertRaises(NativeUIError):self.menu.logout()
        self.assertEqual('File',self.client.inputs[-1][1]);self.assertTrue(self.client.logged)

    def test_row_disappearance_and_delivery_do_not_claim_native_credentials_were_cleared(self):
        def misleading_ui(stage):
            if stage=='logout':self.native_edits.update(loggedIn=True,tokenPresent=True,tokenValid=True,refreshPresent=True)
        self.client.after_click=misleading_ui
        self.assertEqual({'performed':True},self.menu.logout())
        self.assertTrue(self.source.read(self.source.sequence,require_account=True)['account']['loggedIn'])
        # A complete feature owner must reject this from its later native and
        # protected/peer observations. This primitive returns no such verdict.

    def test_foreign_package_or_ambiguous_control_is_rejected_before_any_click(self):
        for fault in ('package','duplicate'):
            self.client.package='foreign.package' if fault=='package' else PACKAGE
            self.client.duplicate=fault=='duplicate'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.menu.logout()
        self.assertEqual([],self.client.inputs)

    def test_missing_native_account_extension_or_lost_guard_is_not_anonymous_success(self):
        self.boundary.mutate=lambda packet:packet.update(processId=31)
        with self.assertRaises(NativeUIError):self.menu.logout()
        self.boundary.guard_okay=False
        with self.assertRaises(NativeUIError):self.menu.logout()
        self.assertEqual([],self.client.inputs)

    def test_whole_deadline_includes_private_intent_before_the_first_input(self):
        def late(*args):self.intent(*args);self.client.clock=21
        self.menu.intent=late
        with self.assertRaises(NativeUIError):self.menu.logout()
        self.assertEqual(1,len(self.intents));self.assertEqual([],self.client.inputs)

    def test_source_guard_lost_after_ownership_write_prevents_the_click(self):
        def lost(*args):self.intent(*args);self.source.guard=lambda:False
        self.menu.intent=lost
        with self.assertRaises(NativeUIError):self.menu.logout()
        self.assertEqual(1,len(self.intents));self.assertEqual([],self.client.inputs)

    def test_bound_phone_factory_uses_existing_sdk_and_original_native_account_sources(self):
        import test_feature_adapters as bound
        f=bound.FeatureAdapterTests('test_existing_input_scope_admits_normal_file_input_without_parent_session_repair')
        f.setUp();self.addCleanup(f.doCleanups)
        source=f.native_feature_boundaries();f.read_only_boundaries()
        source.mutate=self.boundary.mutate
        sdk=f.native.call
        def call(method,path,body=None):
            if method=='GET' and path=='/session/native-session':return sdk(method,path,body)
            return self.client.call(method,path,body)
        boundary=patch.object(f.native,'call',side_effect=call);boundary.start();self.addCleanup(boundary.stop)
        menu=f.adapter._account_menu(bound.SELECTOR,self.intent,RUN,ORIGIN)
        self.assertEqual({'performed':True},menu.logout());self.assertFalse(self.client.logged)
        self.assertTrue(all(command['action']=='feature-native-observe' for command in source.commands))

    def test_factory_candidate_change_cannot_send_menu_input(self):
        import test_feature_adapters as bound
        f=bound.FeatureAdapterTests('test_existing_input_scope_admits_normal_file_input_without_parent_session_repair')
        f.setUp();self.addCleanup(f.doCleanups)
        f.native_feature_boundaries();f.read_only_boundaries()
        menu=f.adapter._account_menu(bound.SELECTOR,self.intent,RUN,ORIGIN)
        f.fixture.adb.digest='f'*64
        with self.assertRaises(NativeUIError):menu.logout()
        self.assertEqual([],f.native.inputs)


if __name__=='__main__':unittest.main()
