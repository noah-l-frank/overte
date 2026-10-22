"""Real loopback HTTP and journals; synthetic Settings server, no domain/device."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from fixture.create_permissions import CreatePermissions,STANDARD,OVERRIDES

DOMAIN='12345678-1234-4234-8234-123456789abc'
CALL=dict(schemaVersion=1,runId='b'*32,ownerToken='d'*64)


class Settings(BaseHTTPRequestHandler):
    def do_GET(self):
        body=self.server.domain.encode() if self.path=='/id' else json.dumps({'values':{'security':self.server.security}}).encode()
        self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_POST(self):
        value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.posts.append(deepcopy(value))
        if not self.server.ignore:self.server.security.update(value['security'])
        body=b'{"status":"success"}';self.send_response(200)
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*_args):pass


class CreatePermissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
        self.process=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.read()'],stdin=subprocess.PIPE)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Settings)
        self.server.security={key:[] for key in OVERRIDES}
        self.server.security.update(standard_permissions=[dict(permissions_id=name,id_can_connect=True,
            id_can_rez=True,id_can_rez_tmp=name!='anonymous',id_can_rez_avatar_entities=True) for name in STANDARD],
            unmodified='private settings are hashed, never journaled')
        self.original=deepcopy(self.server.security);self.server.domain=DOMAIN;self.server.posts=[];self.server.ignore=False
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.owned=True;self.store=PrivateFeatureState(self.root/'permissions.json')
        self.controller=self.build()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        self.process.stdin.close();self.process.wait(timeout=2);self.temporary.cleanup()
    def build(self):
        return CreatePermissions(self.process,lambda pid:self.owned and pid==self.process.pid,
            self.server.server_address[1],DOMAIN,self.store)
    def call(self,operation,**extra):return self.controller.request(CALL|dict(operation=operation)|extra)
    def test_real_http_change_readback_and_exact_original_restoration(self):
        before=self.call('observe');self.assertEqual([],self.server.posts)
        denied=self.call('set',allowed=False)
        self.assertTrue(all(not row['id_can_rez'] and not row['id_can_rez_tmp'] for row in denied['standard']))
        self.assertEqual({'security'},set(self.server.posts[0]));self.assertEqual({'standard_permissions'},set(self.server.posts[0]['security']))
        self.call('set',allowed=True);self.call('restore');self.assertEqual(self.original,self.server.security)
        self.assertTrue(self.call('retire')['restored']);self.assertIsNone(self.store.read())
    def test_ack_without_actual_effect_is_red_and_keeps_original_journal(self):
        self.server.ignore=True
        with self.assertRaises(NativeUIError):self.call('set',allowed=False)
        self.assertEqual('changing',self.store.read()['phase'])
        self.assertEqual(self.original['standard_permissions'],self.store.read()['original'])
        self.assertEqual(self.original,self.server.security)
    def test_lost_response_recovers_actual_state_without_post_replay(self):
        self.call('observe');original=self.controller.original;count=[0]
        def lose():
            count[0]+=1
            if count[0]==2:raise OSError('Synthetic read loss after actual POST')
            return original()
        self.controller.original=lose
        with self.assertRaises(OSError):self.call('set',allowed=False)
        self.controller=self.build();observed=self.call('observe')
        self.assertFalse(any(row['id_can_rez'] for row in observed['standard']));self.assertEqual(1,len(self.server.posts))
        self.call('restore');self.assertEqual(self.original,self.server.security)
    def test_foreign_domain_and_permission_overrides_refuse_all_writes(self):
        for fault in ('domain','override'):
            with self.subTest(fault=fault):
                self.server.domain=DOMAIN;self.server.security=deepcopy(self.original)
                if fault=='domain':self.server.domain='ffffffff-ffff-4fff-8fff-ffffffffffff'
                else:self.server.security['permissions']=[{'permissions_id':'unrelated'}]
                with self.assertRaises(NativeUIError):self.call('set',allowed=False)
                self.assertEqual([],self.server.posts);self.assertIsNone(self.store.read())
    def test_foreign_settings_change_cannot_be_overwritten_by_restoration(self):
        self.call('set',allowed=False);self.server.security['unmodified']='external change'
        with self.assertRaises(NativeUIError):self.call('restore')
        self.assertEqual(1,len(self.server.posts));self.assertEqual('external change',self.server.security['unmodified'])
    def test_different_run_token_or_process_owner_cannot_take_over(self):
        self.call('observe')
        for change in ({'runId':'e'*32},{'ownerToken':'e'*64}):
            with self.assertRaises(NativeUIError):self.controller.request(CALL|dict(operation='set',allowed=False)|change)
        self.owned=False
        with self.assertRaises(NativeUIError):self.call('restore')
        self.assertEqual([],self.server.posts)
    def test_journal_excludes_settings_secrets_and_external_journal_changes_block_mutation(self):
        self.call('observe');self.assertNotIn('private settings',self.store.path.read_text())
        saved=self.store.read();changed=saved|dict(phase='foreign');self.store.write(changed,saved)
        with self.assertRaises(NativeUIError):self.call('set',allowed=False)
        self.assertEqual([],self.server.posts)
    def test_restore_is_idempotent_and_retired_controller_never_grants_again(self):
        self.call('set',allowed=False);self.call('restore');self.call('restore');self.call('retire');self.call('retire')
        before=len(self.server.posts)
        with self.assertRaises(NativeUIError):self.call('set',allowed=True)
        self.assertEqual(before,len(self.server.posts));self.assertEqual(self.original,self.server.security)


if __name__=='__main__':unittest.main()
