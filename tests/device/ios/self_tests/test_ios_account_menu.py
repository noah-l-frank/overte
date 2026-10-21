"""Ordinary iOS menu pointers over original HTTP/AFC frames; SDK is synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ios.self_tests.test_ios_normal_input import Boundary as InputBoundary
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from self_tests.test_native_account_observation import account_source
from adapters.normal_ui import NativeUI,NativeUIError,W3C_ELEMENT
from ios.adapters import normal_input
from ios.adapters.normal_scripts import IOSScriptIO
from ios.adapters.account_menu import IOSAccountMenu

RUN='a'*32;ORIGIN='https://owned.invalid'


class Boundary(InputBoundary):
    def __init__(self):
        super().__init__();self.stage='closed';self.clicks=[];self.references={};self.intents=[]
        self.fault='';self.source=NativeBoundary()
        def native(value):
            value['processId']=42;account_source(value)
            value['account'].update(loggedIn=True,principalSha256=hashlib.sha256(('e2e-'+RUN).encode()).hexdigest())
            value['account']['observation'].update(endpointSha256=hashlib.sha256(ORIGIN.encode()).hexdigest(),tokenPresent=True,tokenValid=True)
        self.source.mutate=native

    def observed(self):
        value=super().observed();value.update(sampleEpochMs=20000,tabletShown=self.stage!='closed',
            featureControlsVersion=1,accountMenuControlsVersion=1,controls=[])
        identifier={'home':'scripts.menu','menu':'account.menu-file','file':'account.logout'}.get(self.stage)
        if identifier:
            row=dict(id=identifier,token=str(uuid.uuid5(uuid.NAMESPACE_URL,identifier)),enabled=True,focused=False,
                frame=dict(x=10,y=20,width=200,height=48))
            if identifier.startswith('account.'):
                label='File' if identifier=='account.menu-file' else 'Directory Service: Logout e2e-'+RUN
                if self.fault=='foreign-label' and identifier=='account.logout':label='Directory Service: Logout foreign'
                row.update(menuSourceVersion=1,sourceType=2 if identifier=='account.menu-file' else 1,
                    labelSha256=hashlib.sha256(label.encode()).hexdigest())
            value['controls'].append(row)
        return value

    def call(self,method,path,body=None):
        if path.endswith('/elements'):
            identifier=body['value']
            rows=self.observed()['controls']
            available=(identifier=='OverteTabletOpen' and self.stage=='closed' or
                identifier.removeprefix('OverteNavigation.') in {row['id'] for row in rows})
            if not available:return []
            key='node-'+str(len(self.references));self.references[key]=identifier
            return [{W3C_ELEMENT:key}]
        identifier=self.references[path.split('/element/')[1].split('/')[0]]
        if path.endswith('/displayed') or path.endswith('/enabled'):return True
        if path.endswith('/attribute/value'):
            return next(row['token'] for row in self.observed()['controls'] if row['id']==identifier.removeprefix('OverteNavigation.'))
        assert path.endswith('/click') and method=='POST'
        self.clicks.append(identifier)
        if self.fault=='ignored':return
        self.stage={'OverteTabletOpen':'home','OverteNavigation.scripts.menu':'menu',
            'OverteNavigation.account.menu-file':'file','OverteNavigation.account.logout':'done'}[identifier]

    def flow(self):
        native=normal_input.NativeInput(self,'owned-session',self.target,self.process,native_epoch_ms=lambda:20000,
            monotonic=lambda:self.clock,sleep=lambda s:setattr(self,'clock',self.clock+s))
        ui=NativeUI(self,'owned-session',native._check,monotonic=lambda:self.clock,sleep=lambda s:setattr(self,'clock',self.clock+s))
        io=IOSScriptIO(ui,native);source=self.source.reader(ios=True);source.pid=42
        def intent(*values):
            self.intents.append(deepcopy(values))
            if self.fault=='intent':raise NativeUIError('synthetic journal failure')
        return IOSAccountMenu(io,source,intent,RUN,ORIGIN)


class IOSAccountMenuTests(unittest.TestCase):
    def test_normal_file_logout_uses_current_native_tokens_and_returns_input_only(self):
        b=Boundary()
        with patch.object(normal_input,'urlopen',b.post):self.assertEqual({'performed':True},b.flow().logout())
        self.assertEqual(['OverteTabletOpen','OverteNavigation.scripts.menu','OverteNavigation.account.menu-file',
                          'OverteNavigation.account.logout'],b.clicks)
        self.assertEqual(4,len(b.intents));self.assertTrue(b.source.sample['account']['loggedIn'])
        self.assertEqual({'normal-ui-input'},{row['action'] for row in b.requests})
        self.assertTrue(all(row['operation']=='observe' for row in b.requests))

    def test_foreign_original_logout_label_is_not_clicked(self):
        b=Boundary();b.fault='foreign-label'
        with patch.object(normal_input,'urlopen',b.post),self.assertRaises(NativeUIError):b.flow().logout()
        self.assertNotIn('OverteNavigation.account.logout',b.clicks)

    def test_missing_owned_principal_or_intent_persistence_blocks_input(self):
        for fault in ('principal','intent'):
            b=Boundary()
            if fault=='principal':
                previous=b.source.mutate
                def foreign(value):previous(value);value['account']['principalSha256']='f'*64
                b.source.mutate=foreign
            else:b.fault='intent'
            with patch.object(normal_input,'urlopen',b.post),self.assertRaises(NativeUIError):b.flow().logout()
            self.assertEqual([],b.clicks)

    def test_ignored_menu_pointer_does_not_become_logout_and_is_not_repeated(self):
        b=Boundary();b.stage='home';b.fault='ignored'
        with patch.object(normal_input,'urlopen',b.post),self.assertRaises(NativeUIError):b.flow().logout()
        self.assertEqual(['OverteNavigation.scripts.menu'],b.clicks)


if __name__=='__main__':unittest.main()
