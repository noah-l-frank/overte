"""Device-free counterexamples for complete private diagnostic publication."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location(
    'phone_diagnostics', Path(__file__).with_name('phone_diagnostics.py'))
logs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(logs)


class PhoneDiagnosticLogsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.private = self.root / 'original.private.log'
        self.public = self.root / 'public'

    def tearDown(self):
        self.temp.cleanup()

    def original(self, raw):
        self.private.write_bytes(raw)
        self.private.chmod(0o600)

    def published(self, result):
        return b''.join((self.public / p['name']).read_bytes()
                        for p in result['parts'])

    def test_complete_large_log_preserves_terminal_failure_and_original(self):
        raw = b'normal progress\n' * 300000 + b'error: assignment-client exited while fixture was active\n'
        self.original(raw)
        result = logs.publish_log(self.private, self.public, set())
        self.assertEqual(raw, self.published(result))
        self.assertEqual(raw, self.private.read_bytes())
        self.assertEqual(result['originalSha256'], hashlib.sha256(raw).hexdigest())
        self.assertGreater(len(result['parts']), 4)
        self.assertFalse(result['truncated'])
        self.assertEqual(result['originalLines'], result['publicLines'])
        self.assertTrue(all(p['bytes'] <= 1024 * 1024 for p in result['parts']))
        self.assertEqual(json.loads((self.public / 'index.json').read_text()), result)

    def test_actual_secrets_are_removed_before_chunking_including_multiline(self):
        secrets = {'actual-device-selector-12345', 'multi\nline-secret-67890'}
        raw = ('a' * 119 + '|'.join(secrets) + '\nGo touch acknowledged; connection still absent\n').encode()
        self.original(raw)
        result = logs.publish_log(self.private, self.public, secrets, chunk_bytes=128)
        public = self.published(result).decode()
        for value in secrets:
            self.assertNotIn(value, public)
        self.assertIn('connection still absent', public)
        self.assertEqual(raw, self.private.read_bytes())

    def test_credentials_urls_and_peer_addresses_are_private(self):
        raw = ('''"controlToken": "sensitive-value"\nAuthorization: Bearer sensitive-value\n'''
               ''''deviceSerial': 'hardware-12345'\n'''
               '''http://name:password@192.168.1.2/path?token=one\n'''
               '''Peer 192.168.1.2 2001:db8::1 01:23:45:67:89:ab\n'''
               '''Domain 12345678-abcd-1234-5678-123456789abc failed\n'''
               '''GET /endpoint?token=relative-secret HTTP/1.1\n''').encode()
        self.original(raw)
        result = logs.publish_log(self.private, self.public, set())
        public = self.published(result).decode()
        for value in ('sensitive-value', 'hardware-12345', '192.168.1.2',
                      '2001:db8::1', '01:23:45:67:89:ab', 'password@',
                      '12345678-abcd-1234-5678-123456789abc', 'relative-secret'):
            self.assertNotIn(value, public)
        self.assertEqual(result['originalLines'], result['publicLines'])

    def test_foreign_mode_symlink_hardlink_and_old_output_are_rejected(self):
        self.original(b'error: retained\n')
        self.private.chmod(0o644)
        with self.assertRaises(logs.DiagnosticPrivacyError):
            logs.publish_log(self.private, self.public, set())
        self.private.chmod(0o600)
        alias = self.root / 'alias'
        alias.symlink_to(self.private)
        with self.assertRaises(logs.DiagnosticPrivacyError):
            logs.publish_log(alias, self.public, set())
        alias.unlink()
        os.link(self.private, alias)
        with self.assertRaises(logs.DiagnosticPrivacyError):
            logs.publish_log(self.private, self.public, set())
        alias.unlink()
        self.public.mkdir()
        (self.public / 'old').write_text('old')
        with self.assertRaises(logs.DiagnosticPrivacyError):
            logs.publish_log(self.private, self.public, set())
        self.assertEqual((self.public / 'old').read_text(), 'old')

    def test_original_drift_blocks_publication(self):
        self.original(b'error: original\n')
        original_sanitize = logs.sanitize

        def changed(text, values):
            self.private.write_bytes(b'foreign replacement\n')
            return original_sanitize(text, values)

        with mock.patch.object(logs, 'sanitize', changed):
            with self.assertRaisesRegex(logs.DiagnosticPrivacyError, 'ORIGINAL_CHANGED'):
                logs.publish_log(self.private, self.public, set())
        self.assertFalse(self.public.exists())

    def test_nul_binary_fails_closed_and_non_utf8_is_explicit(self):
        self.original(b'binary\0secret')
        with self.assertRaises(logs.DiagnosticPrivacyError):
            logs.publish_log(self.private, self.public, set())
        self.assertFalse(self.public.exists())
        self.original(b'error: invalid byte \xff\n')
        result = logs.publish_log(self.private, self.public, set())
        self.assertFalse(result['originalUtf8Valid'])
        self.assertEqual(self.private.read_bytes(), b'error: invalid byte \xff\n')

    def test_unicode_chunks_and_empty_output_are_not_silently_lost(self):
        self.original(('progress ä→🙂\n' * 100).encode())
        result = logs.publish_log(self.private, self.public, set(), chunk_bytes=128)
        self.assertEqual(self.private.read_bytes(), self.published(result))
        for row in result['parts']:
            (self.public / row['name']).read_bytes().decode('utf-8')
        empty = self.root / 'empty'
        self.original(b'')
        result = logs.publish_log(self.private, empty, set())
        self.assertEqual(result['parts'], [])
        self.assertEqual(result['originalBytes'], 0)

    def test_unknown_native_account_names_and_signature_diagnostics_never_leak(self):
        raw = ('Error decrypting directory services username signature for unknown-account-123 - denying connection.\n'
               'Requesting optimistic public key for user "unapproved-account-456"\n'
               'Extracted public key for unapproved-account-456\n'
               'accepting login: "another-account-789"\n'
               '{"domainUsername":"hidden-native-account-ABC", "displayName":"private display"}\n'
               'error: assignment-client exited while fixture was active\n').encode()
        self.original(raw)
        result = logs.publish_log(self.private, self.public, set(), chunk_bytes=128)
        public = self.published(result).decode()
        for value in ('unknown-account-123', 'unapproved-account-456', 'another-account-789',
                      'hidden-native-account-ABC', 'private display'):
            self.assertNotIn(value, public)
        self.assertIn('<private-auth-signature-rejected>', public)
        self.assertIn('assignment-client exited', public)
        self.assertEqual(result['originalLines'], result['publicLines'])
        self.assertEqual(self.private.read_bytes(), raw)

    def test_pem_incomplete_pem_bare_signature_email_and_home_paths_are_private(self):
        raw = ('contact synthetic.person+lab@example.invalid\n'
               'loading /home/private-login/secret/config.json failed\n'
               'loading /root/private/credential.json failed\n'
               '-----BEGIN RSA PRIVATE KEY-----\n'
               'synthetic-short-key-line\n'
               '-----END RSA PRIVATE KEY-----\n'
               '{"publicKey":"small-secret-key", "usernameSignature":"short-signature"}\n'
               + 'QUJD' * 50 + '\n'
               + 'ab12' * 30 + '\n'
               + '-----BEGIN PUBLIC KEY-----\nunfinished-secret-key\n').encode()
        self.original(raw)
        result = logs.publish_log(self.private, self.public, set(), chunk_bytes=128)
        public = self.published(result).decode()
        for value in ('synthetic.person', 'example.invalid', 'private-login', '/root/private',
                      'synthetic-short-key-line', 'small-secret-key', 'short-signature',
                      'QUJD' * 10, 'ab12' * 10, 'unfinished-secret-key', 'BEGIN'):
            self.assertNotIn(value, public)
        self.assertEqual(result['originalLines'], result['publicLines'])

    def test_multiline_private_values_retain_every_original_line(self):
        raw = b'head\r\nmulti\r\nline-secret\r\ntail\r\n'
        self.original(raw)
        result = logs.publish_log(self.private, self.public, {'multi\r\nline-secret'}, chunk_bytes=128)
        public = self.published(result)
        self.assertEqual(public.count(b'\r\n'), raw.count(b'\r\n'))
        self.assertEqual(result['originalLines'], result['publicLines'])
        self.assertNotIn(b'line-secret', public)


if __name__ == '__main__':
    unittest.main()
