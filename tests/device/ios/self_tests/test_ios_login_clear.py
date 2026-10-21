"""Secret-free ordinary username clear uses the actual current focused token."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ios.self_tests.test_ios_normal_input import Boundary as InputBoundary
from ios.adapters import normal_input
from adapters.normal_ui import NativeUIError


class Boundary(InputBoundary):
    def __init__(self):
        super().__init__(field='login.username');self.focused=True;self.hook=True;self.ignored=False
    def observed(self):
        value=super().observed()
        value.update(sampleEpochMs=20000,loginControlsVersion=2,generation=self.instance)
        value['controls'][0].update(inputReady=True,focused=self.focused)
        if self.hook:value['loginClearInputVersion']=1
        return value
    def post(self,request,timeout):
        payload=json.loads(request.data)
        if payload['operation']=='observe':return super().post(request,timeout)
        assert payload['operation']=='edit' and payload['input']['operation']=='clear-login-username'
        assert set(payload['input'])=={'schemaVersion','commandId','instance','sequence','observedElapsedMs','fieldToken','operation'}
        self.requests.append(payload);native=payload['input'];self.sequence=native['sequence']
        self.receipt=dict(schemaVersion=1,commandId=payload['commandId'],status=dict(schemaVersion=1,
            commandId=native['commandId'],instance=self.instance,sequence=self.sequence,performed=not self.ignored,
            processId=42,sampleEpochMs=20000))
        self.response=json.dumps(payload).encode();return self
    def native(self):
        return normal_input.NativeInput(self,'owned-session',self.target,self.process,native_epoch_ms=lambda:20000,
            monotonic=self.tick,sleep=lambda _:None)


class IOSLoginClearTests(unittest.TestCase):
    def test_actual_clear_command_has_no_text_bytes_or_secret_value_carrier(self):
        b=Boundary()
        with patch.object(normal_input,'urlopen',b.post):
            self.assertEqual({'performed':True},b.native().clear_login_username(token=b.token))
        self.assertEqual(['observe','edit'],[row['operation'] for row in b.requests])
        self.assertNotIn('text',b.requests[-1]['input'])

    def test_unfocused_retired_token_or_missing_hook_prevents_input(self):
        for fault in ('focus','token','hook'):
            b=Boundary();b.focused=fault!='focus';b.hook=fault!='hook'
            with patch.object(normal_input,'urlopen',b.post),self.assertRaises(NativeUIError):
                b.native().clear_login_username(token='11111111-2222-4333-8444-777777777777' if fault=='token' else b.token)
            self.assertEqual(['observe'],[row['operation'] for row in b.requests])

    def test_ignored_clear_is_not_accepted_or_replayed(self):
        b=Boundary();b.ignored=True
        with patch.object(normal_input,'urlopen',b.post),self.assertRaises(NativeUIError):b.native().clear_login_username(token=b.token)
        self.assertEqual(['observe','edit'],[row['operation'] for row in b.requests])


if __name__=='__main__':unittest.main()
