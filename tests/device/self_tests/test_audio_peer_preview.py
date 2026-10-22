"""Actual PC preview private-file owner counterexamples; synthetic file producer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from voice_peer.runtime import Peer,InfrastructureError


class AudioPeerPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700);self.capture='a'*32
        self.peer=Peer.__new__(Peer);self.peer.root=self.root;self.peer.receiving_preview=None
        self.peer.preview_instance='b'*32;self.peer.preview_used={self.capture};self.peer.preview_retired=set()
        self.path=self.root/('preview-'+self.capture+'.wav');self.journal=self.path.with_suffix('.json')
        self.path.write_bytes(b'synthetic original PCM container');self.path.chmod(0o600);info=self.path.stat()
        self.value=dict(schemaVersion=1,captureId=self.capture,bytes=info.st_size,sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(),device=info.st_dev,inode=info.st_ino)
        self.journal.write_text(json.dumps(self.value));self.journal.chmod(0o600)
        self.env=patch.dict(os.environ,{'OVERTE_E2E_RECORDED_PREVIEW_TESTS':'1'});self.env.start();self.addCleanup(self.env.stop)
    def query(self,action='preview-files',capture=None):
        request=secrets.token_hex(16);value=self.peer.preview(dict(action=action,capture_id=capture or self.capture,request_id=request));self.assertEqual(request,value['requestId']);return value

    def test_original_inode_bytes_and_sha_are_observed_then_separately_absent_and_retired(self):
        before=self.query();self.assertTrue(before['exists']);self.assertFalse(before['retired']);self.assertEqual(self.value,before['original'])
        self.query('preview-release');after=self.query();self.assertFalse(after['exists']);self.assertTrue(after['retired']);self.assertIsNone(after['original'])
        self.query('preview-release');self.assertFalse(self.query()['exists'])

    def test_modified_pcm_missing_pair_and_wrong_original_inode_cannot_be_green(self):
        original=self.path.read_bytes();self.path.write_bytes(b'x'*len(original))
        with self.assertRaises(InfrastructureError):self.query()
        self.path.write_bytes(original);backup=self.journal.with_suffix('.held');self.journal.rename(backup)
        with self.assertRaises((OSError,InfrastructureError)):self.query('preview-release')
        backup.rename(self.journal);value=dict(self.value,inode=self.value['inode']+1);self.journal.write_text(json.dumps(value))
        with self.assertRaises(InfrastructureError):self.query('preview-release')
        self.assertTrue(self.path.exists());self.assertNotIn(self.capture,self.peer.preview_retired)

    def test_dangling_symlink_and_hardlink_never_report_empty_or_get_deleted(self):
        self.path.unlink();self.journal.unlink();self.path.symlink_to(self.root/'missing')
        with self.assertRaises((OSError,InfrastructureError)):self.query('preview-release')
        self.assertTrue(self.path.is_symlink());self.path.unlink();self.path.write_bytes(b'input');self.path.chmod(0o600)
        os.link(self.path,self.root/'foreign-link')
        with self.assertRaises((OSError,InfrastructureError)):self.query('preview-release')
        self.assertTrue((self.root/'foreign-link').exists())

    def test_busy_unknown_owner_disabled_or_missing_nonce_reject_before_cleanup(self):
        self.peer.receiving_preview=self.capture
        with self.assertRaises(InfrastructureError):self.query('preview-release')
        self.peer.receiving_preview=None;self.peer.preview_used.clear()
        with self.assertRaises(ValueError):self.query('preview-release')
        self.assertTrue(self.path.exists())
        with patch.dict(os.environ,{'OVERTE_E2E_RECORDED_PREVIEW_TESTS':'0'}),self.assertRaises(ValueError):self.query()
        with self.assertRaises(ValueError):self.peer.preview(dict(action='preview-files',capture_id=self.capture))


if __name__=='__main__':unittest.main()
