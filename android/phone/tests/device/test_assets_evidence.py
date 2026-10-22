"""Historical parse reuse keeps original inode/bytes/guards authoritative."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
import test_emote_originals
from test_graphics_images import BINDING
from adapters.normal_ui import NativeUIError
from overte_phone_assets_evidence import AssetsOriginals

class AssetsEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='assets-history-');self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.clock=0.;self.okay=True
        self.owner=AssetsOriginals(self.root,BINDING,'d'*32,'primary',lambda:self.okay,lambda *_:True,kind='assets',monotonic=lambda:self.clock)
        self.frame=dict(originalEpochMs=12000,rows=[dict(original='actual')]);ref=self.owner.write(1,self.frame);self.value=self.owner.expand(ref)
        self.assertEqual(self.frame,self.owner.read(self.value))
    def test_returned_graph_cannot_mutate_cached_original(self):
        changed=self.owner.read(self.value);changed['rows'][0]['original']='foreign'
        self.assertEqual(self.frame,self.owner.read(self.value))
    def test_cache_cannot_replace_actual_bytes_inode_mode_link_or_live_guard(self):
        path=self.owner.path(self.value);raw=path.read_bytes()
        path.write_bytes(raw.replace(b'actual',b'forged'))
        with self.assertRaises(NativeUIError):self.owner.read(self.value)
        path.write_bytes(raw);path.chmod(0o644)
        with self.assertRaises(NativeUIError):self.owner.read(self.value)
        path.chmod(0o600);link=self.root/'alias';os.link(path,link)
        with self.assertRaises(NativeUIError):self.owner.read(self.value)
        link.unlink();self.okay=False
        with self.assertRaises(NativeUIError):self.owner.read(self.value)
        self.okay=True;replacement=self.root/'replacement';replacement.write_bytes(raw);replacement.chmod(0o600);os.replace(replacement,path)
        with self.assertRaises(NativeUIError):self.owner.read(self.value)
    def test_cached_read_keeps_real_elapsed_five_second_guard(self):
        original=self.owner.file;calls=[0]
        def slow(*args):
            original(*args);calls[0]+=1
            if calls[0]==2:self.clock+=5.001
        self.owner.file=slow
        with self.assertRaises(NativeUIError):self.owner.read(self.value)

if __name__=='__main__':unittest.main()
