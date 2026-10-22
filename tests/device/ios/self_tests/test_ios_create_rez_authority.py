"""Real local HTTP and durable control tests; no DomainServer is launched."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from fixture.create_rez_authority import CreateRezAuthority, CreateRezControl, STANDARD_IDS, fixture_permissions


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args): pass
    def do_GET(self):
        fixture = self.server.fixture
        raw = (fixture.binding['domainId'].encode() if self.path == '/id' else
               json.dumps(dict(values=dict(security=fixture.security), descriptions=[])).encode())
        self.send_response(200); self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_POST(self):
        fixture = self.server.fixture; fixture.posts += 1
        command = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if not fixture.ignore: fixture.security['standard_permissions'] = command['security']['standard_permissions']
        if fixture.lose: self.close_connection = True; return
        raw = b'{"status":"success"}'; self.send_response(200); self.send_header('Content-Length', str(len(raw)))
        self.end_headers(); self.wfile.write(raw)


class RezAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name); self.path.chmod(0o700)
        self.store = PrivateFeatureState(self.path/'create-rez-authority.json')
        self.binding = dict(processId=42, startIdentity='12345', domainId='11111111-1111-4111-8111-111111111111')
        self.security = dict(standard_permissions=[dict(permissions_id=name, id_can_rez=name in ('anonymous', 'localhost'),
            id_can_rez_tmp=name == 'localhost', id_can_connect=True, id_can_write_to_asset_server=name == 'localhost') for name in sorted(STANDARD_IDS)])
        self.posts = 0; self.ignore = self.lose = False
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler); self.server.fixture = self
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01}, daemon=True); self.thread.start()
        self.addCleanup(self.server.server_close); self.addCleanup(self.thread.join, 2); self.addCleanup(self.server.shutdown)
        self.origin = 'http://127.0.0.1:'+str(self.server.server_port)
    def owner(self): return CreateRezAuthority(self.origin, self.store, lambda: deepcopy(self.binding))

    def test_both_rez_bits_are_changed_via_actual_api_and_original_unrelated_permissions_restore(self):
        owner = self.owner(); original = deepcopy(self.security); first = owner.prepare(); denied = owner.transition(False)
        self.assertTrue(all(not row['id_can_rez'] and not row['id_can_rez_tmp'] for row in denied['standardPermissions']))
        self.assertEqual(original['standard_permissions'][0]['id_can_write_to_asset_server'],
                         self.security['standard_permissions'][0]['id_can_write_to_asset_server'])
        recovered = owner.transition(True); self.assertEqual(first['standardPermissions'], recovered['standardPermissions'])
        owner.restore(); self.owner().restore()
        self.assertEqual(original, self.security); self.assertEqual(2, self.posts); self.assertIsNotNone(self.store.read())
        self.assertNotIn('canRez', recovered)  # HTTP rows are never native effective permission.

    def test_success_ack_without_changed_actual_settings_fails_and_keeps_pending_owner(self):
        owner = self.owner(); owner.prepare(); self.ignore = True
        with self.assertRaises(NativeUIError): owner.transition(False)
        self.assertEqual('issued', self.owner().state['phase']); self.assertEqual(1, self.posts)
        with self.assertRaises(NativeUIError): self.owner().transition(False)
        self.assertEqual(1, self.posts)

    def test_lost_post_return_is_recovered_by_get_without_mutation_resend(self):
        owner = self.owner(); owner.prepare(); self.lose = True
        with self.assertRaises(Exception): owner.transition(False)
        self.assertEqual('issued', self.owner().state['phase']); self.assertEqual(1, self.posts)
        self.lose = False; recovered = self.owner(); recovered.recover()
        self.assertEqual('ready', recovered.state['phase']); self.assertEqual(1, self.posts)
        recovered.restore(); self.assertEqual(2, self.posts)

    def test_foreign_process_and_unrelated_settings_change_refuse_control(self):
        owner = self.owner(); owner.prepare(); self.binding['processId'] = 43
        with self.assertRaises(NativeUIError): owner.transition(False)
        self.assertEqual(0, self.posts); self.binding['processId'] = 42
        self.security['standard_permissions'][0]['id_can_write_to_asset_server'] = not self.security['standard_permissions'][0]['id_can_write_to_asset_server']
        with self.assertRaises(NativeUIError): owner.transition(False)
        self.assertEqual(0, self.posts)

    def test_other_permission_override_tables_and_remote_admin_origins_are_outside_closed_fixture(self):
        self.security['permissions'] = [dict(permissions_id='some-user', id_can_rez=True)]
        with self.assertRaises(NativeUIError): self.owner().prepare()
        self.assertIsNone(self.store.read()); self.assertEqual(0, self.posts)
        with self.assertRaises(NativeUIError): CreateRezAuthority('http://192.0.2.10:40100', self.store, lambda: self.binding)

    def test_private_control_nonce_survives_lost_return_and_cannot_adopt_another_run(self):
        store = PrivateFeatureState(self.path/'create-rez-control.json'); control = CreateRezControl(self.owner(), store)
        command = dict(schemaVersion=1, commandId='a'*32, runId='b'*32, operation='set', allowed=False)
        self.lose = True
        with self.assertRaises(Exception): control.handle(command)
        self.assertEqual(1, self.posts); self.lose = False
        recovered = CreateRezControl(self.owner(), store); original = recovered.handle(command)
        self.assertEqual(original, recovered.handle(command)); self.assertEqual(1, self.posts)
        with self.assertRaises(NativeUIError): recovered.handle(dict(command, allowed=True))
        with self.assertRaises(NativeUIError): recovered.handle(dict(command, commandId='c'*32, runId='d'*32))

    def test_opt_in_fixture_profile_preserves_existing_defaults_and_materializes_false_bits(self):
        path = Path(__file__).resolve().parents[4]/'domain-server/resources/describe-settings.json'
        description = json.loads(path.read_text()); original = deepcopy(description)
        result = fixture_permissions(description)
        self.assertEqual(original, description); self.assertEqual(STANDARD_IDS, {row['permissions_id'] for row in result})
        anonymous = next(row for row in result if row['permissions_id'] == 'anonymous')
        self.assertTrue(anonymous['id_can_rez']); self.assertTrue(anonymous['id_can_rez_tmp'])
        self.assertTrue(anonymous['id_can_connect']); self.assertFalse(anonymous['id_can_write_to_asset_server'])


if __name__ == '__main__': unittest.main()
