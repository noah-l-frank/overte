"""Owned real HTTP Settings writes; explicit synthetic domain and actor process."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
from urllib.error import HTTPError
from urllib.request import Request,urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from fixture.assets_permissions import AssetsPermissions,WRITE
from fixture.create_permissions import CreatePermissions,permission_request
from fixture.domain import DomainControlHandler
from self_tests import test_create_permissions as create_tests
from self_tests.test_create_permissions import CALL,DOMAIN


class AssetsPermissionTests(create_tests.CreatePermissionTests):
    def build(self):
        if WRITE not in self.server.security['standard_permissions'][0]:
            for row in self.server.security['standard_permissions']:row[WRITE]=row['permissions_id']!='friends'
            self.original=deepcopy(self.server.security)
        return AssetsPermissions(self.process,lambda pid:self.owned and pid==self.process.pid,
            self.server.server_address[1],DOMAIN,self.store)
    def test_real_http_change_readback_and_exact_original_restoration(self):
        before=self.call('observe');self.assertEqual([],self.server.posts)
        self.assertEqual(1,before['assetsPermissionsVersion']);self.assertNotIn('createPermissionsVersion',before)
        denied=self.call('set',allowed=False)
        self.assertTrue(all(not row[WRITE] for row in denied['standard']))
        unchanged=lambda rows:[{key:value for key,value in row.items() if key!=WRITE} for row in rows]
        self.assertEqual(unchanged(before['standard']),unchanged(denied['standard']))
        self.assertEqual({'security'},set(self.server.posts[0]));self.assertEqual({'standard_permissions'},set(self.server.posts[0]['security']))
        self.call('set',allowed=True);self.call('restore');self.assertEqual(self.original,self.server.security)
        self.assertTrue(self.call('retire')['restored']);self.assertIsNone(self.store.read())
    def test_lost_response_recovers_actual_state_without_post_replay(self):
        self.call('observe');original=self.controller.original;count=[0]
        def lose():
            count[0]+=1
            if count[0]==2:raise OSError('Synthetic read loss after actual POST')
            return original()
        self.controller.original=lose
        with self.assertRaises(OSError):self.call('set',allowed=False)
        self.controller=self.build();observed=self.call('observe')
        self.assertFalse(any(row[WRITE] for row in observed['standard']));self.assertEqual(1,len(self.server.posts))
        self.call('restore');self.assertEqual(self.original,self.server.security)
    def test_missing_or_nonboolean_actual_write_field_is_red_before_journal_or_post(self):
        for value in (None,1,'true'):
            self.server.security=deepcopy(self.original)
            if value is None:self.server.security['standard_permissions'][0].pop(WRITE)
            else:self.server.security['standard_permissions'][0][WRITE]=value
            with self.subTest(value=value),self.assertRaises(NativeUIError):self.call('observe')
            self.assertEqual([],self.server.posts);self.assertIsNone(self.store.read())
    def test_create_and_assets_never_adopt_each_others_active_settings_lease(self):
        create=CreatePermissions(self.process,lambda pid:pid==self.process.pid,self.server.server_address[1],DOMAIN,
            PrivateFeatureState(self.root/'create.json'))
        permission_request(create,self.controller,CALL|dict(operation='observe'))
        with self.assertRaises(NativeUIError):permission_request(self.controller,create,CALL|dict(operation='observe'))
        self.assertIsNone(self.store.read());self.assertEqual([],self.server.posts)
        permission_request(create,self.controller,CALL|dict(operation='set',allowed=False))
        permission_request(create,self.controller,CALL|dict(operation='restore'))
        permission_request(create,self.controller,CALL|dict(operation='retire'))
        permission_request(self.controller,create,CALL|dict(operation='set',allowed=False))
        with self.assertRaises(NativeUIError):permission_request(create,self.controller,CALL|dict(operation='observe'))
        self.call('restore');self.call('retire');self.assertEqual(self.original,self.server.security)
    def test_default_disabled_and_explicitly_token_bound_fixture_http_endpoint(self):
        class Handler(DomainControlHandler):
            token='synthetic-private-control-token'
            assets_permissions=None
            def log_message(self,*_args):pass
        control=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=control.serve_forever,daemon=True);thread.start()
        url='http://127.0.0.1:'+str(control.server_address[1])+'/v1/assets-permissions'
        def post(token):
            with urlopen(Request(url,data=json.dumps(CALL|dict(operation='observe')).encode(),
                headers={'X-Overte-E2E-Token':token}),timeout=2) as reply:return json.loads(reply.read())
        try:
            with self.assertRaises(HTTPError) as disabled:post(Handler.token)
            self.assertEqual(503,disabled.exception.code);disabled.exception.close();self.assertIsNone(self.store.read())
            Handler.assets_permissions=staticmethod(self.controller.request)
            with self.assertRaises(HTTPError) as foreign:post('foreign-token')
            self.assertEqual(404,foreign.exception.code);foreign.exception.close();self.assertIsNone(self.store.read())
            self.assertEqual(1,post(Handler.token)['assetsPermissionsVersion'])
        finally:control.shutdown();control.server_close();thread.join(timeout=2)


if __name__=='__main__':
    import unittest
    unittest.main()
